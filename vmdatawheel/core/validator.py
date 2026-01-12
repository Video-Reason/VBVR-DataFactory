"""Output validation logic.

NO try-catch blocks - let exceptions bubble up.
"""

import logging
import re
from pathlib import Path

from vmdatawheel.core.models import ValidationResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SampleValidator:
    """Validates generator output."""

    REQUIRED_FILES = {"first_frame.png", "prompt.txt"}
    OPTIONAL_FILES = {"final_frame.png", "ground_truth.mp4"}
    ALL_VALID_FILES = REQUIRED_FILES | OPTIONAL_FILES

    def validate_sample(self, sample_dir: Path) -> ValidationResult:
        """Validate a single sample directory."""
        files = {f.name for f in sample_dir.iterdir() if f.is_file()}

        missing_required = [f for f in self.REQUIRED_FILES if f not in files]
        extra_files = [f for f in files if f not in self.ALL_VALID_FILES]

        file_sizes = {f.name: f.stat().st_size for f in sample_dir.iterdir() if f.is_file()}

        return ValidationResult(
            sample_id=sample_dir.name,
            valid=len(missing_required) == 0,
            missing_required=missing_required,
            extra_files=extra_files,
            file_sizes=file_sizes,
        )


def find_task_directories(output_path: Path) -> Path | None:
    """
    Find the base directory containing *_task directories.

    Args:
        output_path: Path to search in

    Returns:
        Path to the base directory, or None if not found
    """
    if not output_path.exists():
        return None

    # Look for _task directories
    for item in output_path.rglob("*_task"):
        if item.is_dir():
            logger.info(f"Found _task directory at: {item}")
            return item.parent

    # Fallback: search by task files
    logger.debug(f"Searching for task files (png/txt/mp4) in: {output_path}")
    checked = 0
    max_checks = 100
    for item in output_path.rglob("*"):
        if checked >= max_checks:
            break
        checked += 1
        if item.is_file() and item.suffix in [".png", ".txt", ".mp4"]:
            current = item.parent
            while current != output_path.parent and current != output_path:
                if current.name.endswith("_task"):
                    logger.info(f"Found _task via file {item}, using base: {current.parent}")
                    return current.parent
                current = current.parent

    return None


def rename_samples(domain_task_dir: Path, start_index: int) -> list[str]:
    """
    Rename sample directories to global zero-padded IDs.

    Args:
        domain_task_dir: Path to the domain task directory
        start_index: Starting index for global IDs

    Returns:
        List of renamed sample IDs

    Raises:
        OSError: If rename operation fails
    """
    renamed_samples = []

    task_dirs = list(domain_task_dir.iterdir())

    def get_sort_key(path: Path):
        name = path.name
        numbers = re.findall(r"\d+", name)
        if numbers:
            return int(numbers[-1])
        return name

    task_dirs.sort(key=get_sort_key)

    local_index = 0
    for task_id_dir in task_dirs:
        if not task_id_dir.is_dir():
            continue

        original_task_id = task_id_dir.name

        # Check if directory has task files
        has_files = False
        for _ in task_id_dir.glob("*.png"):
            has_files = True
            break
        if not has_files:
            for _ in task_id_dir.glob("*.txt"):
                has_files = True
                break
        if not has_files:
            for _ in task_id_dir.glob("*.mp4"):
                has_files = True
                break

        if not has_files:
            logger.debug(f"Skipping empty directory: {task_id_dir}")
            task_id_dir.rmdir()
            continue

        global_task_id_int = start_index + local_index
        sample_id = f"{global_task_id_int:05d}"

        logger.debug(f"Mapping local task {original_task_id} to global ID {sample_id} (start_index={start_index})")

        new_dir = task_id_dir.parent / sample_id
        task_id_dir.rename(new_dir)  # This will raise OSError if it fails
        renamed_samples.append(sample_id)
        local_index += 1
        logger.debug(f"Renamed {original_task_id} to {sample_id}")

    return renamed_samples

