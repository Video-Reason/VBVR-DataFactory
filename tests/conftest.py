"""Shared pytest fixtures."""

import os
import tempfile
from pathlib import Path

import pytest

# Set required environment variables before importing src modules
os.environ.setdefault("OUTPUT_BUCKET", "test-bucket")
os.environ.setdefault("AWS_REGION", "us-east-2")


@pytest.fixture
def tmp_output_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_task_dir(tmp_output_dir):
    """Create a sample task directory structure with test files."""
    task_dir = tmp_output_dir / "test_task"
    task_dir.mkdir()

    # Create sample directories with files
    for i in range(3):
        sample_dir = task_dir / f"sample_{i:04d}"
        sample_dir.mkdir()
        (sample_dir / "image.png").write_bytes(b"fake png content")
        (sample_dir / "data.txt").write_text("test data")

    return task_dir


@pytest.fixture
def empty_task_dir(tmp_output_dir):
    """Create an empty task directory structure."""
    task_dir = tmp_output_dir / "empty_task"
    task_dir.mkdir()

    # Create empty sample directories
    for i in range(2):
        sample_dir = task_dir / f"sample_{i:04d}"
        sample_dir.mkdir()

    return task_dir


@pytest.fixture
def mock_generator_path(tmp_output_dir):
    """Create a mock generator directory with generate.py script."""
    generator_path = tmp_output_dir / "test-generator"
    examples_dir = generator_path / "examples"
    examples_dir.mkdir(parents=True)

    # Create a mock generate.py script that shows --output-dir in help
    generate_script = examples_dir / "generate.py"
    generate_script.write_text(
        '''#!/usr/bin/env python3
"""Mock generator script."""
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-samples", type=int, default=1)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output-dir", type=str)
    args = parser.parse_args()
    print(f"Generating {args.num_samples} samples")

if __name__ == "__main__":
    main()
'''
    )

    return generator_path


@pytest.fixture
def mock_s3(mocker):
    """Mock boto3 S3 client."""
    mock_client = mocker.MagicMock()
    mocker.patch("src.uploader.s3", mock_client)
    return mock_client


@pytest.fixture(autouse=True)
def reset_env():
    """Reset environment variables after each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)
