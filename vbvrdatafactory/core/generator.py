"""Generator execution logic.

NO try-catch blocks - let exceptions bubble up for Lambda/SQS to handle retries.
"""

import logging
import subprocess
import sys
from pathlib import Path

from vbvrdatafactory.core.models import TaskMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class GeneratorRunner:
    """Executes generator scripts."""

    def __init__(self, generators_path: str):
        self.generators_path = Path(generators_path)

    def detect_output_arg(self, generator_path: Path) -> str:
        """
        Detect which output argument the generator uses (--output-dir or --output).

        Args:
            generator_path: Path to the generator directory

        Returns:
            The output argument name ('--output-dir' or '--output')

        Raises:
            subprocess.TimeoutExpired: If help command times out
            subprocess.CalledProcessError: If help command fails
        """
        generate_script = generator_path / "examples" / "generate.py"
        env = {"PYTHONPATH": str(generator_path.absolute())}

        result = subprocess.run(
            [sys.executable, str(generate_script), "--help"],
            cwd=generator_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        help_text = result.stdout + result.stderr
        if "--output-dir" in help_text:
            return "--output-dir"
        elif "--output" in help_text:
            return "--output"
        return "--output-dir"

    def run(self, task: TaskMessage, output_dir: Path) -> int:
        """
        Run generator subprocess.

        Args:
            task: Task message with generator info
            output_dir: Directory for output files

        Returns:
            Number of samples generated

        Raises:
            FileNotFoundError: If generator not found
            subprocess.CalledProcessError: If generator fails
        """
        generator_path = self.generators_path / task.type

        if not generator_path.exists():
            raise FileNotFoundError(f"Generator not found: {generator_path}")

        output_arg = self.detect_output_arg(generator_path)

        cmd = [
            sys.executable,
            "examples/generate.py",
            "--num-samples",
            str(task.num_samples),
        ]

        if task.seed is not None:
            cmd.extend(["--seed", str(task.seed)])

        cmd.extend([output_arg, str(output_dir)])

        logger.info(f"Running command: {' '.join(cmd)}")
        logger.info(f"Working directory: {generator_path}")

        env = {"PYTHONPATH": str(generator_path.absolute())}

        result = subprocess.run(
            cmd,
            cwd=generator_path,
            env=env,
            check=True,  # Raises CalledProcessError on failure
            capture_output=True,
            text=True,
        )

        logger.info("Generator completed successfully")
        if result.stdout:
            logger.debug(f"Generator stdout (first 500 chars): {result.stdout[:500]}")
        if result.stderr:
            logger.debug(f"Generator stderr (first 500 chars): {result.stderr[:500]}")

        generated = self._count_samples(output_dir)
        logger.info(f"Generated {generated} samples")

        return generated

    def _count_samples(self, output_dir: Path) -> int:
        """Count successfully generated samples in output directory."""
        count = 0
        for task_dir in output_dir.rglob("*_task"):
            if task_dir.is_dir():
                for sample_dir in task_dir.iterdir():
                    if sample_dir.is_dir():
                        has_files = (
                            any(sample_dir.glob("*.png"))
                            or any(sample_dir.glob("*.txt"))
                            or any(sample_dir.glob("*.mp4"))
                        )
                        if has_files:
                            count += 1
        return count

