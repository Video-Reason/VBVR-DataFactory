"""Tests for src/generator.py."""

import subprocess

import pytest

from src.generator import detect_output_arg, run_generator


class TestDetectOutputArg:
    """Tests for detect_output_arg function."""

    def test_detect_output_dir(self, mock_generator_path):
        """Test detecting --output-dir argument."""
        result = detect_output_arg(str(mock_generator_path))
        assert result == "--output-dir"

    def test_detect_output(self, tmp_output_dir):
        """Test detecting --output argument."""
        generator_path = tmp_output_dir / "generator"
        examples_dir = generator_path / "examples"
        examples_dir.mkdir(parents=True)

        # Create script with --output instead of --output-dir
        (examples_dir / "generate.py").write_text(
            """import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=str)
parser.parse_args()
"""
        )

        result = detect_output_arg(str(generator_path))
        assert result == "--output"

    def test_detect_fallback(self, tmp_output_dir):
        """Test fallback when script doesn't exist."""
        result = detect_output_arg(str(tmp_output_dir / "nonexistent"))
        assert result == "--output-dir"

    def test_detect_timeout(self, tmp_output_dir, mocker):
        """Test timeout handling."""
        # Mock subprocess.run to raise TimeoutExpired
        mocker.patch(
            "src.generator.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="test", timeout=30),
        )

        result = detect_output_arg(str(tmp_output_dir))
        assert result == "--output-dir"


class TestRunGenerator:
    """Tests for run_generator function."""

    def test_successful_generation(self, tmp_output_dir, mocker):
        """Test successful generation."""
        generator_path = tmp_output_dir / "gen"
        generator_path.mkdir()
        output_dir = tmp_output_dir / "output"

        mocker.patch("src.generator.detect_output_arg", return_value="--output-dir")
        mocker.patch("src.generator.subprocess.run")
        mocker.patch("src.generator.count_generated_samples", return_value=5)

        result = run_generator(
            generator_path=str(generator_path),
            num_samples=5,
            seed=42,
            output_dir=str(output_dir),
        )

        assert result == 5

    def test_generation_with_no_seed(self, tmp_output_dir, mocker):
        """Test generation works when no seed is provided."""
        generator_path = tmp_output_dir / "gen"
        generator_path.mkdir()
        output_dir = tmp_output_dir / "output"

        mocker.patch("src.generator.detect_output_arg", return_value="--output-dir")
        mock_run = mocker.patch("src.generator.subprocess.run")
        mocker.patch("src.generator.count_generated_samples", return_value=5)

        run_generator(
            generator_path=str(generator_path),
            num_samples=5,
            seed=None,
            output_dir=str(output_dir),
        )

        # Verify --seed was not in the command
        call_args = mock_run.call_args[0][0]
        assert "--seed" not in call_args

    def test_generation_failure_raises(self, tmp_output_dir, mocker):
        """Test that subprocess errors propagate."""
        generator_path = tmp_output_dir / "gen"
        generator_path.mkdir()
        output_dir = tmp_output_dir / "output"

        mocker.patch("src.generator.detect_output_arg", return_value="--output-dir")
        error = subprocess.CalledProcessError(1, "cmd")
        error.stderr = "Some error"
        error.stdout = ""
        mocker.patch("src.generator.subprocess.run", side_effect=error)

        with pytest.raises(subprocess.CalledProcessError):
            run_generator(
                generator_path=str(generator_path),
                num_samples=5,
                seed=42,
                output_dir=str(output_dir),
            )
