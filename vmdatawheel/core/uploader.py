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
            s3_prefix: S3 key prefix (e.g., "data/v1/generator_name/sample_id/")

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
    ) -> str:
        """
        Create a tar.gz archive from a directory and upload to S3.

        Args:
            source_dir: Path to the source directory to archive
            tar_filename: Name for the tar.gz file
            s3_key: S3 key (full path including filename)

        Returns:
            S3 URI of the uploaded file

        Raises:
            ClientError: If S3 upload fails
        """
        tar_path = Path(f"/tmp/{tar_filename}")

        # Create tar archive
        with tarfile.open(tar_path, "w:gz") as tar:
            for item in source_dir.iterdir():
                tar.add(str(item), arcname=item.name)

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

        Args:
            domain_task_dir: Path to the domain task directory
            renamed_samples: List of sample IDs to upload
            task_type: Generator type name
            start_index: Starting index for samples
            output_format: Output format - "files" (default) or "tar"

        Returns:
            Tuple of (list of upload results, tar filename or None)

        Raises:
            ClientError: If S3 upload fails
        """
        uploaded_samples = []
        tar_file = None

        if output_format == "tar":
            end_index = start_index + len(renamed_samples) - 1
            tar_filename = f"{task_type}_{start_index}_{end_index}.tar.gz"
            s3_key = f"data/v1/{task_type}/{tar_filename}"

            self.create_and_upload_tar(domain_task_dir, tar_filename, s3_key)

            for sample_id in renamed_samples:
                uploaded_samples.append({"sample_id": sample_id, "files_uploaded": 0})

            logger.info(f"Created and uploaded tar with {len(renamed_samples)} samples")
            tar_file = tar_filename
        else:
            for sample_id in renamed_samples:
                sample_dir = domain_task_dir / sample_id
                if sample_dir.exists():
                    s3_prefix = f"data/v1/{task_type}/{sample_id}/"
                    files_uploaded = self.upload_directory(sample_dir, s3_prefix)
                    uploaded_samples.append({"sample_id": sample_id, "files_uploaded": files_uploaded})
                    logger.info(f"Uploaded sample {sample_id}: {files_uploaded} files")

            logger.info(f"Uploaded {len(renamed_samples)} samples directly")

        return uploaded_samples, tar_file

