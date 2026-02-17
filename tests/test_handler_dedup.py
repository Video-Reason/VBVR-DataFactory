"""Integration tests for handler dedup logic with mocked DDB, S3, and generator."""

import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from vbvrdatafactory.core.models import TaskMessage

TABLE_NAME = "vbvr-param-hash"
BUCKET_NAME = "test-output-bucket"
REGION = "us-east-2"


def _create_sample_dir(base: Path, task_name: str, sample_name: str, param_hash: str) -> Path:
    """Create a fake sample directory with metadata.json and a dummy png."""
    task_dir = base / f"{task_name}_task"
    task_dir.mkdir(parents=True, exist_ok=True)
    sample_dir = task_dir / sample_name
    sample_dir.mkdir(parents=True, exist_ok=True)

    # metadata.json
    metadata = {"param_hash": param_hash, "seed": 42}
    (sample_dir / "metadata.json").write_text(json.dumps(metadata))

    # Required files
    (sample_dir / "first_frame.png").write_bytes(b"\x89PNG fake")
    (sample_dir / "prompt.txt").write_text("test prompt")

    return task_dir


def _setup_aws():
    """Create mocked DynamoDB table and S3 bucket."""
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "generator_name", "KeyType": "HASH"},
            {"AttributeName": "param_hash", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "generator_name", "AttributeType": "S"},
            {"AttributeName": "param_hash", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(
        Bucket=BUCKET_NAME,
        CreateBucketConfiguration={"LocationConstraint": REGION},
    )

    return dynamodb.Table(TABLE_NAME), s3


@pytest.fixture
def output_dir(tmp_path):
    """Provide a temporary output directory, cleaned up after test."""
    d = tmp_path / "output"
    d.mkdir()
    yield d


@pytest.fixture
def mock_config():
    """Patch config values for tests."""
    with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg, \
         patch("vbvrdatafactory.core.dedup.boto3") as _:
        cfg.output_bucket = BUCKET_NAME
        cfg.aws_region = REGION
        cfg.generators_path = "/opt/generators"
        cfg.dedup_table_name = TABLE_NAME
        yield cfg


class TestDedupSamples:
    """Tests for _dedup_samples function."""

    @mock_aws
    def test_all_unique_samples_pass(self, output_dir):
        """All samples have unique hashes → all pass."""
        _setup_aws()

        task_dir = output_dir / "object_trajectory_task"
        task_dir.mkdir()
        for i in range(5):
            sample_dir = task_dir / f"object_trajectory_{i:08d}"
            sample_dir.mkdir()
            (sample_dir / "metadata.json").write_text(json.dumps({"param_hash": f"hash_{i:016x}"}))
            (sample_dir / "first_frame.png").write_bytes(b"\x89PNG")
            (sample_dir / "prompt.txt").write_text("test")

        renamed = [f"object_trajectory_{i:08d}" for i in range(5)]
        task = TaskMessage(type="test-gen", num_samples=5, start_index=0)
        runner = MagicMock()
        metrics = MagicMock()

        with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg:
            cfg.dedup_table_name = TABLE_NAME
            cfg.aws_region = REGION

            from vbvrdatafactory.lambda_handler.handler import _dedup_samples
            result = _dedup_samples(task_dir, renamed, task, runner, metrics)

        assert result == renamed
        runner.run.assert_not_called()  # No regeneration needed

    @mock_aws
    def test_duplicate_samples_detected(self, output_dir):
        """Samples with same param_hash → only first passes, rest are duplicates."""
        _setup_aws()

        task_dir = output_dir / "object_trajectory_task"
        task_dir.mkdir()

        same_hash = "deadbeef" * 2
        for i in range(3):
            sample_dir = task_dir / f"object_trajectory_{i:08d}"
            sample_dir.mkdir()
            (sample_dir / "metadata.json").write_text(json.dumps({"param_hash": same_hash}))
            (sample_dir / "first_frame.png").write_bytes(b"\x89PNG")
            (sample_dir / "prompt.txt").write_text("test")

        renamed = [f"object_trajectory_{i:08d}" for i in range(3)]
        task = TaskMessage(type="test-gen", num_samples=3, start_index=0)

        # Mock runner to produce new samples with unique hashes on retry
        runner = MagicMock()
        _global_counter = [0]

        def fake_run(retry_task, retry_output_dir):
            retry_output_dir.mkdir(parents=True, exist_ok=True)
            rtask_dir = retry_output_dir / "object_trajectory_task"
            rtask_dir.mkdir()
            for j in range(retry_task.num_samples):
                sd = rtask_dir / f"task_{j}"
                sd.mkdir()
                # Each sample gets a globally unique hash
                unique_hash = f"{_global_counter[0]:016x}"
                _global_counter[0] += 1
                (sd / "metadata.json").write_text(json.dumps({"param_hash": unique_hash}))
                (sd / "first_frame.png").write_bytes(b"\x89PNG")
                (sd / "prompt.txt").write_text("test")

        runner.run.side_effect = fake_run

        metrics = MagicMock()

        with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg:
            cfg.dedup_table_name = TABLE_NAME
            cfg.aws_region = REGION

            from vbvrdatafactory.lambda_handler.handler import _dedup_samples
            result = _dedup_samples(task_dir, renamed, task, runner, metrics)

        # First sample passes, 2 duplicates get regenerated and pass
        assert len(result) == 3
        assert runner.run.call_count == 1  # One batch regeneration

    @mock_aws
    def test_no_param_hash_passes_through(self, output_dir):
        """Samples without param_hash in metadata skip dedup check."""
        _setup_aws()

        task_dir = output_dir / "object_trajectory_task"
        task_dir.mkdir()

        sample_dir = task_dir / "object_trajectory_0000"
        sample_dir.mkdir()
        (sample_dir / "metadata.json").write_text(json.dumps({"some_other_field": "value"}))
        (sample_dir / "first_frame.png").write_bytes(b"\x89PNG")
        (sample_dir / "prompt.txt").write_text("test")

        renamed = ["object_trajectory_0000"]
        task = TaskMessage(type="test-gen", num_samples=1, start_index=0)
        runner = MagicMock()
        metrics = MagicMock()

        with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg:
            cfg.dedup_table_name = TABLE_NAME
            cfg.aws_region = REGION

            from vbvrdatafactory.lambda_handler.handler import _dedup_samples
            result = _dedup_samples(task_dir, renamed, task, runner, metrics)

        assert result == renamed

    @mock_aws
    def test_no_metadata_passes_through(self, output_dir):
        """Samples without metadata.json skip dedup check."""
        _setup_aws()

        task_dir = output_dir / "object_trajectory_task"
        task_dir.mkdir()

        sample_dir = task_dir / "object_trajectory_0000"
        sample_dir.mkdir()
        (sample_dir / "first_frame.png").write_bytes(b"\x89PNG")
        (sample_dir / "prompt.txt").write_text("test")

        renamed = ["object_trajectory_0000"]
        task = TaskMessage(type="test-gen", num_samples=1, start_index=0)
        runner = MagicMock()
        metrics = MagicMock()

        with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg:
            cfg.dedup_table_name = TABLE_NAME
            cfg.aws_region = REGION

            from vbvrdatafactory.lambda_handler.handler import _dedup_samples
            result = _dedup_samples(task_dir, renamed, task, runner, metrics)

        assert result == renamed

    @mock_aws
    def test_missing_sample_dir_skipped(self, output_dir):
        """Sample dir was cleaned up (regeneration failed) → skipped, not treated as unique."""
        _setup_aws()

        task_dir = output_dir / "object_trajectory_task"
        task_dir.mkdir()
        # Don't create the sample dir — simulate cleanup after failed regeneration

        renamed = ["object_trajectory_0000"]
        task = TaskMessage(type="test-gen", num_samples=1, start_index=0)
        runner = MagicMock()
        metrics = MagicMock()

        with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg:
            cfg.dedup_table_name = TABLE_NAME
            cfg.aws_region = REGION

            from vbvrdatafactory.lambda_handler.handler import _dedup_samples
            result = _dedup_samples(task_dir, renamed, task, runner, metrics)

        assert result == []  # Should NOT be in unique_samples

    @mock_aws
    def test_dedup_table_name_not_set(self, output_dir):
        """If DEDUP_TABLE_NAME is not set, dedup is skipped entirely."""
        _setup_aws()

        task_dir = output_dir / "object_trajectory_task"
        task_dir.mkdir()

        renamed = ["object_trajectory_0000"]
        task = TaskMessage(type="test-gen", num_samples=1, start_index=0)
        runner = MagicMock()
        metrics = MagicMock()

        with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg:
            cfg.dedup_table_name = None
            cfg.aws_region = REGION

            from vbvrdatafactory.lambda_handler.handler import _dedup_samples
            result = _dedup_samples(task_dir, renamed, task, runner, metrics)

        assert result == renamed  # Pass through without checking

    @mock_aws
    def test_lambda_retry_same_sample_passes(self, output_dir):
        """Lambda retry: same sample_id re-registers same hash → should pass."""
        table, _ = _setup_aws()

        # Pre-register as if from previous Lambda invocation
        table.put_item(Item={
            "generator_name": "test-gen",
            "param_hash": "abcd1234abcd1234",
            "sample_id": "object_trajectory_0000",
        })

        task_dir = output_dir / "object_trajectory_task"
        task_dir.mkdir()
        sample_dir = task_dir / "object_trajectory_0000"
        sample_dir.mkdir()
        (sample_dir / "metadata.json").write_text(json.dumps({"param_hash": "abcd1234abcd1234"}))
        (sample_dir / "first_frame.png").write_bytes(b"\x89PNG")
        (sample_dir / "prompt.txt").write_text("test")

        renamed = ["object_trajectory_0000"]
        task = TaskMessage(type="test-gen", num_samples=1, start_index=0)
        runner = MagicMock()
        metrics = MagicMock()

        with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg:
            cfg.dedup_table_name = TABLE_NAME
            cfg.aws_region = REGION

            from vbvrdatafactory.lambda_handler.handler import _dedup_samples
            result = _dedup_samples(task_dir, renamed, task, runner, metrics)

        assert result == renamed
        runner.run.assert_not_called()

    @mock_aws
    def test_dedup_metrics_emitted(self, output_dir):
        """Verify dedup metrics are emitted correctly."""
        _setup_aws()

        task_dir = output_dir / "object_trajectory_task"
        task_dir.mkdir()

        same_hash = "deadbeef" * 2
        for i in range(3):
            sample_dir = task_dir / f"object_trajectory_{i:08d}"
            sample_dir.mkdir()
            if i == 0:
                (sample_dir / "metadata.json").write_text(json.dumps({"param_hash": "unique_hash_0000"}))
            else:
                (sample_dir / "metadata.json").write_text(json.dumps({"param_hash": same_hash}))
            (sample_dir / "first_frame.png").write_bytes(b"\x89PNG")
            (sample_dir / "prompt.txt").write_text("test")

        renamed = [f"object_trajectory_{i:08d}" for i in range(3)]
        task = TaskMessage(type="test-gen", num_samples=3, start_index=0)

        # Make runner produce unique samples
        def fake_run(retry_task, retry_output_dir):
            retry_output_dir.mkdir(parents=True, exist_ok=True)
            rtask_dir = retry_output_dir / "object_trajectory_task"
            rtask_dir.mkdir()
            for j in range(retry_task.num_samples):
                sd = rtask_dir / f"task_{j}"
                sd.mkdir()
                (sd / "metadata.json").write_text(json.dumps({"param_hash": f"retry_unique_{j:08x}"}))
                (sd / "first_frame.png").write_bytes(b"\x89PNG")
                (sd / "prompt.txt").write_text("test")

        runner = MagicMock()
        runner.run.side_effect = fake_run
        metrics = MagicMock()

        with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg:
            cfg.dedup_table_name = TABLE_NAME
            cfg.aws_region = REGION

            from vbvrdatafactory.lambda_handler.handler import _dedup_samples
            _dedup_samples(task_dir, renamed, task, runner, metrics)

        # Check metrics were emitted
        metric_calls = {call.args[0]: call.args[1] for call in metrics.put_metric.call_args_list}
        assert "DedupDuplicatesFound" in metric_calls
        assert "DedupRetryRounds" in metric_calls
        assert "DedupSkipped" in metric_calls


class TestBatchRegenerate:
    """Tests for _batch_regenerate function."""

    def test_successful_regeneration(self, output_dir):
        """Batch regenerate replaces duplicate sample dirs with new ones."""
        task_dir = output_dir / "object_trajectory_task"
        task_dir.mkdir()

        # Create old samples to be replaced
        for i in range(2):
            sd = task_dir / f"object_trajectory_{i:08d}"
            sd.mkdir()
            (sd / "metadata.json").write_text(json.dumps({"param_hash": "old_hash"}))
            (sd / "first_frame.png").write_bytes(b"\x89PNG old")

        task = TaskMessage(type="test-gen", num_samples=2, start_index=0)

        def fake_run(retry_task, retry_output_dir):
            retry_output_dir.mkdir(parents=True, exist_ok=True)
            rtask_dir = retry_output_dir / "object_trajectory_task"
            rtask_dir.mkdir()
            for j in range(retry_task.num_samples):
                sd = rtask_dir / f"task_{j}"
                sd.mkdir()
                (sd / "metadata.json").write_text(json.dumps({"param_hash": f"new_hash_{j}"}))
                (sd / "first_frame.png").write_bytes(b"\x89PNG new")

        runner = MagicMock()
        runner.run.side_effect = fake_run

        from vbvrdatafactory.lambda_handler.handler import _batch_regenerate
        _batch_regenerate(
            ["object_trajectory_00000000", "object_trajectory_00000001"],
            task_dir, task, runner,
        )

        # Old samples should be replaced with new ones
        for i in range(2):
            sd = task_dir / f"object_trajectory_{i:08d}"
            assert sd.exists()
            meta = json.loads((sd / "metadata.json").read_text())
            assert meta["param_hash"].startswith("new_hash_")

    def test_failed_regeneration_cleans_up(self, output_dir):
        """If generator fails, old sample dirs are cleaned up."""
        task_dir = output_dir / "object_trajectory_task"
        task_dir.mkdir()

        sd = task_dir / "object_trajectory_00000000"
        sd.mkdir()
        (sd / "metadata.json").write_text(json.dumps({"param_hash": "old"}))

        task = TaskMessage(type="test-gen", num_samples=1, start_index=0)
        runner = MagicMock()
        runner.run.side_effect = RuntimeError("generator crashed")

        from vbvrdatafactory.lambda_handler.handler import _batch_regenerate
        _batch_regenerate(["object_trajectory_00000000"], task_dir, task, runner)

        # Sample dir should be cleaned up
        assert not sd.exists()


class TestProcessSamplesDedup:
    """Tests for _process_samples with dedup enabled (end-to-end with mocks)."""

    @mock_aws
    def test_dedup_all_duplicates_no_error(self, output_dir):
        """When dedup removes all samples, should return 0 samples, not raise."""
        table, s3 = _setup_aws()

        # Pre-register all hashes
        same_hash = "aaaa1111bbbb2222"
        table.put_item(Item={
            "generator_name": "test-gen",
            "param_hash": same_hash,
            "sample_id": "other_sample",
        })

        task = TaskMessage(type="test-gen", num_samples=2, start_index=0, seed=42, dedup=True)

        # Mock generator to produce samples with same hash
        def fake_generator_run(t, out_dir):
            out_dir.mkdir(parents=True, exist_ok=True)
            task_dir = out_dir / "object_trajectory_task"
            task_dir.mkdir()
            for i in range(t.num_samples):
                sd = task_dir / f"task_{i}"
                sd.mkdir()
                (sd / "metadata.json").write_text(json.dumps({"param_hash": same_hash}))
                (sd / "first_frame.png").write_bytes(b"\x89PNG")
                (sd / "prompt.txt").write_text("test")
            return t.num_samples

        with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg, \
             patch("vbvrdatafactory.lambda_handler.handler.GeneratorRunner") as MockRunner, \
             patch("vbvrdatafactory.lambda_handler.handler.S3Uploader") as MockUploader:
            cfg.output_bucket = BUCKET_NAME
            cfg.aws_region = REGION
            cfg.generators_path = "/opt/generators"
            cfg.dedup_table_name = TABLE_NAME

            runner_instance = MockRunner.return_value
            runner_instance.run.side_effect = fake_generator_run

            uploader_instance = MockUploader.return_value
            uploader_instance.upload_samples.return_value = ([], None)

            from vbvrdatafactory.core.metrics import MetricsClient
            metrics = MagicMock(spec=MetricsClient)

            from vbvrdatafactory.lambda_handler.handler import _process_samples
            result = _process_samples(task, metrics)

        # Should succeed with 0 samples, not raise ValueError
        assert result.samples_uploaded == 0
        assert result.sample_ids == []

    @mock_aws
    def test_dedup_disabled_no_ddb_calls(self, output_dir):
        """When dedup=False, no DDB interaction should happen."""
        _setup_aws()

        task = TaskMessage(type="test-gen", num_samples=2, start_index=0, seed=42, dedup=False)

        def fake_generator_run(t, out_dir):
            out_dir.mkdir(parents=True, exist_ok=True)
            task_dir = out_dir / "object_trajectory_task"
            task_dir.mkdir()
            for i in range(t.num_samples):
                sd = task_dir / f"task_{i}"
                sd.mkdir()
                (sd / "metadata.json").write_text(json.dumps({"param_hash": "same_hash"}))
                (sd / "first_frame.png").write_bytes(b"\x89PNG")
                (sd / "prompt.txt").write_text("test")
            return t.num_samples

        with patch("vbvrdatafactory.lambda_handler.handler.config") as cfg, \
             patch("vbvrdatafactory.lambda_handler.handler.GeneratorRunner") as MockRunner, \
             patch("vbvrdatafactory.lambda_handler.handler.S3Uploader") as MockUploader:
            cfg.output_bucket = BUCKET_NAME
            cfg.aws_region = REGION
            cfg.generators_path = "/opt/generators"
            cfg.dedup_table_name = TABLE_NAME

            runner_instance = MockRunner.return_value
            runner_instance.run.side_effect = fake_generator_run

            uploaded = [{"sample_id": f"object_trajectory_{i:08d}", "files_uploaded": 2} for i in range(2)]
            uploader_instance = MockUploader.return_value
            uploader_instance.upload_samples.return_value = (uploaded, None)

            metrics = MagicMock()

            from vbvrdatafactory.lambda_handler.handler import _process_samples
            result = _process_samples(task, metrics)

        assert result.samples_uploaded == 2
        # DedupChecker should NOT have been used
        metrics.put_metric.assert_not_called()  # No dedup metrics
