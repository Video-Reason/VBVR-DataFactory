"""Tests for src/handler.py."""

import json

import pytest

from src.handler import handler, process_task


class TestHandler:
    """Tests for the Lambda handler function."""

    def test_handler_direct_invocation(self, mocker):
        """Test handler with direct task invocation (no SQS Records)."""
        mock_process_task = mocker.patch("src.handler.process_task")
        mock_process_task.return_value = {
            "generator": "test-gen",
            "samples_uploaded": 5,
            "sample_ids": ["00000", "00001", "00002", "00003", "00004"],
        }

        event = {
            "type": "test-gen",
            "num_samples": 5,
            "start_index": 0,
        }

        result = handler(event, None)

        assert result["status"] == "ok"
        assert result["processed"] == 1
        assert len(result["results"]) == 1
        mock_process_task.assert_called_once()

    def test_handler_sqs_event(self, mocker):
        """Test handler with SQS event format."""
        mock_process_task = mocker.patch("src.handler.process_task")
        mock_process_task.return_value = {
            "generator": "test-gen",
            "samples_uploaded": 5,
            "sample_ids": ["00000"],
        }

        event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "type": "test-gen",
                            "num_samples": 5,
                            "start_index": 0,
                        }
                    )
                }
            ]
        }

        result = handler(event, None)

        assert result["status"] == "ok"
        assert result["processed"] == 1

    def test_handler_multiple_records(self, mocker):
        """Test handler with multiple SQS records."""
        mock_process_task = mocker.patch("src.handler.process_task")
        mock_process_task.return_value = {
            "generator": "test-gen",
            "samples_uploaded": 1,
            "sample_ids": ["00000"],
        }

        event = {
            "Records": [
                {"body": json.dumps({"type": "gen1", "num_samples": 1})},
                {"body": json.dumps({"type": "gen2", "num_samples": 1})},
            ]
        }

        result = handler(event, None)

        assert result["status"] == "ok"
        assert result["processed"] == 2
        assert len(result["results"]) == 2


class TestProcessTask:
    """Tests for the process_task function."""

    def test_invalid_output_format(self):
        """Test that invalid output_format raises ValueError."""
        task = {
            "type": "test-gen",
            "num_samples": 5,
            "output_format": "invalid",
        }

        with pytest.raises(ValueError, match="Invalid output_format"):
            process_task(task)

    def test_valid_output_format_files(self, mocker):
        """Test valid output_format 'files' is accepted."""
        mock_process = mocker.patch("src.handler._process_samples")
        mock_process.return_value = {
            "generator": "test-gen",
            "samples_uploaded": 5,
            "sample_ids": ["00000"],
        }

        task = {
            "type": "test-gen",
            "num_samples": 5,
            "output_format": "files",
        }

        result = process_task(task)
        assert result["generator"] == "test-gen"

    def test_valid_output_format_tar(self, mocker):
        """Test valid output_format 'tar' is accepted."""
        mock_process = mocker.patch("src.handler._process_samples")
        mock_process.return_value = {
            "generator": "test-gen",
            "samples_uploaded": 5,
            "sample_ids": ["00000"],
            "tar_file": "test.tar.gz",
        }

        task = {
            "type": "test-gen",
            "num_samples": 5,
            "output_format": "tar",
        }

        result = process_task(task)
        assert "tar_files" in result

    def test_random_seed_generated_when_not_provided(self, mocker):
        """Test that random seed is generated when not provided."""
        mock_process = mocker.patch("src.handler._process_samples")
        mock_process.return_value = {
            "generator": "test-gen",
            "samples_uploaded": 5,
            "sample_ids": ["00000"],
        }

        task = {
            "type": "test-gen",
            "num_samples": 5,
        }

        process_task(task)

        # Check that _process_samples was called with a seed (not None)
        # Args: task_type, num_samples, start_index, seed, output_format
        call_args = mock_process.call_args[0]
        seed = call_args[3]  # seed is 4th positional arg
        assert seed is not None
        assert isinstance(seed, int)

    def test_provided_seed_is_used(self, mocker):
        """Test that provided seed is passed through."""
        mock_process = mocker.patch("src.handler._process_samples")
        mock_process.return_value = {
            "generator": "test-gen",
            "samples_uploaded": 5,
            "sample_ids": ["00000"],
        }

        task = {
            "type": "test-gen",
            "num_samples": 5,
            "seed": 12345,
        }

        process_task(task)

        # Args: task_type, num_samples, start_index, seed, output_format
        call_args = mock_process.call_args[0]
        seed = call_args[3]  # seed is 4th positional arg
        assert seed == 12345

    def test_default_output_format_is_files(self, mocker):
        """Test that default output_format is 'files'."""
        mock_process = mocker.patch("src.handler._process_samples")
        mock_process.return_value = {
            "generator": "test-gen",
            "samples_uploaded": 5,
            "sample_ids": ["00000"],
        }

        task = {
            "type": "test-gen",
            "num_samples": 5,
        }

        process_task(task)

        # Args: task_type, num_samples, start_index, seed, output_format
        call_args = mock_process.call_args[0]
        output_format = call_args[4]  # output_format is 5th positional arg
        assert output_format == "files"

    def test_missing_type_raises_error(self):
        """Test that missing 'type' field raises KeyError."""
        task = {
            "num_samples": 5,
        }

        with pytest.raises(KeyError):
            process_task(task)

    def test_missing_num_samples_raises_error(self):
        """Test that missing 'num_samples' field raises KeyError."""
        task = {
            "type": "test-gen",
        }

        with pytest.raises(KeyError):
            process_task(task)

    def test_process_samples_exception_propagates(self, mocker):
        """Test that exceptions from _process_samples propagate correctly."""
        mock_process = mocker.patch("src.handler._process_samples")
        mock_process.side_effect = ValueError("Generator not found")

        task = {
            "type": "nonexistent-gen",
            "num_samples": 5,
        }

        with pytest.raises(ValueError, match="Generator not found"):
            process_task(task)

    def test_handler_raises_on_task_failure(self, mocker):
        """Test that handler re-raises exceptions from process_task."""
        mock_process_task = mocker.patch("src.handler.process_task")
        mock_process_task.side_effect = RuntimeError("Task failed")

        event = {
            "type": "test-gen",
            "num_samples": 5,
        }

        with pytest.raises(RuntimeError, match="Task failed"):
            handler(event, None)
