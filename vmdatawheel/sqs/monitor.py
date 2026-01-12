"""Queue monitoring.

NO try-catch blocks - let exceptions bubble up.
"""

from vmdatawheel.core.config import config
from vmdatawheel.sqs.client import SQSClient


class QueueMonitor:
    """Monitor queue status."""

    def __init__(self, queue_url: str | None = None, dlq_url: str | None = None):
        self.main_queue = SQSClient(queue_url or config.sqs_queue_url)
        self.dlq = SQSClient(dlq_url or config.sqs_dlq_url) if (dlq_url or config.sqs_dlq_url) else None

    def get_status(self) -> dict:
        """
        Get current queue status.

        Returns:
            Dictionary with main_queue and dlq statistics

        Raises:
            ClientError: If get attributes fails
        """
        main_stats = self.main_queue.get_queue_attributes()

        result = {
            "main_queue": main_stats,
            "dlq": None,
        }

        if self.dlq:
            result["dlq"] = self.dlq.get_queue_attributes()

        return result

