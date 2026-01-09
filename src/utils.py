"""Utility functions for file and directory operations."""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def count_generated_samples(output_dir: str) -> int:
    """
    Count successfully generated samples in output directory.

    Args:
        output_dir: Path to the output directory

    Returns:
        Number of samples with actual task files
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        return 0

    count = 0
    for task_dir in output_path.rglob("*_task"):
        if task_dir.is_dir():
            for sample_dir in task_dir.iterdir():
                if sample_dir.is_dir():
                    has_files = (
                        any(sample_dir.glob("*.png")) or any(sample_dir.glob("*.txt")) or any(sample_dir.glob("*.mp4"))
                    )
                    if has_files:
                        count += 1
    return count


def find_task_directories(output_path: Path) -> Optional[Path]:
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
    """
    renamed_samples = []

    try:
        task_dirs = list(domain_task_dir.iterdir())
    except Exception as e:
        logger.error(f"Error listing task dirs in {domain_task_dir}: {e}")
        return renamed_samples

    def get_sort_key(path: Path):
        name = path.name
        try:
            numbers = re.findall(r"\d+", name)
            if numbers:
                return int(numbers[-1])
        except Exception:
            pass
        return name

    task_dirs.sort(key=get_sort_key)

    local_index = 0
    for task_id_dir in task_dirs:
        if not task_id_dir.is_dir():
            continue

        original_task_id = task_id_dir.name

        # Check if directory has task files
        has_files = False
        try:
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
        except Exception as e:
            logger.error(f"Error checking files in {task_id_dir}: {e}")
            continue

        if not has_files:
            logger.debug(f"Skipping empty directory: {task_id_dir}")
            try:
                task_id_dir.rmdir()
            except Exception:
                pass
            continue

        global_task_id_int = start_index + local_index
        sample_id = f"{global_task_id_int:05d}"

        logger.debug(f"Mapping local task {original_task_id} to global ID {sample_id} (start_index={start_index})")

        new_dir = task_id_dir.parent / sample_id
        try:
            task_id_dir.rename(new_dir)
            renamed_samples.append(sample_id)
            local_index += 1
            logger.debug(f"Renamed {original_task_id} to {sample_id}")
        except Exception as e:
            logger.error(f"Error renaming {task_id_dir} to {new_dir}: {e}")
            raise

    return renamed_samples
