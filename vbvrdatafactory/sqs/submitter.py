"""Task submission to SQS.

NO try-catch blocks - let exceptions bubble up.
"""

import logging

from vbvrdatafactory.core.models import TaskMessage
from vbvrdatafactory.sqs.client import SQSClient

logger = logging.getLogger(__name__)


class TaskSubmitter:
    """Submits generation tasks to SQS."""

    def __init__(self, queue_url: str | None = None):
        self.client = SQSClient(queue_url)

    def create_task_messages(
        self,
        generator: str,
        total_samples: int,
        batch_size: int,
        seed: int,
        output_format: str = "files",
        output_bucket: str | None = None,
    ) -> list[TaskMessage]:
        """
        Create task messages for a generator.

        Args:
            generator: Generator name
            total_samples: Total number of samples to generate
            batch_size: Number of samples per Lambda invocation
            seed: Random seed
            output_format: Output format - "files" or "tar"
            output_bucket: Optional S3 bucket override

        Returns:
            List of TaskMessage objects
        """
        messages = []

        for idx, start in enumerate(range(0, total_samples, batch_size)):
            num_samples = min(batch_size, total_samples - start)
            message_seed = (seed + idx) % (2**31)

            task = TaskMessage(
                type=generator,
                start_index=start,
                num_samples=num_samples,
                seed=message_seed,
                output_format=output_format,
                output_bucket=output_bucket,
            )
            messages.append(task)

        return messages

    def submit_tasks(
        self,
        generators: list[str],
        total_samples: int,
        batch_size: int,
        seed: int,
        output_format: str = "files",
        output_bucket: str | None = None,
    ) -> dict:
        """
        Submit tasks for multiple generators.

        Args:
            generators: List of generator names
            total_samples: Samples per generator
            batch_size: Samples per Lambda task
            seed: Random seed
            output_format: Output format - "files" or "tar"
            output_bucket: Optional S3 bucket override

        Returns:
            Dictionary with submission statistics

        Raises:
            ClientError: If SQS operations fail
        """
        total_successful = 0
        total_failed = 0
        failed_generators = []

        for generator in generators:
            # Create messages with Pydantic validation
            tasks = self.create_task_messages(
                generator, total_samples, batch_size, seed, output_format, output_bucket
            )

            # Convert to SQS format and send in batches of 10
            batches = [tasks[i : i + 10] for i in range(0, len(tasks), 10)]

            gen_successful = 0
            gen_failed = 0

            for batch_idx, batch in enumerate(batches):
                entries = [
                    {
                        "Id": f"{generator}_{batch_idx}_{idx}",
                        "MessageBody": task.model_dump_json(),
                    }
                    for idx, task in enumerate(batch)
                ]

                successful, failed = self.client.send_batch(entries)
                gen_successful += successful
                gen_failed += failed

                logger.info(
                    f"Generator {generator} batch {batch_idx + 1}/{len(batches)}: "
                    f"{successful} sent, {failed} failed"
                )

            total_successful += gen_successful
            total_failed += gen_failed

            if gen_failed > 0:
                failed_generators.append(generator)

        return {
            "total_successful": total_successful,
            "total_failed": total_failed,
            "total_generators": len(generators),
            "failed_generators": failed_generators,
        }

