"""AWS Lambda handler for generating dataset samples."""

import gc
import json
import logging
import os
import random
import shutil
from pathlib import Path
from typing import Any

from src.config import GENERATORS_PATH, OUTPUT_BUCKET
from src.generator import run_generator
from src.metrics import put_metric, track_duration
from src.uploader import upload_samples
from src.utils import find_task_directories, rename_samples

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for generating dataset samples.

    Expected event format (from SQS):
    {
        "type": "chess-task-data-generator",
        "start_index": 0,
        "num_samples": 100,      // recommended <= 100
        "seed": 42,              // optional, random if not provided
        "output_format": "files" // optional, "files" (default) or "tar"
    }

    Args:
        event: Lambda event (SQS message or direct invocation)
        context: Lambda context

    Returns:
        Result dictionary with status and processed count
    """
    records = event.get("Records", [event])
    results = []

    for record in records:
        try:
            if "body" in record:
                task = json.loads(record["body"])
            else:
                task = record

            result = process_task(task)
            results.append(result)
        except Exception as e:
            logger.error(f"Error processing record: {e}")
            raise

    return {"status": "ok", "processed": len(records), "results": results}


def process_task(task: dict) -> dict:
    """
    Process a single generation task.

    Args:
        task: Task dictionary with type, num_samples, etc.

    Returns:
        Result dictionary with generator name, samples uploaded, and sample IDs
    """
    task_type = task["type"]
    num_samples = task["num_samples"]
    start_index = task.get("start_index", 0)
    seed = task.get("seed")
    output_format = task.get("output_format", "files")

    # Validate output_format
    if output_format not in ("files", "tar"):
        raise ValueError(f"Invalid output_format: {output_format}. Must be 'files' or 'tar'")

    # Generate random seed if not provided
    if seed is None:
        seed = random.randint(1, 2**31 - 1)
        logger.info(f"No seed provided, using random seed: {seed}")

    try:
        with track_duration(task_type):
            result = _process_samples(task_type, num_samples, start_index, seed, output_format)

        # Success metrics
        put_metric("TaskSuccess", 1, "Count", task_type)
        put_metric("SamplesUploaded", len(result["sample_ids"]), "Count", task_type)

        if result.get("tar_file"):
            result["tar_files"] = [result.pop("tar_file")]
        return result

    except Exception as e:
        # Failure metric with exception class name as error type
        error_type = type(e).__name__
        put_metric("TaskFailure", 1, "Count", task_type, error_type=error_type)
        raise


def _process_samples(
    task_type: str,
    num_samples: int,
    start_index: int,
    seed: int,
    output_format: str = "files",
) -> dict:
    """
    Process samples for a generator task.

    Args:
        task_type: Generator type name
        num_samples: Number of samples to generate
        start_index: Starting index for global IDs
        seed: Random seed
        output_format: Output format - "files" (default) or "tar"

    Returns:
        Result dictionary with samples uploaded and sample IDs
    """
    generator_path = os.path.join(GENERATORS_PATH, task_type)
    if not os.path.exists(generator_path):
        raise ValueError(f"Generator not found: {task_type} at {generator_path}")

    output_dir = f"/tmp/output_{task_type}_{os.getpid()}"

    # Run generator (SQS handles retries if this fails)
    run_generator(
        generator_path=generator_path,
        num_samples=num_samples,
        seed=seed,
        output_dir=output_dir,
    )

    output_path = Path(output_dir)
    logger.info(f"Checking output directory: {output_dir}")
    logger.info(f"Output directory exists: {output_path.exists()}")

    # Find task directories
    logger.info(f"Searching for _task directories in: {output_path}")
    questions_dir = find_task_directories(output_path)

    if not questions_dir:
        logger.info(f"Using output_path as fallback: {output_path}")
        questions_dir = output_path

    uploaded_samples = []
    tar_file = None

    if questions_dir and questions_dir.exists():
        logger.info(f"Using questions directory: {questions_dir}")
        found_any = False

        for item in questions_dir.rglob("*"):
            if item.is_dir() and item.name.endswith("_task"):
                domain_task_dir = item
                logger.info(f"Found domain_task directory: {domain_task_dir}")

                renamed_samples = rename_samples(domain_task_dir, start_index)

                if renamed_samples:
                    found_any = True
                    try:
                        batch_uploaded, batch_tar = upload_samples(
                            domain_task_dir=domain_task_dir,
                            renamed_samples=renamed_samples,
                            task_type=task_type,
                            bucket=OUTPUT_BUCKET,
                            start_index=start_index,
                            output_format=output_format,
                        )
                        uploaded_samples.extend(batch_uploaded)
                        if batch_tar:
                            tar_file = batch_tar
                        gc.collect()
                    except Exception as e:
                        logger.error(f"Error uploading samples: {e}")
                        raise

        if not found_any:
            logger.warning(f"No task directories with files found in {questions_dir}")
            raise ValueError(f"No task files found in output directory: {questions_dir}")
    else:
        error_msg = f"Cannot process output: questions_dir={questions_dir}\n"
        error_msg += f"Output directory exists: {output_path.exists()}\n"
        if not output_path.exists():
            error_msg += f"Output directory {output_dir} does not exist.\n"
        error_msg += "This usually means the generator did not produce any output files.\n"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Cleanup
    try:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
            logger.info(f"Cleaned up output directory: {output_dir}")
    except Exception as e:
        logger.warning(f"Failed to clean up {output_dir}: {e}")

    gc.collect()
    logger.info(f"Task complete: uploaded {len(uploaded_samples)} samples")

    result = {
        "generator": task_type,
        "samples_uploaded": len(uploaded_samples),
        "sample_ids": [s["sample_id"] for s in uploaded_samples],
    }
    if tar_file:
        result["tar_file"] = tar_file
    return result
