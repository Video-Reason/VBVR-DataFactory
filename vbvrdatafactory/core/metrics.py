"""CloudWatch metrics for pipeline monitoring.

NO try-catch blocks - let boto3 exceptions bubble up.
"""

import logging
import time
from contextlib import contextmanager

import boto3

logger = logging.getLogger(__name__)


class MetricsClient:
    """CloudWatch metrics client."""

    def __init__(self, namespace: str = "VBVRDataFactoryPipeline"):
        self.namespace = namespace
        self.cloudwatch = boto3.client("cloudwatch")

    def put_metric(
        self,
        name: str,
        value: float,
        unit: str,
        generator_type: str,
        error_type: str | None = None,
    ) -> None:
        """
        Send a metric to CloudWatch.

        Args:
            name: Metric name (e.g., TaskSuccess, TaskFailure, SamplesUploaded)
            value: Metric value
            unit: Unit type (Count, Milliseconds, etc.)
            generator_type: Generator type dimension
            error_type: Optional error type dimension (for failures)

        Raises:
            ClientError: If CloudWatch API call fails
        """
        dimensions = [{"Name": "GeneratorType", "Value": generator_type}]
        if error_type:
            dimensions.append({"Name": "ErrorType", "Value": error_type})

        self.cloudwatch.put_metric_data(
            Namespace=self.namespace,
            MetricData=[
                {
                    "MetricName": name,
                    "Value": value,
                    "Unit": unit,
                    "Dimensions": dimensions,
                }
            ],
        )

    @contextmanager
    def track_duration(self, generator_type: str):
        """
        Context manager to track task duration.

        Args:
            generator_type: Generator type for the dimension

        Yields:
            None

        Example:
            with metrics.track_duration("chess-task-data-generator"):
                # do work
                pass
        """
        start = time.time()
        yield
        duration_ms = (time.time() - start) * 1000
        self.put_metric("TaskDuration", duration_ms, "Milliseconds", generator_type)

