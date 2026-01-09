"""Common utilities for scripts."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent.parent
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment from {env_path}")


def get_env(name: str, default: str = None, required: bool = False) -> str:
    """Get environment variable with optional default and required check."""
    value = os.environ.get(name, default)
    if required and not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set.\n" f"Set it via .env file or export {name}=..."
        )
    return value


# Common environment variables
AWS_REGION = get_env("AWS_REGION", "us-east-2")
AWS_PROFILE = get_env("AWS_PROFILE")
SQS_QUEUE_URL = get_env("SQS_QUEUE_URL")
SQS_DLQ_URL = get_env("SQS_DLQ_URL")
OUTPUT_BUCKET = get_env("OUTPUT_BUCKET")
GENERATORS_PATH = get_env("GENERATORS_PATH", str(PROJECT_ROOT / "generators"))
