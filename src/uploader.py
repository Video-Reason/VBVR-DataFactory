"""S3 upload functions for direct files and tar archives."""

import logging
import os
import tarfile
from pathlib import Path

import boto3

from src.config import AWS_REGION

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize S3 client
s3 = boto3.client("s3", region_name=AWS_REGION)


def upload_directory_to_s3(local_dir: str, bucket: str, s3_prefix: str) -> int:
    """
    Upload all files in a directory to S3, deleting each file after successful upload.

    Args:
        local_dir: Path to local directory
        bucket: S3 bucket name
        s3_prefix: S3 key prefix (e.g., "data/v1/generator_name/sample_id/")

    Returns:
        Number of files uploaded
    """
    local_path = Path(local_dir)
    upload_count = 0
    files_to_delete = []

    for file_path in local_path.rglob("*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(local_path)
            s3_key = s3_prefix + str(relative_path).replace("\\", "/")

            try:
                s3.upload_file(str(file_path), bucket, s3_key)
                upload_count += 1
                logger.info(f"Uploaded: s3://{bucket}/{s3_key}")
                files_to_delete.append(file_path)
            except Exception as e:
                logger.error(f"Error uploading {file_path} to s3://{bucket}/{s3_key}: {e}")
                raise

    for file_path in files_to_delete:
        try:
            file_path.unlink()
            logger.debug(f"Deleted local file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete {file_path}: {e}")

    return upload_count


def create_tar_archive(source_dir: str, tar_path: str) -> str:
    """
    Create a tar.gz archive from a directory.

    Args:
        source_dir: Path to the source directory to archive
        tar_path: Path where the tar.gz file will be created

    Returns:
        Path to the created tar.gz file
    """
    source_path = Path(source_dir)
    with tarfile.open(tar_path, "w:gz") as tar:
        for item in source_path.iterdir():
            tar.add(str(item), arcname=item.name)
    logger.info(f"Created tar archive: {tar_path}")
    return tar_path


def upload_tar_to_s3(tar_path: str, bucket: str, s3_key: str) -> str:
    """
    Upload a tar file to S3 and delete the local file after successful upload.

    Args:
        tar_path: Path to the local tar file
        bucket: S3 bucket name
        s3_key: S3 key (full path including filename)

    Returns:
        S3 URI of the uploaded file
    """
    s3.upload_file(str(tar_path), bucket, s3_key)
    s3_uri = f"s3://{bucket}/{s3_key}"
    logger.info(f"Uploaded tar to: {s3_uri}")

    try:
        os.remove(tar_path)
        logger.debug(f"Deleted local tar file: {tar_path}")
    except Exception as e:
        logger.warning(f"Failed to delete local tar file {tar_path}: {e}")

    return s3_uri


def upload_samples(
    domain_task_dir: Path,
    renamed_samples: list[str],
    task_type: str,
    bucket: str,
    start_index: int,
    output_format: str = "files",
) -> tuple[list[dict], str | None]:
    """
    Upload renamed samples to S3, either as individual files or as a tar archive.

    Args:
        domain_task_dir: Path to the domain task directory
        renamed_samples: List of sample IDs to upload
        task_type: Generator type name
        bucket: S3 bucket name
        start_index: Starting index for samples
        output_format: Output format - "files" (default) or "tar"

    Returns:
        Tuple of (list of upload results, tar filename or None)
    """
    uploaded_samples = []
    tar_file = None

    if output_format == "tar":
        end_index = start_index + len(renamed_samples) - 1
        tar_filename = f"{task_type}_{start_index}_{end_index}.tar.gz"
        tar_path = f"/tmp/{tar_filename}"

        create_tar_archive(str(domain_task_dir), tar_path)

        s3_key = f"data/v1/{task_type}/{tar_filename}"
        upload_tar_to_s3(tar_path, bucket, s3_key)

        for sample_id in renamed_samples:
            uploaded_samples.append({"sample_id": sample_id, "files_uploaded": 0})

        logger.info(f"Created and uploaded tar with {len(renamed_samples)} samples")
        tar_file = tar_filename
    else:
        for sample_id in renamed_samples:
            sample_dir = domain_task_dir / sample_id
            if sample_dir.exists():
                s3_prefix = f"data/v1/{task_type}/{sample_id}/"
                files_uploaded = upload_directory_to_s3(str(sample_dir), bucket, s3_prefix)
                uploaded_samples.append({"sample_id": sample_id, "files_uploaded": files_uploaded})
                logger.info(f"Uploaded sample {sample_id}: {files_uploaded} files")

        logger.info(f"Uploaded {len(renamed_samples)} samples directly")

    return uploaded_samples, tar_file
