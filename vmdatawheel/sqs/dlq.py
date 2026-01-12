"""Dead Letter Queue operations.

NO try-catch blocks - let exceptions bubble up.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from vmdatawheel.sqs.client import SQSClient

logger = logging.getLogger(__name__)


class DLQManager:
    """Manage DLQ messages."""

    def __init__(self, dlq_url: str):
        self.client = SQSClient(dlq_url)

    def download_messages(
        self,
        output_dir: Path,
        delete_after: bool = False,
        max_messages: int | None = None,
    ) -> int:
        """
        Download all messages from DLQ.

        Args:
            output_dir: Directory to save messages
            delete_after: If True, delete messages from queue after downloading
            max_messages: Maximum number of messages to download (None for all)

        Returns:
            Number of messages downloaded

        Raises:
            ClientError: If SQS operations fail
            OSError: If file operations fail
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded = 0

        while max_messages is None or downloaded < max_messages:
            response = self.client.sqs.receive_message(
                QueueUrl=self.client.queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=1,
                AttributeNames=["All"],
            )

            messages = response.get("Messages", [])
            if not messages:
                break

            for msg in messages:
                message_id = msg.get("MessageId", f"msg_{downloaded}")
                receipt_handle = msg["ReceiptHandle"]
                body = msg.get("Body", "")

                # Parse body as JSON if possible
                if body.startswith("{"):
                    body_json = json.loads(body)
                else:
                    body_json = {"raw_body": body}

                # Save to file
                message_data = {
                    "message_id": message_id,
                    "receipt_handle": receipt_handle,
                    "timestamp": msg.get("Attributes", {}).get("SentTimestamp", ""),
                    "receive_count": msg.get("Attributes", {}).get("ApproximateReceiveCount", ""),
                    "attributes": msg.get("Attributes", {}),
                    "body": body_json,
                }

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{message_id}.json"
                filepath = output_dir / filename

                filepath.write_text(json.dumps(message_data, indent=2))
                downloaded += 1

                logger.info(f"Downloaded message {downloaded}: {message_id}")

                if delete_after:
                    self.client.sqs.delete_message(
                        QueueUrl=self.client.queue_url,
                        ReceiptHandle=receipt_handle,
                    )

        logger.info(f"Total messages downloaded: {downloaded}")
        return downloaded

    def resubmit_messages(
        self,
        dlq_dir: Path,
        target_queue_url: str,
    ) -> dict:
        """
        Resubmit DLQ messages to target queue.

        Args:
            dlq_dir: Directory containing DLQ message JSON files
            target_queue_url: Target SQS queue URL to send messages to

        Returns:
            Dictionary with submission statistics

        Raises:
            ClientError: If SQS operations fail
            OSError: If file operations fail
            JSONDecodeError: If message files are invalid
        """
        target_client = SQSClient(target_queue_url)

        # Load all JSON files
        json_files = [f for f in dlq_dir.glob("*.json") if not f.name.endswith((".bak", ".original"))]

        messages = []
        skipped = 0

        for json_file in json_files:
            data = json.loads(json_file.read_text())
            body = data.get("body")

            if body and isinstance(body, dict) and "type" in body:
                messages.append(body)
            else:
                logger.warning(f"Skipping invalid message file: {json_file.name}")
                skipped += 1

        logger.info(f"Loaded {len(messages)} valid messages from {len(json_files)} files ({skipped} skipped)")

        # Send in batches of 10
        total_successful = 0
        total_failed = 0

        for i in range(0, len(messages), 10):
            batch = messages[i : i + 10]
            entries = [{"Id": str(idx), "MessageBody": json.dumps(msg)} for idx, msg in enumerate(batch)]

            successful, failed = target_client.send_batch(entries)
            total_successful += successful
            total_failed += failed

            logger.info(f"Batch {i // 10 + 1}: {successful} sent, {failed} failed")

        return {
            "total_successful": total_successful,
            "total_failed": total_failed,
            "total_messages": len(messages),
            "skipped": skipped,
        }

