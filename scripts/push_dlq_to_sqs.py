#!/usr/bin/env python3
"""
Push DLQ message files to an SQS queue.

Reads all JSON message files from a directory and sends their body content to SQS.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError
from common import AWS_REGION, SQS_QUEUE_URL


def load_messages_from_dlq(dlq_dir: str) -> List[Dict[str, Any]]:
    """
    Load all messages from DLQ directory.

    Args:
        dlq_dir: Directory containing DLQ message files

    Returns:
        List of message bodies to send to SQS
    """
    dlq_path = Path(dlq_dir)

    if not dlq_path.exists():
        print(f"Error: Directory not found: {dlq_dir}")
        return []

    # Find all JSON files (excluding backups and originals)
    json_files = [
        f for f in dlq_path.glob("*.json") if not f.name.endswith(".bak") and not f.name.endswith(".original")
    ]

    if not json_files:
        print(f"No JSON files found in {dlq_dir}")
        return []

    messages = []
    skipped_count = 0

    for json_file in json_files:
        try:
            # Read the message file
            with open(json_file, "r", encoding="utf-8") as f:
                message_data = json.load(f)

            # Extract body
            if "body" not in message_data:
                print(f"Warning: Skipping {json_file.name}: no 'body' field")
                skipped_count += 1
                continue

            body = message_data["body"]

            # Handle nested JSON string case
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    print(f"Warning: Skipping {json_file.name}: body is not valid JSON")
                    skipped_count += 1
                    continue

            # Validate required fields
            if "type" not in body:
                print(f"Warning: Skipping {json_file.name}: no 'type' field in body")
                skipped_count += 1
                continue

            messages.append({"file": json_file.name, "body": body})

        except json.JSONDecodeError as e:
            print(f"Error parsing {json_file.name}: {e}")
            skipped_count += 1
        except Exception as e:
            print(f"Error processing {json_file.name}: {e}")
            skipped_count += 1

    if skipped_count > 0:
        print(f"\nSkipped {skipped_count} files due to errors")

    return messages


def send_message_batch(sqs_client, queue_url: str, messages: List[Dict], batch_id: int, retry_count: int = 3) -> tuple:
    """
    Send a batch of messages to SQS (max 10 messages per batch).

    Args:
        sqs_client: Boto3 SQS client
        queue_url: SQS queue URL
        messages: List of message dictionaries with 'file' and 'body' keys
        batch_id: Batch identifier for logging
        retry_count: Number of retry attempts

    Returns:
        Tuple of (successful_count, failed_count, failed_messages)
    """
    # Prepare SQS batch entries (max 10 per batch)
    entries = []
    for idx, msg in enumerate(messages):
        entries.append({"Id": str(batch_id * 10 + idx), "MessageBody": json.dumps(msg["body"])})

    for attempt in range(retry_count):
        try:
            response = sqs_client.send_message_batch(QueueUrl=queue_url, Entries=entries)

            successful = len(response.get("Successful", []))
            failed = len(response.get("Failed", []))
            failed_messages = []

            if failed > 0:
                # Extract failed message IDs
                failed_ids = {f["Id"] for f in response.get("Failed", [])}
                for idx, msg in enumerate(messages):
                    entry_id = str(batch_id * 10 + idx)
                    if entry_id in failed_ids:
                        failed_messages.append(msg)

                # Log failure reasons
                for failure in response.get("Failed", []):
                    print(
                        f"  Failed ID {failure['Id']}: {failure.get('Code', 'Unknown')} - {failure.get('Message', 'No message')}"
                    )

                # Retry if not last attempt
                if attempt < retry_count - 1:
                    print(f"  Retrying batch {batch_id} (attempt {attempt + 2}/{retry_count})...")
                    time.sleep(1)  # Brief delay before retry
                    continue

            return successful, failed, failed_messages

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))

            if attempt < retry_count - 1:
                print(f"  AWS error (attempt {attempt + 1}/{retry_count}): {error_code} - {error_msg}")
                print(f"  Retrying batch {batch_id}...")
                time.sleep(2**attempt)  # Exponential backoff
                continue
            else:
                print(f"  Failed after {retry_count} attempts: {error_code} - {error_msg}")
                return 0, len(messages), messages

        except Exception as e:
            print(f"  Unexpected error: {e}")
            if attempt < retry_count - 1:
                time.sleep(1)
                continue
            return 0, len(messages), messages

    return 0, len(messages), messages


def push_messages_to_sqs(
    dlq_dir: str, queue_url: str, region: str = AWS_REGION, dry_run: bool = False, batch_size: int = 10
):
    """
    Push all DLQ messages to SQS queue.

    Args:
        dlq_dir: Directory containing DLQ message files
        queue_url: SQS queue URL
        region: AWS region
        dry_run: If True, only preview what would be sent
        batch_size: Number of messages per batch (max 10 for SQS)
    """
    if batch_size > 10:
        print("Warning: SQS batch size limit is 10, using 10")
        batch_size = 10

    print(f"Loading messages from: {dlq_dir}")
    messages = load_messages_from_dlq(dlq_dir)

    if not messages:
        print("No messages to send")
        return

    print(f"Found {len(messages)} messages to send")
    print(f"Queue URL: {queue_url}")
    print(f"Dry run: {dry_run}")
    print()

    if dry_run:
        print("Dry run mode - previewing messages:")
        for i, msg in enumerate(messages[:5], 1):
            print(f"\nMessage {i} (from {msg['file']}):")
            print(json.dumps(msg["body"], indent=2))
        if len(messages) > 5:
            print(f"\n... and {len(messages) - 5} more messages")
        print(f"\nWould send {len(messages)} messages to SQS")
        return

    # Initialize SQS client
    try:
        sqs_client = boto3.client("sqs", region_name=region)
        print(f"Connected to SQS (region: {region})")
    except Exception as e:
        print(f"Error connecting to SQS: {e}")
        return

    # Send messages in batches
    total_successful = 0
    total_failed = 0
    all_failed_messages = []

    # Split messages into batches
    batches = [messages[i : i + batch_size] for i in range(0, len(messages), batch_size)]

    print(f"Sending {len(messages)} messages in {len(batches)} batches...")
    print()

    for batch_idx, batch in enumerate(batches, 1):
        print(f"Batch {batch_idx}/{len(batches)} ({len(batch)} messages)...", end=" ")

        successful, failed, failed_msgs = send_message_batch(sqs_client, queue_url, batch, batch_idx - 1)

        total_successful += successful
        total_failed += failed
        all_failed_messages.extend(failed_msgs)

        if successful > 0:
            print(f"✓ {successful} sent", end="")
        if failed > 0:
            print(f" ✗ {failed} failed", end="")
        print()

        # Brief delay between batches to avoid throttling
        if batch_idx < len(batches):
            time.sleep(0.1)

    print()
    print("=" * 60)
    print(f"Total messages processed: {len(messages)}")
    print(f"Successfully sent: {total_successful}")
    print(f"Failed: {total_failed}")

    if all_failed_messages:
        print(f"\nFailed messages ({len(all_failed_messages)}):")
        for msg in all_failed_messages[:10]:  # Show first 10
            print(f"  - {msg['file']}")
        if len(all_failed_messages) > 10:
            print(f"  ... and {len(all_failed_messages) - 10} more")


def main():
    parser = argparse.ArgumentParser(
        description="Push DLQ message files to an SQS queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Push all messages from DLQ directory to SQS
  python push_dlq_to_sqs.py --queue-url https://sqs.us-east-2.amazonaws.com/956728988776/MyPOCQueue --dlq-dir DLQ

  # Dry run to preview what would be sent
  python push_dlq_to_sqs.py --queue-url https://sqs.us-east-2.amazonaws.com/956728988776/MyPOCQueue --dlq-dir DLQ --dry-run

  # Custom region
  python push_dlq_to_sqs.py --queue-url https://sqs.us-west-2.amazonaws.com/123456789/MyQueue --dlq-dir DLQ --region us-west-2
        """,
    )

    parser.add_argument(
        "--queue-url", type=str, default=SQS_QUEUE_URL, help="SQS queue URL (or set SQS_QUEUE_URL in .env)"
    )
    parser.add_argument(
        "--dlq-dir", type=str, default="DLQ", help="Directory containing DLQ message files (default: ./DLQ)"
    )
    parser.add_argument("--region", type=str, default=AWS_REGION, help="AWS region (default: us-east-2)")
    parser.add_argument("--dry-run", action="store_true", help="Preview messages without actually sending to SQS")
    parser.add_argument("--batch-size", type=int, default=10, help="Number of messages per batch (max 10, default: 10)")

    args = parser.parse_args()

    if not args.queue_url:
        print("Error: --queue-url is required or set SQS_QUEUE_URL in .env")
        parser.print_help()
        sys.exit(1)

    # Resolve path relative to project root
    if not args.dlq_dir.startswith("/"):
        project_root = Path(__file__).parent.parent
        dlq_path = project_root / args.dlq_dir
    else:
        dlq_path = Path(args.dlq_dir)

    push_messages_to_sqs(
        dlq_dir=str(dlq_path),
        queue_url=args.queue_url,
        region=args.region,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
