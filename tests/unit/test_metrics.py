"""Tests for src/metrics.py."""

import pytest

from src.metrics import put_metric, track_duration


class TestPutMetric:
    """Tests for put_metric function."""

    def test_put_metric_success(self, mocker):
        """Test putting a metric to CloudWatch."""
        mock_cloudwatch = mocker.patch("src.metrics.cloudwatch")

        put_metric("TaskSuccess", 1, "Count", "test-generator")

        mock_cloudwatch.put_metric_data.assert_called_once_with(
            Namespace="VMDatasetPipeline",
            MetricData=[
                {
                    "MetricName": "TaskSuccess",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "GeneratorType", "Value": "test-generator"}],
                }
            ],
        )

    def test_put_metric_with_error_type(self, mocker):
        """Test putting a failure metric with error type."""
        mock_cloudwatch = mocker.patch("src.metrics.cloudwatch")

        put_metric("TaskFailure", 1, "Count", "test-generator", error_type="ValueError")

        mock_cloudwatch.put_metric_data.assert_called_once_with(
            Namespace="VMDatasetPipeline",
            MetricData=[
                {
                    "MetricName": "TaskFailure",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "GeneratorType", "Value": "test-generator"},
                        {"Name": "ErrorType", "Value": "ValueError"},
                    ],
                }
            ],
        )

    def test_put_metric_cloudwatch_error_does_not_raise(self, mocker):
        """Test that CloudWatch errors are logged but not raised."""
        mock_cloudwatch = mocker.patch("src.metrics.cloudwatch")
        mock_cloudwatch.put_metric_data.side_effect = Exception("CloudWatch error")
        mock_logger = mocker.patch("src.metrics.logger")

        # Should not raise
        put_metric("TaskSuccess", 1, "Count", "test-generator")

        mock_logger.warning.assert_called_once()


class TestTrackDuration:
    """Tests for track_duration context manager."""

    def test_track_duration_emits_metric(self, mocker):
        """Test that track_duration emits TaskDuration metric."""
        mock_put_metric = mocker.patch("src.metrics.put_metric")
        mocker.patch("src.metrics.time.time", side_effect=[0, 1.5])  # 1.5 seconds

        with track_duration("test-generator"):
            pass

        mock_put_metric.assert_called_once_with("TaskDuration", 1500.0, "Milliseconds", "test-generator")

    def test_track_duration_emits_on_exception(self, mocker):
        """Test that duration is emitted even if exception occurs."""
        mock_put_metric = mocker.patch("src.metrics.put_metric")
        mocker.patch("src.metrics.time.time", side_effect=[0, 2.0])

        with pytest.raises(ValueError):
            with track_duration("test-generator"):
                raise ValueError("Test error")

        mock_put_metric.assert_called_once_with("TaskDuration", 2000.0, "Milliseconds", "test-generator")
