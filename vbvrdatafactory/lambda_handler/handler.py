"""AWS Lambda handler.

NO try-catch blocks - let Lambda/SQS handle retries on failure.
Pydantic validates messages automatically - invalid messages go to DLQ.
"""

import gc
import logging
import os
import random
import shutil
from pathlib import Path

from vbvrdatafactory.core.config import config
from vbvrdatafactory.core.generator import GeneratorRunner
from vbvrdatafactory.core.metrics import MetricsClient
from vbvrdatafactory.core.models import TaskMessage, TaskResult
from vbvrdatafactory.core.uploader import S3Uploader
from vbvrdatafactory.core.validator import find_task_directories, rename_samples

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context) -> dict:
    """
    Lambda entry point.

    Pydantic validates automatically - invalid messages raise ValidationError → DLQ.

    Args:
        event: Lambda event (SQS message or direct invocation)
        context: Lambda context

    Returns:
        Result dictionary with status and processed count

    Raises:
        ValidationError: If message is invalid (goes to DLQ)
        Any other exception: Lambda will retry, then DLQ
    """
    records = event.get("Records", [event])
    results = []

    for record in records:
        # Parse with Pydantic - raises ValidationError if invalid
        if "body" in record:
            task = TaskMessage.model_validate_json(record["body"])
        else:
            task = TaskMessage.model_validate(record)

        result = process_task(task)
        results.append(result.model_dump())

    return {"status": "ok", "processed": len(records), "results": results}


def process_task(task: TaskMessage) -> TaskResult:
    """
    Process a single generation task.

    No try-catch - let exceptions bubble up for Lambda/SQS retry mechanism.

    Args:
        task: Task message (Pydantic validated)

    Returns:
        TaskResult with upload information

    Raises:
        Various exceptions that trigger Lambda retry → DLQ after max retries
    """
    # Generate random seed if not provided
    if task.seed is None:
        task.seed = random.randint(1, 2**31 - 1)
        logger.info(f"No seed provided, using random seed: {task.seed}")

    metrics = MetricsClient()

    # Track duration and execute
    with metrics.track_duration(task.type):
        result = _process_samples(task)

    # Success metrics (only reached if no exception)
    metrics.put_metric("TaskSuccess", 1, "Count", task.type)
    metrics.put_metric("SamplesUploaded", len(result.sample_ids), "Count", task.type)

    return result


def _process_samples(task: TaskMessage) -> TaskResult:
    """
    Process samples for a generator task.

    Args:
        task: Task message

    Returns:
        TaskResult with upload information

    Raises:
        FileNotFoundError: If generator not found
        ValueError: If no task files found
        CalledProcessError: If generator fails
        ClientError: If S3 upload fails
        OSError: If file operations fail
    """
    output_bucket = task.output_bucket or config.output_bucket
    output_dir = Path(f"/tmp/output_{task.type}_{os.getpid()}")

    # 1. Run generator (raises on failure)
    runner = GeneratorRunner(config.generators_path)
    runner.run(task, output_dir)

    # 2. Find task directories
    logger.info(f"Checking output directory: {output_dir}")
    questions_dir = find_task_directories(output_dir)

    if not questions_dir:
        error_msg = f"No task files found in output directory: {output_dir}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"Using questions directory: {questions_dir}")

    # 3. Rename and upload samples
    uploader = S3Uploader(output_bucket, config.aws_region)
    uploaded_samples = []
    tar_files = []

    found_any = False

    for item in questions_dir.rglob("*"):
        if item.is_dir() and item.name.endswith("_task"):
            domain_task_dir = item
            logger.info(f"Found domain_task directory: {domain_task_dir}")

            renamed = rename_samples(domain_task_dir, task.start_index)

            if renamed:
                found_any = True

                batch_uploaded, batch_tar = uploader.upload_samples(
                    domain_task_dir=domain_task_dir,
                    renamed_samples=renamed,
                    task_type=task.type,
                    start_index=task.start_index,
                    output_format=task.output_format,
                )

                uploaded_samples.extend(batch_uploaded)
                if batch_tar:
                    tar_files.append(batch_tar)

                gc.collect()

    if not found_any:
        error_msg = f"No task directories with files found in {questions_dir}"
        logger.warning(error_msg)
        raise ValueError(error_msg)

    # 4. Cleanup
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)
        logger.info(f"Cleaned up output directory: {output_dir}")

    gc.collect()
    logger.info(f"Task complete: uploaded {len(uploaded_samples)} samples")

    return TaskResult(
        generator=task.type,
        samples_uploaded=len(uploaded_samples),
        sample_ids=[s["sample_id"] for s in uploaded_samples],
        tar_files=tar_files,
    )

