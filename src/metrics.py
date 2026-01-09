"""CloudWatch metrics for pipeline monitoring."""

import logging
import time
from contextlib import contextmanager
from typing import Optional

import boto3

logger = logging.getLogger(__name__)

cloudwatch = boto3.client("cloudwatch")
NAMESPACE = "VMDatasetPipeline"


def put_metric(
    name: str,
    value: float,
    unit: str,
    generator_type: str,
    error_type: Optional[str] = None,
) -> None:
    """
    Send a metric to CloudWatch.

    Args:
        name: Metric name (e.g., TaskSuccess, TaskFailure, SamplesUploaded)
        value: Metric value
        unit: Unit type (Count, Milliseconds, etc.)
        generator_type: Generator type dimension
        error_type: Optional error type dimension (for failures)
    """
    dimensions = [{"Name": "GeneratorType", "Value": generator_type}]
    if error_type:
        dimensions.append({"Name": "ErrorType", "Value": error_type})

    try:
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    "MetricName": name,
                    "Value": value,
                    "Unit": unit,
                    "Dimensions": dimensions,
                }
            ],
        )
    except Exception as e:
        logger.warning(f"Failed to put metric {name}: {e}")


@contextmanager
def track_duration(generator_type: str):
    """
    Context manager to track task duration.

    Args:
        generator_type: Generator type for the dimension

    Yields:
        None

    Example:
        with track_duration("chess-task-data-generator"):
            # do work
            pass
    """
    start = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start) * 1000
        put_metric("TaskDuration", duration_ms, "Milliseconds", generator_type)
