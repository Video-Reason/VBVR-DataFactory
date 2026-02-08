"""VBVR-DataFactory - Distributed data generation system for AWS Lambda."""

__version__ = "1.0.0"

from vbvrdatafactory.core.config import config
from vbvrdatafactory.core.models import TaskMessage, TaskResult, ValidationResult

__all__ = ["config", "TaskMessage", "TaskResult", "ValidationResult", "__version__"]

