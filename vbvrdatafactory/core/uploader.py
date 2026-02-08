"""S3 upload operations.

NO try-catch blocks - let boto3 exceptions bubble up for Lambda/SQS to handle retries.
"""

import logging
import tarfile
from pathlib import Path

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class S3Uploader:
    """Handles S3 uploads."""

    def __init__(self, bucket: str, region: str):
        self.bucket = bucket
        self.s3 = boto3.client("s3", region_name=region)

    def upload_directory(self, local_dir: Path, s3_prefix: str) -> int:
        """
        Upload all files in a directory to S3, deleting each file after successful upload.

        Args:
            local_dir: Path to local directory
            s3_prefix: S3 key prefix (e.g., "questions/G-1_generator/task_name_task/task_name_0000/")

        Returns:
            Number of files uploaded

        Raises:
            ClientError: If S3 upload fails
        """
        upload_count = 0
        files_to_delete = []

        for file_path in local_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_dir)
                s3_key = s3_prefix + str(relative_path).replace("\\", "/")

                # This will raise ClientError if it fails
                self.s3.upload_file(str(file_path), self.bucket, s3_key)
                upload_count += 1
                logger.info(f"Uploaded: s3://{self.bucket}/{s3_key}")
                files_to_delete.append(file_path)

        # Delete files after successful upload
        for file_path in files_to_delete:
            file_path.unlink()
            logger.debug(f"Deleted local file: {file_path}")

        return upload_count

    def create_and_upload_tar(
        self,
        source_dir: Path,
        tar_filename: str,
        s3_key: str,
        task_type: str,
        task_folder: str,
    ) -> str:
        """
        Create a tar.gz archive from a directory with proper internal structure and upload to S3.

        Args:
            source_dir: Path to the source directory to archive
            tar_filename: Name for the tar.gz file
            s3_key: S3 key (full path including filename)
            task_type: Generator type name (e.g., "G-1_object_trajectory_data-generator")
            task_folder: Task folder name (e.g., "object_trajectory_task")

        Returns:
            S3 URI of the uploaded file

        Raises:
            ClientError: If S3 upload fails
        """
        tar_path = Path(f"/tmp/{tar_filename}")

        # Create tar archive with proper directory structure
        # Structure inside tar: {generator}/{task}_task/{samples}/
        with tarfile.open(tar_path, "w:gz") as tar:
            for item in source_dir.iterdir():
                if item.is_dir():
                    # Add with full path structure
                    arcname = f"{task_type}/{task_folder}/{item.name}"
                    tar.add(str(item), arcname=arcname)

        logger.info(f"Created tar archive: {tar_path}")

        # Upload to S3
        self.s3.upload_file(str(tar_path), self.bucket, s3_key)
        s3_uri = f"s3://{self.bucket}/{s3_key}"
        logger.info(f"Uploaded tar to: {s3_uri}")

        # Delete local tar file
        tar_path.unlink()
        logger.debug(f"Deleted local tar file: {tar_path}")

        return s3_uri

    def upload_samples(
        self,
        domain_task_dir: Path,
        renamed_samples: list[str],
        task_type: str,
        start_index: int,
        output_format: str = "files",
    ) -> tuple[list[dict], str | None]:
        """
        Upload renamed samples to S3, either as individual files or as a tar archive.

        New structure: questions/{generator-name}/{task-name}_task/{task-name}_0000/files

        Args:
            domain_task_dir: Path to the domain task directory (e.g., object_trajectory_task)
            renamed_samples: List of sample IDs to upload (e.g., ["object_trajectory_0000"])
            task_type: Generator type name (e.g., "G-1_object_trajectory_data-generator")
            start_index: Starting index for samples
            output_format: Output format - "files" (default) or "tar"

        Returns:
            Tuple of (list of upload results, tar filename or None)

        Raises:
            ClientError: If S3 upload fails
        """
        uploaded_samples = []
        tar_file = None

        # Extract task folder name (e.g., "object_trajectory_task")
        task_folder = domain_task_dir.name

        if output_format == "tar":
            # Create one tar file per batch with proper internal structure
            end_index = start_index + len(renamed_samples) - 1
            tar_filename = f"{task_type}_{start_index:05d}-{end_index:05d}.tar.gz"
            s3_key = f"questions/{tar_filename}"

            self.create_and_upload_tar(
                domain_task_dir,
                tar_filename,
                s3_key,
                task_type,
                task_folder
            )

            for sample_id in renamed_samples:
                uploaded_samples.append({"sample_id": sample_id, "files_uploaded": 0})

            logger.info(f"Created and uploaded tar with {len(renamed_samples)} samples to questions/{tar_filename}")
            tar_file = tar_filename
        else:
            for sample_id in renamed_samples:
                sample_dir = domain_task_dir / sample_id
                if sample_dir.exists():
                    s3_prefix = f"questions/{task_type}/{task_folder}/{sample_id}/"
                    files_uploaded = self.upload_directory(sample_dir, s3_prefix)
                    uploaded_samples.append({"sample_id": sample_id, "files_uploaded": files_uploaded})
                    logger.info(f"Uploaded sample {sample_id}: {files_uploaded} files")

            logger.info(f"Uploaded {len(renamed_samples)} samples directly to questions/{task_type}/{task_folder}/")

        return uploaded_samples, tar_file

