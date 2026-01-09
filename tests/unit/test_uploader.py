"""Tests for src/uploader.py."""

import tarfile

import pytest

from src.uploader import create_tar_archive, upload_directory_to_s3, upload_samples


class TestCreateTarArchive:
    """Tests for create_tar_archive function."""

    def test_create_tar_archive(self, tmp_output_dir):
        """Test creating a tar.gz archive."""
        # Create source directory with files
        source_dir = tmp_output_dir / "source"
        source_dir.mkdir()
        (source_dir / "file1.txt").write_text("content1")
        (source_dir / "file2.txt").write_text("content2")

        subdir = source_dir / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("content3")

        tar_path = tmp_output_dir / "output.tar.gz"
        result = create_tar_archive(str(source_dir), str(tar_path))

        assert result == str(tar_path)
        assert tar_path.exists()

        # Verify tar contents
        with tarfile.open(tar_path, "r:gz") as tar:
            names = tar.getnames()
            assert "file1.txt" in names
            assert "file2.txt" in names
            assert "subdir" in names

    def test_create_tar_empty_dir(self, tmp_output_dir):
        """Test creating tar from empty directory."""
        source_dir = tmp_output_dir / "empty"
        source_dir.mkdir()

        tar_path = tmp_output_dir / "empty.tar.gz"
        create_tar_archive(str(source_dir), str(tar_path))

        assert tar_path.exists()


class TestUploadDirectoryToS3:
    """Tests for upload_directory_to_s3 function."""

    def test_upload_directory(self, sample_task_dir, mock_s3):
        """Test uploading directory to S3."""
        sample_dir = sample_task_dir / "sample_0000"

        count = upload_directory_to_s3(str(sample_dir), "test-bucket", "data/v1/test/00000/")

        assert count == 2  # image.png and data.txt
        assert mock_s3.upload_file.call_count == 2

    def test_upload_deletes_files(self, sample_task_dir, mock_s3):
        """Test that files are deleted after upload."""
        sample_dir = sample_task_dir / "sample_0000"

        upload_directory_to_s3(str(sample_dir), "test-bucket", "data/v1/test/00000/")

        # Files should be deleted
        assert not (sample_dir / "image.png").exists()
        assert not (sample_dir / "data.txt").exists()

    def test_upload_empty_directory(self, tmp_output_dir, mock_s3):
        """Test uploading empty directory."""
        empty_dir = tmp_output_dir / "empty"
        empty_dir.mkdir()

        count = upload_directory_to_s3(str(empty_dir), "test-bucket", "prefix/")

        assert count == 0
        mock_s3.upload_file.assert_not_called()


class TestUploadSamples:
    """Tests for upload_samples function."""

    def test_upload_samples_direct(self, sample_task_dir, mock_s3):
        """Test uploading samples directly (not as tar)."""
        renamed = ["00000", "00001", "00002"]

        # Rename directories for test
        for i, name in enumerate(renamed):
            old = sample_task_dir / f"sample_{i:04d}"
            new = sample_task_dir / name
            old.rename(new)

        uploaded, tar_file = upload_samples(
            domain_task_dir=sample_task_dir,
            renamed_samples=renamed,
            task_type="test-generator",
            bucket="test-bucket",
            start_index=0,
            output_format="files",
        )

        assert len(uploaded) == 3
        assert tar_file is None
        assert mock_s3.upload_file.call_count == 6  # 2 files per sample

    def test_upload_samples_as_tar(self, sample_task_dir, mock_s3, tmp_output_dir):
        """Test uploading samples as tar archive."""
        renamed = ["00000", "00001", "00002"]

        # Rename directories for test
        for i, name in enumerate(renamed):
            old = sample_task_dir / f"sample_{i:04d}"
            new = sample_task_dir / name
            old.rename(new)

        uploaded, tar_file = upload_samples(
            domain_task_dir=sample_task_dir,
            renamed_samples=renamed,
            task_type="test-generator",
            bucket="test-bucket",
            start_index=0,
            output_format="tar",
        )

        assert len(uploaded) == 3
        assert tar_file == "test-generator_0_2.tar.gz"
        # Only 1 upload call for the tar file
        mock_s3.upload_file.assert_called_once()


class TestUploadFailures:
    """Tests for S3 upload failure handling."""

    def test_upload_directory_raises_on_s3_error(self, sample_task_dir, mocker):
        """Test that S3 errors are propagated."""
        from botocore.exceptions import ClientError

        mock_s3 = mocker.MagicMock()
        mock_s3.upload_file.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject"
        )
        mocker.patch("src.uploader.s3", mock_s3)

        sample_dir = sample_task_dir / "sample_0000"

        with pytest.raises(ClientError):
            upload_directory_to_s3(str(sample_dir), "test-bucket", "prefix/")

    def test_upload_partial_success_then_failure(self, sample_task_dir, mocker):
        """Test behavior when upload fails after some files succeed."""
        from botocore.exceptions import ClientError

        mock_s3 = mocker.MagicMock()
        # First upload succeeds, second fails
        mock_s3.upload_file.side_effect = [
            None,
            ClientError({"Error": {"Code": "InternalError", "Message": "Internal Error"}}, "PutObject"),
        ]
        mocker.patch("src.uploader.s3", mock_s3)

        sample_dir = sample_task_dir / "sample_0000"

        with pytest.raises(ClientError):
            upload_directory_to_s3(str(sample_dir), "test-bucket", "prefix/")

        # First file was uploaded
        assert mock_s3.upload_file.call_count == 2

    def test_upload_tar_raises_on_s3_error(self, tmp_output_dir, mocker):
        """Test that tar upload errors are propagated."""
        from botocore.exceptions import ClientError

        # Create a tar file
        tar_path = tmp_output_dir / "test.tar.gz"
        tar_path.write_bytes(b"fake tar content")

        mock_s3 = mocker.MagicMock()
        mock_s3.upload_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}}, "PutObject"
        )
        mocker.patch("src.uploader.s3", mock_s3)

        from src.uploader import upload_tar_to_s3

        with pytest.raises(ClientError):
            upload_tar_to_s3(str(tar_path), "nonexistent-bucket", "key.tar.gz")
