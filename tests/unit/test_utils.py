"""Tests for src/utils.py."""

from src.utils import (
    count_generated_samples,
    find_task_directories,
    rename_samples,
)


class TestCountGeneratedSamples:
    """Tests for count_generated_samples function."""

    def test_count_samples_with_files(self, tmp_output_dir):
        """Test counting samples in directories with task files."""
        # Create structure: output/domain_task/sample_0001/
        task_dir = tmp_output_dir / "domain_task"
        task_dir.mkdir()

        for i in range(5):
            sample_dir = task_dir / f"sample_{i:04d}"
            sample_dir.mkdir()
            (sample_dir / "image.png").write_bytes(b"content")

        count = count_generated_samples(str(tmp_output_dir))
        assert count == 5

    def test_count_samples_empty_dir(self, tmp_output_dir):
        """Test counting samples in empty directory."""
        count = count_generated_samples(str(tmp_output_dir))
        assert count == 0

    def test_count_samples_nonexistent_dir(self):
        """Test counting samples in nonexistent directory."""
        count = count_generated_samples("/nonexistent/path")
        assert count == 0

    def test_count_samples_with_mixed_files(self, tmp_output_dir):
        """Test counting with different file types (png, txt, mp4)."""
        task_dir = tmp_output_dir / "test_task"
        task_dir.mkdir()

        # Sample with png
        s1 = task_dir / "sample_0001"
        s1.mkdir()
        (s1 / "image.png").write_bytes(b"png")

        # Sample with txt
        s2 = task_dir / "sample_0002"
        s2.mkdir()
        (s2 / "data.txt").write_text("text")

        # Sample with mp4
        s3 = task_dir / "sample_0003"
        s3.mkdir()
        (s3 / "video.mp4").write_bytes(b"mp4")

        # Empty sample (should not count)
        s4 = task_dir / "sample_0004"
        s4.mkdir()

        count = count_generated_samples(str(tmp_output_dir))
        assert count == 3


class TestFindTaskDirectories:
    """Tests for find_task_directories function."""

    def test_find_task_dir(self, tmp_output_dir):
        """Test finding _task directory."""
        task_dir = tmp_output_dir / "output" / "domain_task"
        task_dir.mkdir(parents=True)

        result = find_task_directories(tmp_output_dir / "output")
        assert result == tmp_output_dir / "output"

    def test_find_task_via_files(self, tmp_output_dir):
        """Test finding task directory via task files."""
        task_dir = tmp_output_dir / "nested" / "domain_task" / "sample"
        task_dir.mkdir(parents=True)
        (task_dir / "image.png").write_bytes(b"content")

        result = find_task_directories(tmp_output_dir / "nested")
        assert result is not None

    def test_find_task_empty_dir(self, tmp_output_dir):
        """Test with empty directory returns None."""
        result = find_task_directories(tmp_output_dir)
        assert result is None


class TestRenameSamples:
    """Tests for rename_samples function."""

    def test_rename_samples_basic(self, sample_task_dir):
        """Test basic sample renaming."""
        renamed = rename_samples(sample_task_dir, start_index=0)

        assert len(renamed) == 3
        assert renamed == ["00000", "00001", "00002"]

        # Verify directories were actually renamed
        for sample_id in renamed:
            assert (sample_task_dir / sample_id).exists()

    def test_rename_samples_with_offset(self, sample_task_dir):
        """Test renaming with start_index offset."""
        renamed = rename_samples(sample_task_dir, start_index=100)

        assert renamed == ["00100", "00101", "00102"]

    def test_rename_samples_empty_dirs_skipped(self, empty_task_dir):
        """Test that empty directories are skipped."""
        renamed = rename_samples(empty_task_dir, start_index=0)
        assert len(renamed) == 0

    def test_rename_samples_preserves_files(self, sample_task_dir):
        """Test that files are preserved after renaming."""
        renamed = rename_samples(sample_task_dir, start_index=0)

        for sample_id in renamed:
            sample_dir = sample_task_dir / sample_id
            assert (sample_dir / "image.png").exists()
            assert (sample_dir / "data.txt").exists()
