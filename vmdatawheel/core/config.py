"""Configuration management using Pydantic Settings.

Replaces both src/config.py and scripts/common.py with a single unified config.
NO try-catch blocks - let Pydantic raise ValidationError if required env vars missing.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VMDataWheelConfig(BaseSettings):
    """Global configuration - loads from environment variables or .env file."""

    # Required
    output_bucket: str = Field(..., description="S3 bucket for output data")

    # AWS
    aws_region: str = Field(default="us-east-2", description="AWS region")
    aws_profile: str | None = Field(default=None, description="AWS profile name")

    # Paths
    generators_path: str = Field(default="/opt/generators", description="Path to generators directory")

    # SQS
    sqs_queue_url: str | None = Field(default=None, description="Main SQS queue URL")
    sqs_dlq_url: str | None = Field(default=None, description="Dead letter queue URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Singleton instance
config = VMDataWheelConfig()

