"""SQS client wrapper.

NO try-catch blocks - let boto3 exceptions bubble up.
"""

import boto3

from vmdatawheel.core.config import config


class SQSClient:
    """High-level SQS operations."""

    def __init__(self, queue_url: str | None = None, region: str | None = None):
        self.queue_url = queue_url or config.sqs_queue_url
        self.region = region or config.aws_region
        self.sqs = boto3.client("sqs", region_name=self.region)

    def send_message(self, message_body: str) -> str:
        """
        Send single message to queue.

        Args:
            message_body: JSON string message body

        Returns:
            Message ID

        Raises:
            ClientError: If SQS send fails
        """
        response = self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=message_body,
        )
        return response["MessageId"]

    def send_batch(self, entries: list[dict]) -> tuple[int, int]:
        """
        Send batch of messages (max 10).

        Args:
            entries: List of message entries with 'Id' and 'MessageBody'

        Returns:
            Tuple of (successful_count, failed_count)

        Raises:
            ClientError: If SQS batch send fails
        """
        response = self.sqs.send_message_batch(
            QueueUrl=self.queue_url,
            Entries=entries,
        )

        successful = len(response.get("Successful", []))
        failed = len(response.get("Failed", []))

        return successful, failed

    def get_queue_attributes(self) -> dict:
        """
        Get queue statistics.

        Returns:
            Dictionary with 'available', 'in_flight', 'delayed' message counts

        Raises:
            ClientError: If get attributes fails
        """
        response = self.sqs.get_queue_attributes(
            QueueUrl=self.queue_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
            ],
        )

        attrs = response["Attributes"]
        return {
            "available": int(attrs.get("ApproximateNumberOfMessages", 0)),
            "in_flight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
            "delayed": int(attrs.get("ApproximateNumberOfMessagesDelayed", 0)),
        }

    def purge_queue(self) -> None:
        """
        Purge all messages from queue.

        Raises:
            ClientError: If purge fails
        """
        self.sqs.purge_queue(QueueUrl=self.queue_url)

