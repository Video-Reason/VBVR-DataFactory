#!/usr/bin/env python3
"""
Download all messages from SQS Dead Letter Queue and save them to DLQ directory.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
from common import AWS_REGION, SQS_QUEUE_URL


def download_dlq_messages(
    queue_url: str,
    output_dir: str,
    delete_after_download: bool = False,
    region: str = "us-east-2",
    max_messages: Optional[int] = None,
):
    """
    Download all messages from SQS DLQ and save them to files.

    Args:
        queue_url: SQS queue URL
        output_dir: Directory to save messages
        delete_after_download: If True, delete messages from queue after downloading
        region: AWS region
        max_messages: Maximum number of messages to download (None for all)
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize SQS client
    sqs = boto3.client("sqs", region_name=region)

    # Get queue attributes to check message count
    try:
        queue_attrs = sqs.get_queue_attributes(
            QueueUrl=queue_url, AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"]
        )
        approx_messages = int(queue_attrs["Attributes"].get("ApproximateNumberOfMessages", 0))
        print(f"Queue URL: {queue_url}")
        print(f"Approximate messages in queue: {approx_messages}")
        if max_messages:
            print(f"Downloading up to {max_messages} messages")
        else:
            print("Downloading all messages")
    except Exception as e:
        print(f"Warning: Could not get queue attributes: {e}")
        approx_messages = None

    downloaded_count = 0
    message_batch = 0

    while True:
        try:
            # Receive messages (max 10 at a time)
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=1,  # Short wait time
                AttributeNames=["All"],
            )

            messages = response.get("Messages", [])

            if not messages:
                # No more messages
                if downloaded_count == 0:
                    print("No messages found in DLQ")
                else:
                    print(f"\nFinished downloading. Total messages: {downloaded_count}")
                break

            # Process each message
            for msg in messages:
                if max_messages and downloaded_count >= max_messages:
                    print(f"\nReached max messages limit ({max_messages})")
                    return downloaded_count

                message_id = msg.get("MessageId", f"msg_{downloaded_count}")
                receipt_handle = msg["ReceiptHandle"]
                body = msg.get("Body", "")

                # Try to parse body as JSON
                try:
                    if body.startswith("{"):
                        body_json = json.loads(body)
                        # If it's a nested JSON string, parse again
                        if isinstance(body_json, str):
                            body_json = json.loads(body_json)
                    else:
                        body_json = {"raw_body": body}
                except json.JSONDecodeError:
                    body_json = {"raw_body": body}

                # Add metadata
                message_data = {
                    "message_id": message_id,
                    "receipt_handle": receipt_handle,
                    "timestamp": msg.get("Attributes", {}).get("SentTimestamp", ""),
                    "receive_count": msg.get("Attributes", {}).get("ApproximateReceiveCount", ""),
                    "first_receive_timestamp": msg.get("Attributes", {}).get("ApproximateFirstReceiveTimestamp", ""),
                    "attributes": msg.get("Attributes", {}),
                    "message_attributes": msg.get("MessageAttributes", {}),
                    "body": body_json,
                }

                # Generate filename with timestamp and message ID
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{message_id}.json"
                filepath = output_path / filename

                # Save message to file
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(message_data, f, indent=2, ensure_ascii=False)

                downloaded_count += 1

                # Delete message from queue if requested
                if delete_after_download:
                    try:
                        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
                    except Exception as e:
                        print(f"Warning: Failed to delete message {message_id}: {e}")

                if downloaded_count % 10 == 0:
                    print(f"Downloaded {downloaded_count} messages...", end="\r")

            message_batch += 1

        except Exception as e:
            print(f"\nError processing messages: {e}")
            break

    print(f"\nTotal messages downloaded: {downloaded_count}")
    return downloaded_count


def main():
    parser = argparse.ArgumentParser(
        description="Download all messages from SQS Dead Letter Queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all messages from DLQ
  python download_dlq_messages.py --queue-url https://sqs.us-east-2.amazonaws.com/123456789/dlq-name

  # Download and delete messages from queue
  python download_dlq_messages.py --queue-url https://sqs.us-east-2.amazonaws.com/123456789/dlq-name --delete

  # Download up to 100 messages
  python download_dlq_messages.py --queue-url https://sqs.us-east-2.amazonaws.com/123456789/dlq-name --max-messages 100

  # Specify custom output directory
  python download_dlq_messages.py --queue-url https://sqs.us-east-2.amazonaws.com/123456789/dlq-name --output ./custom_dlq

Environment Variables:
  AWS_REGION          AWS region (default: us-east-2)
  DLQ_QUEUE_URL       SQS DLQ URL (if not provided via --queue-url)
        """,
    )

    parser.add_argument(
        "--queue-url", type=str, default=SQS_QUEUE_URL, help="SQS Dead Letter Queue URL (or set SQS_QUEUE_URL in .env)"
    )
    parser.add_argument("--output", type=str, default="DLQ", help="Output directory to save messages (default: ./DLQ)")
    parser.add_argument("--delete", action="store_true", help="Delete messages from queue after downloading")
    parser.add_argument("--region", type=str, default=AWS_REGION, help="AWS region (default: us-east-2)")
    parser.add_argument(
        "--max-messages", type=int, default=None, help="Maximum number of messages to download (default: all)"
    )

    args = parser.parse_args()

    if not args.queue_url:
        print("Error: --queue-url is required or set SQS_QUEUE_URL in .env")
        parser.print_help()
        sys.exit(1)

    # Resolve output path relative to project root
    if not args.output.startswith("/"):
        project_root = Path(__file__).parent.parent
        output_path = project_root / args.output
    else:
        output_path = Path(args.output)

    print("Downloading DLQ messages...")
    print(f"Queue URL: {args.queue_url}")
    print(f"Output directory: {output_path}")
    print(f"Delete after download: {args.delete}")
    print(f"Region: {args.region}")
    print()

    downloaded = download_dlq_messages(
        queue_url=args.queue_url,
        output_dir=str(output_path),
        delete_after_download=args.delete,
        region=args.region,
        max_messages=args.max_messages,
    )

    print(f"\nMessages saved to: {output_path}")
    if downloaded > 0:
        print(f"Use 'cat {output_path}/*.json' to view messages")
    sys.exit(0)


if __name__ == "__main__":
    main()
