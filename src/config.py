"""Configuration from environment variables.

For local development, create a .env file based on .env.example:
    cp .env.example .env
    # Edit .env with your values
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if it exists (for local development)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


def get_required_env(name: str) -> str:
    """Get required environment variable or raise error with helpful message."""
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set.\n"
            f"For local development, copy .env.example to .env and fill in the values:\n"
            f"    cp .env.example .env"
        )
    return value


# Required - must be set by CDK, Console, or .env file
OUTPUT_BUCKET = get_required_env("OUTPUT_BUCKET")

# Optional with defaults
AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")
GENERATORS_PATH = os.environ.get("GENERATORS_PATH", "/opt/generators")
