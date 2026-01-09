#!/usr/bin/env python3
"""
Local test module for validating generators.

Features:
- Output format validation (required files, structure)
- Performance metrics (generation time, samples/sec)
- Memory monitoring (peak RSS)

Can be used as a library (imported by test_server.py) or CLI tool.

Usage:
    uv run python scripts/local_test.py -g G-1_object_trajectory_data-generator -n 5
    uv run python scripts/local_test.py --all -n 3
    uv run python scripts/local_test.py --list
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import psutil

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.common import GENERATORS_PATH  # noqa: E402
from src.utils import find_task_directories  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Expected output structure
REQUIRED_FILES = {"first_frame.png", "prompt.txt"}
OPTIONAL_FILES = {"final_frame.png", "rubric.txt", "ground_truth.mp4"}
ALL_VALID_FILES = REQUIRED_FILES | OPTIONAL_FILES


@dataclass
class ValidationResult:
    """Result of validating a single sample."""

    sample_id: str
    valid: bool
    missing_required: list[str] = field(default_factory=list)
    extra_files: list[str] = field(default_factory=list)
    file_sizes: dict[str, int] = field(default_factory=dict)


@dataclass
class TestResult:
    """Result of testing a generator."""

    generator: str
    success: bool
    num_samples_requested: int
    num_samples_generated: int
    duration_seconds: float
    seconds_per_sample: float
    peak_memory_mb: float
    validation_results: list[ValidationResult] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "generator": self.generator,
            "success": self.success,
            "num_samples_requested": self.num_samples_requested,
            "num_samples_generated": self.num_samples_generated,
            "duration_seconds": round(self.duration_seconds, 2),
            "seconds_per_sample": round(self.seconds_per_sample, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 1),
            "validation": {
                "all_valid": all(v.valid for v in self.validation_results),
                "valid_count": sum(1 for v in self.validation_results if v.valid),
                "invalid_count": sum(1 for v in self.validation_results if not v.valid),
                "details": [asdict(v) for v in self.validation_results],
            },
            "error": self.error,
        }


def run_generator_with_memory_tracking(
    generator_path: str,
    num_samples: int,
    seed: Optional[int],
    output_dir: str,
) -> tuple[int, float]:
    """
    Run generator and track peak memory usage.

    Returns:
        Tuple of (samples_generated, peak_memory_mb)
    """
    from src.generator import detect_output_arg
    from src.utils import count_generated_samples

    output_arg = detect_output_arg(generator_path)
    cmd = [sys.executable, "examples/generate.py", "--num-samples", str(num_samples)]

    if seed is not None:
        cmd.extend(["--seed", str(seed)])
    cmd.extend([output_arg, output_dir])

    # Set PYTHONPATH to generator directory
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(generator_path)

    # Track peak memory in a separate thread
    peak_memory_mb = 0.0
    stop_monitoring = threading.Event()

    def monitor_memory(proc: subprocess.Popen):
        nonlocal peak_memory_mb
        try:
            ps_proc = psutil.Process(proc.pid)
            while not stop_monitoring.is_set():
                try:
                    # Get memory of process and all children
                    mem = ps_proc.memory_info().rss
                    for child in ps_proc.children(recursive=True):
                        try:
                            mem += child.memory_info().rss
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    peak_memory_mb = max(peak_memory_mb, mem / (1024 * 1024))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
                time.sleep(0.1)  # Sample every 100ms
        except Exception:
            pass

    proc = subprocess.Popen(
        cmd,
        cwd=generator_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    monitor_thread = threading.Thread(target=monitor_memory, args=(proc,))
    monitor_thread.start()

    stdout, stderr = proc.communicate()
    stop_monitoring.set()
    monitor_thread.join(timeout=1)

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, stdout, stderr)

    generated = count_generated_samples(output_dir)
    return generated, peak_memory_mb


def list_generators() -> list[str]:
    """List all available generators."""
    generators_path = Path(GENERATORS_PATH)
    if not generators_path.exists():
        return []
    return sorted(
        [d.name for d in generators_path.iterdir() if d.is_dir() and (d / "examples" / "generate.py").exists()]
    )


def validate_sample(sample_dir: Path) -> ValidationResult:
    """Validate a single sample's output structure."""
    files = {f.name for f in sample_dir.iterdir() if f.is_file()}

    missing_required = [f for f in REQUIRED_FILES if f not in files]
    extra_files = [f for f in files if f not in ALL_VALID_FILES]

    file_sizes = {}
    for f in sample_dir.iterdir():
        if f.is_file():
            file_sizes[f.name] = f.stat().st_size

    return ValidationResult(
        sample_id=sample_dir.name,
        valid=len(missing_required) == 0,
        missing_required=missing_required,
        extra_files=extra_files,
        file_sizes=file_sizes,
    )


def test_generator(
    generator: str,
    num_samples: int,
    seed: Optional[int] = None,
    keep_output: bool = False,
    output_base: Optional[str] = None,
) -> TestResult:
    """
    Test a single generator.

    Args:
        generator: Generator name
        num_samples: Number of samples to generate
        seed: Random seed (optional)
        keep_output: Whether to keep output files
        output_base: Base directory for output

    Returns:
        TestResult with metrics and validation results
    """
    generator_path = os.path.join(GENERATORS_PATH, generator)

    if not os.path.exists(generator_path):
        return TestResult(
            generator=generator,
            success=False,
            num_samples_requested=num_samples,
            num_samples_generated=0,
            duration_seconds=0,
            seconds_per_sample=0,
            peak_memory_mb=0,
            error=f"Generator not found: {generator_path}",
        )

    output_dir = output_base or f"./local_output/{generator}"
    output_path = Path(output_dir).resolve()  # Use absolute path

    # Clean up previous output
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Testing: {generator}")
    logger.info(f"  Samples: {num_samples}, Seed: {seed or 'random'}")

    start_time = time.perf_counter()
    try:
        generated, peak_memory = run_generator_with_memory_tracking(
            generator_path=generator_path,
            num_samples=num_samples,
            seed=seed,
            output_dir=str(output_path),
        )
    except Exception as e:
        logger.error(f"Generator failed: {e}")
        return TestResult(
            generator=generator,
            success=False,
            num_samples_requested=num_samples,
            num_samples_generated=0,
            duration_seconds=time.perf_counter() - start_time,
            seconds_per_sample=0,
            peak_memory_mb=0,
            error=str(e),
        )

    duration = time.perf_counter() - start_time

    # Find and validate samples
    validation_results = []
    questions_dir = find_task_directories(output_path)

    if questions_dir:
        for item in questions_dir.rglob("*"):
            if item.is_dir() and item.name.endswith("_task"):
                for sample_dir in sorted(item.iterdir()):
                    if sample_dir.is_dir():
                        result = validate_sample(sample_dir)
                        validation_results.append(result)

    seconds_per_sample = duration / generated if generated > 0 else 0

    result = TestResult(
        generator=generator,
        success=True,
        num_samples_requested=num_samples,
        num_samples_generated=generated,
        duration_seconds=duration,
        seconds_per_sample=seconds_per_sample,
        peak_memory_mb=peak_memory,
        validation_results=validation_results,
    )

    # Clean up unless --keep-output
    if not keep_output and output_path.exists():
        shutil.rmtree(output_path)

    return result


def print_result(result: TestResult, verbose: bool = False) -> None:
    """Print test result to console."""
    status = "PASS" if result.success else "FAIL"
    valid_count = sum(1 for v in result.validation_results if v.valid)
    total_count = len(result.validation_results)

    print(f"\n{'='*60}")
    print(f"Generator: {result.generator}")
    print(f"Status: {status}")
    print(f"{'='*60}")

    if result.error:
        print(f"Error: {result.error}")
        return

    print(f"Samples: {result.num_samples_generated}/{result.num_samples_requested}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Per Sample: {result.seconds_per_sample:.2f}s")
    print(f"Peak Memory: {result.peak_memory_mb:.1f} MB")
    print(f"Validation: {valid_count}/{total_count} valid")

    # Show validation issues
    invalid = [v for v in result.validation_results if not v.valid]
    if invalid:
        print("\nValidation Issues:")
        for v in invalid[:5]:
            print(f"  - {v.sample_id}: missing {v.missing_required}")
        if len(invalid) > 5:
            print(f"  ... and {len(invalid) - 5} more")

    if verbose and result.validation_results:
        first = result.validation_results[0]
        print(f"\nSample file sizes ({first.sample_id}):")
        for name, size in sorted(first.file_sizes.items()):
            print(f"  {name}: {size:,} bytes")


def print_summary(results: list[TestResult]) -> None:
    """Print summary table for multiple generators."""
    print(f"\n{'='*90}")
    print("SUMMARY")
    print(f"{'='*90}")
    header = f"{'Generator':<50} {'Status':<8} {'Samples':<10} {'Time':<10} {'Per Sample':<12} {'Memory':<10}"
    print(header)
    print("-" * 90)

    for r in results:
        status = "PASS" if r.success else "FAIL"
        samples = f"{r.num_samples_generated}/{r.num_samples_requested}"
        time_str = f"{r.duration_seconds:.2f}s"
        per_sample = f"{r.seconds_per_sample:.2f}s"
        memory = f"{r.peak_memory_mb:.1f}MB"
        print(f"{r.generator:<50} {status:<8} {samples:<10} {time_str:<10} {per_sample:<12} {memory:<10}")

    passed = sum(1 for r in results if r.success)
    print(f"\nTotal: {passed}/{len(results)} passed")


def main():
    parser = argparse.ArgumentParser(
        description="Test generators locally with validation and performance metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--generator",
        "-g",
        help="Generator name to test",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Test all available generators",
    )
    parser.add_argument(
        "--num-samples",
        "-n",
        type=int,
        default=3,
        help="Number of samples to generate (default: 3)",
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--keep-output",
        "-k",
        action="store_true",
        help="Keep output files after test (default: delete)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        help="Output directory (default: ./local_output/<generator>)",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available generators and exit",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output including file sizes",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    if args.list:
        generators = list_generators()
        if generators:
            print(f"Available generators ({len(generators)}):")
            for g in generators:
                print(f"  {g}")
        else:
            print(f"No generators found in {GENERATORS_PATH}")
            print("Run scripts/download_all_repos.sh to download generators")
        return

    if not args.generator and not args.all:
        parser.error("Either --generator or --all is required")

    generators = list_generators() if args.all else [args.generator]

    if not generators:
        print(f"No generators found in {GENERATORS_PATH}")
        sys.exit(1)

    results = []
    for gen in generators:
        result = test_generator(
            generator=gen,
            num_samples=args.num_samples,
            seed=args.seed,
            keep_output=args.keep_output,
            output_base=args.output_dir if not args.all else None,
        )
        results.append(result)

        if not args.json:
            print_result(result, verbose=args.verbose)

    if args.json:
        output = {
            "results": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
            },
        }
        print(json.dumps(output, indent=2))
    elif len(results) > 1:
        print_summary(results)

    if any(not r.success for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
