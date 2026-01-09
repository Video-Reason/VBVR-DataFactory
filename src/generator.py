"""Generator execution logic."""

import logging
import os
import subprocess
import sys
from typing import Optional

from src.utils import count_generated_samples

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def detect_output_arg(generator_path: str) -> str:
    """
    Detect which output argument the generator uses (--output-dir or --output).

    Args:
        generator_path: Path to the generator directory

    Returns:
        The output argument name ('--output-dir' or '--output')
    """
    generate_script = os.path.join(generator_path, "examples", "generate.py")
    try:
        result = subprocess.run(
            [sys.executable, generate_script, "--help"],
            cwd=generator_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        help_text = result.stdout + result.stderr
        if "--output-dir" in help_text:
            return "--output-dir"
        elif "--output" in help_text:
            return "--output"
    except Exception as e:
        logger.warning(f"Failed to detect output arg: {e}")
    return "--output-dir"


def run_generator(
    generator_path: str,
    num_samples: int,
    seed: Optional[int],
    output_dir: str,
) -> int:
    """
    Run the generator subprocess once.

    SQS handles retries - if this fails, the message returns to queue.

    Args:
        generator_path: Path to the generator directory
        num_samples: Number of samples to generate
        seed: Random seed (optional)
        output_dir: Output directory path

    Returns:
        Number of samples generated

    Raises:
        subprocess.CalledProcessError: If generator fails
    """
    output_arg = detect_output_arg(generator_path)
    cmd = [sys.executable, "examples/generate.py", "--num-samples", str(num_samples)]

    if seed is not None:
        cmd.extend(["--seed", str(seed)])

    cmd.extend([output_arg, output_dir])

    logger.info(f"Running command: {' '.join(cmd)}")
    logger.info(f"Working directory: {generator_path}")

    result = subprocess.run(cmd, cwd=generator_path, check=True, capture_output=True, text=True)

    logger.info("Generator completed successfully")
    if result.stdout:
        logger.debug(f"Generator stdout (first 500 chars): {result.stdout[:500]}")
    if result.stderr:
        logger.debug(f"Generator stderr (first 500 chars): {result.stderr[:500]}")

    generated = count_generated_samples(output_dir)
    logger.info(f"Generated {generated} samples")

    return generated
