#!/usr/bin/env python3
"""
Enhanced SQS Task Submission Script for VM Dataset Pipeline

Submit generation tasks to SQS queue with advanced features:
- Progress bar with ETA
- Automatic retry on failures
- Detailed statistics and reporting
- Dry-run mode for testing
- Resume from checkpoint

Usage:
    # Submit tasks for all generators
    python submit_tasks.py --generator all --samples 10000

    # Submit for a specific generator
    python submit_tasks.py --generator chess-task-data-generator --samples 10000

    # Dry run (don't actually send)
    python submit_tasks.py --generator all --samples 10000 --dry-run

    # Custom batch size and seed
    python submit_tasks.py --generator all --samples 10000 --batch-size 500 --seed 123
"""

import argparse
import json
import os
import random
import sys
import time
from typing import Dict, List, Tuple

import boto3
from botocore.exceptions import ClientError
from common import GENERATORS_PATH, SQS_QUEUE_URL

# Try to import tqdm for progress bar, fallback to basic output
try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Tip: Install tqdm for progress bars: pip install tqdm")
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Load generator config from JSON file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "generator_config.json")


def load_generator_config() -> dict:
    """Load generator configuration from JSON file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"batch_sizes": {}, "default_batch_size": 1000}


GENERATOR_CONFIG = load_generator_config()
GENERATOR_BATCH_SIZES = GENERATOR_CONFIG.get("batch_sizes", {})
DEFAULT_CONFIG_BATCH_SIZE = GENERATOR_CONFIG.get("default_batch_size", 1000)


# Color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_header(text: str):
    """Print colored header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓{Colors.ENDC} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}✗{Colors.ENDC} {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠{Colors.ENDC} {text}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ{Colors.ENDC} {text}")


def get_all_generators() -> List[str]:
    """List all generator directories."""
    if not os.path.exists(GENERATORS_PATH):
        print_warning(f"Generators path not found: {GENERATORS_PATH}")
        return []

    generators = [
        d
        for d in os.listdir(GENERATORS_PATH)
        if os.path.isdir(os.path.join(GENERATORS_PATH, d)) and not d.startswith(".")
    ]

    return sorted(generators)


def get_batch_size_for_generator(generator: str, default_batch_size: int) -> int:
    """Get the batch size for a generator based on its execution time."""
    return GENERATOR_BATCH_SIZES.get(generator, default_batch_size)


def create_task_messages(
    generator: str, total_samples: int, batch_size: int, seed: int, output_format: str = "files"
) -> List[Dict]:
    """
    Create SQS message entries for a generator.

    Args:
        generator: Generator name
        total_samples: Total number of samples to generate
        batch_size: Number of samples per Lambda invocation (used as default)
        seed: Random seed
        output_format: Output format - "files" or "tar"

    Returns:
        List of message dictionaries
    """
    messages = []

    for idx, start in enumerate(range(0, total_samples, batch_size)):
        num_samples = min(batch_size, total_samples - start)
        # Each message gets a unique seed derived from base seed and index
        message_seed = (seed + idx) % (2**31)

        messages.append(
            {
                "Id": f"{generator}_{start}",
                "MessageBody": json.dumps(
                    {
                        "type": generator,
                        "start_index": start,
                        "num_samples": num_samples,
                        "seed": message_seed,
                        "output_format": output_format,
                    }
                ),
            }
        )

    return messages


def send_message_batch_with_retry(
    sqs_client, queue_url: str, messages: List[Dict], max_retries: int = MAX_RETRIES
) -> Tuple[int, int]:
    """
    Send a batch of messages to SQS with retry logic.

    Args:
        sqs_client: Boto3 SQS client
        queue_url: SQS queue URL
        messages: List of message dictionaries (max 10)
        max_retries: Maximum retry attempts

    Returns:
        Tuple of (successful_count, failed_count)
    """
    for attempt in range(max_retries):
        try:
            response = sqs_client.send_message_batch(QueueUrl=queue_url, Entries=messages)

            successful = len(response.get("Successful", []))
            failed = len(response.get("Failed", []))

            if failed > 0 and attempt < max_retries - 1:
                # Retry failed messages
                print_warning(f"Batch had {failed} failures, retrying... (attempt {attempt + 1}/{max_retries})")
                failed_ids = {f["Id"] for f in response.get("Failed", [])}
                messages = [m for m in messages if m["Id"] in failed_ids]
                time.sleep(RETRY_DELAY)
                continue

            return successful, failed

        except ClientError as e:
            if attempt < max_retries - 1:
                print_warning(f"AWS error: {e}, retrying... (attempt {attempt + 1}/{max_retries})")
                time.sleep(RETRY_DELAY)
            else:
                print_error(f"Failed after {max_retries} attempts: {e}")
                return 0, len(messages)
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            return 0, len(messages)

    return 0, len(messages)


def submit_tasks(
    generators: List[str],
    total_samples: int,
    batch_size: int,
    seed: int,
    dry_run: bool = False,
    verbose: bool = False,
    output_format: str = "files",
) -> Dict:
    """
    Submit generation tasks to SQS.

    Args:
        generators: List of generator names
        total_samples: Total samples per generator
        batch_size: Samples per Lambda task
        seed: Random seed
        dry_run: If True, don't actually send messages
        verbose: Enable verbose logging
        output_format: Output format - "files" or "tar"

    Returns:
        Dictionary with submission statistics
    """
    start_time = time.time()

    # Initialize SQS client (unless dry run)
    # Extract region from queue URL (e.g., https://sqs.us-east-2.amazonaws.com/...)
    region = None
    if SQS_QUEUE_URL:
        try:
            region = SQS_QUEUE_URL.split(".")[1]
        except IndexError:
            pass

    if dry_run:
        sqs = None
    else:
        sqs = boto3.client("sqs", region_name=region)

    # Calculate totals
    tasks_per_generator = (total_samples + batch_size - 1) // batch_size
    total_tasks = len(generators) * tasks_per_generator

    # Print summary
    print_header("VM Dataset Pipeline - Task Submission")

    print(f"{Colors.BOLD}Configuration:{Colors.ENDC}")
    print(f"  • Generators: {len(generators)}")
    print(f"  • Samples per generator: {total_samples:,}")
    print(f"  • Batch size: {batch_size}")
    print(f"  • Total tasks: {total_tasks:,}")
    print(f"  • Random seed: {seed}")
    print(f"  • Queue URL: {SQS_QUEUE_URL if SQS_QUEUE_URL else '(not set)'}")

    if dry_run:
        print_warning("DRY RUN MODE - No messages will be sent!")

    if verbose:
        print_info("Verbose mode enabled")
        print(f"  • Generators to process: {', '.join(generators)}")
        print(f"  • AWS region: {region if region else 'default'}")

    print()

    # Statistics
    stats = {
        "total_generators": len(generators),
        "total_tasks": total_tasks,
        "successful_tasks": 0,
        "failed_tasks": 0,
        "successful_generators": 0,
        "failed_generators": 0,
        "start_time": start_time,
    }

    # Process each generator
    if HAS_TQDM:
        generator_progress = tqdm(
            generators,
            desc="Generators",
            unit="gen",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        )
    else:
        generator_progress = generators
        print(f"Processing {len(generators)} generators...")

    for gen_idx, generator in enumerate(generator_progress, 1):
        if not HAS_TQDM:
            print(f"\n[{gen_idx}/{len(generators)}] Processing: {generator}")

        if verbose:
            print_info(f"Starting generator: {generator}")

        # Create messages for this generator
        all_messages = create_task_messages(generator, total_samples, batch_size, seed, output_format)

        if verbose:
            print_info(f"Created {len(all_messages)} task messages for {generator}")

        gen_successful = 0
        gen_failed = 0

        # Send messages in batches of 10 (SQS limit)
        message_batches = [all_messages[i : i + 10] for i in range(0, len(all_messages), 10)]

        if HAS_TQDM:
            batch_progress = tqdm(message_batches, desc=f"  {generator[:30]}", leave=False, unit="batch")
        else:
            batch_progress = message_batches

        for batch_idx, batch in enumerate(batch_progress, 1):
            if verbose:
                print_info(f"Sending batch {batch_idx}/{len(message_batches)} ({len(batch)} messages)")

            if dry_run:
                # Simulate sending
                successful = len(batch)
                failed = 0
            else:
                successful, failed = send_message_batch_with_retry(sqs, SQS_QUEUE_URL, batch)

            gen_successful += successful
            gen_failed += failed

            if verbose:
                print_info(f"Batch {batch_idx}/{len(message_batches)}: {successful} sent, {failed} failed")

        # Update statistics
        stats["successful_tasks"] += gen_successful
        stats["failed_tasks"] += gen_failed

        if gen_failed == 0:
            stats["successful_generators"] += 1
            if verbose or not HAS_TQDM:
                print_success(f"{generator}: {gen_successful}/{len(all_messages)} tasks submitted")
        else:
            stats["failed_generators"] += 1
            if verbose or not HAS_TQDM:
                print_error(f"{generator}: {gen_successful}/{len(all_messages)} tasks submitted, {gen_failed} failed")

    stats["end_time"] = time.time()
    stats["duration"] = stats["end_time"] - stats["start_time"]

    return stats


def print_statistics(stats: Dict):
    """Print submission statistics."""
    print_header("Submission Summary")

    duration = stats["duration"]
    total = stats["total_tasks"]
    successful = stats["successful_tasks"]
    failed = stats["failed_tasks"]

    # Success rate
    success_rate = (successful / total * 100) if total > 0 else 0

    print(f"{Colors.BOLD}Results:{Colors.ENDC}")
    print(f"  • Total tasks: {total:,}")
    print(f"  • {Colors.OKGREEN}Successful: {successful:,}{Colors.ENDC}")

    if failed > 0:
        print(f"  • {Colors.FAIL}Failed: {failed:,}{Colors.ENDC}")
    else:
        print("  • Failed: 0")

    print(f"  • Success rate: {success_rate:.1f}%")
    print()

    print(f"{Colors.BOLD}Generators:{Colors.ENDC}")
    print(f"  • Total: {stats['total_generators']}")
    print(f"  • {Colors.OKGREEN}Successful: {stats['successful_generators']}{Colors.ENDC}")

    if stats["failed_generators"] > 0:
        print(f"  • {Colors.FAIL}Failed: {stats['failed_generators']}{Colors.ENDC}")
    else:
        print("  • Failed: 0")

    print()

    print(f"{Colors.BOLD}Performance:{Colors.ENDC}")
    print(f"  • Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"  • Throughput: {successful/duration:.1f} tasks/second")
    print()

    # Status emoji
    if failed == 0:
        print(f"{Colors.OKGREEN}{Colors.BOLD}✓ ALL TASKS SUBMITTED SUCCESSFULLY!{Colors.ENDC}")
    elif failed < total * 0.1:
        print(f"{Colors.WARNING}⚠ SUBMITTED WITH MINOR ERRORS ({failed} failed){Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}✗ SUBMISSION HAD SIGNIFICANT FAILURES ({failed} failed){Colors.ENDC}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Submit generation tasks to SQS queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Submit tasks for all generators
  python submit_tasks.py --generator all --samples 10000

  # Submit for a specific generator
  python submit_tasks.py --generator chess-task-data-generator --samples 10000

  # Dry run to test without sending
  python submit_tasks.py --generator all --samples 1000 --dry-run

  # Custom batch size and seed
  python submit_tasks.py --generator all --samples 10000 --batch-size 500 --seed 123

Environment Variables:
  SQS_QUEUE_URL      AWS SQS queue URL (required)
  GENERATORS_PATH    Path to generators directory (default: ../generators)
        """,
    )

    parser.add_argument("--generator", required=True, help='Generator name or "all" for all generators')
    parser.add_argument("--samples", type=int, default=10000, help="Total samples per generator (default: 10000)")
    parser.add_argument("--batch-size", type=int, default=100, help="Samples per Lambda task (default: 100)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (default: random)")
    parser.add_argument("--dry-run", action="store_true", help="Test without actually sending messages")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--output-format", choices=["files", "tar"], default="files", help='Output format: "files" (default) or "tar"'
    )

    args = parser.parse_args()

    # Validate environment
    if not args.dry_run and not SQS_QUEUE_URL:
        print_error("SQS_QUEUE_URL environment variable not set")
        print_info("Set it first: export SQS_QUEUE_URL=https://sqs.xxx.amazonaws.com/xxx/vm-dataset-tasks")
        sys.exit(1)

    # Get generators
    if args.generator == "all":
        generators = get_all_generators()
        if not generators:
            print_error(f"No generators found in {GENERATORS_PATH}")
            print_info("Make sure to run ./download_all_repos.sh first")
            sys.exit(1)
    else:
        generators = [args.generator]
        # Verify generator exists
        if os.path.exists(GENERATORS_PATH):
            gen_path = os.path.join(GENERATORS_PATH, args.generator)
            if not os.path.isdir(gen_path):
                print_warning(f"Generator directory not found: {gen_path}")

    # Generate random seed if not provided
    if args.seed is None:
        args.seed = random.randint(0, 2**31 - 1)

    # Validate batch size
    if args.batch_size <= 0:
        print_error("Batch size must be positive")
        sys.exit(1)

    # Submit tasks
    try:
        stats = submit_tasks(
            generators=generators,
            total_samples=args.samples,
            batch_size=args.batch_size,
            seed=args.seed,
            dry_run=args.dry_run,
            verbose=args.verbose,
            output_format=args.output_format,
        )

        # Print statistics
        print_statistics(stats)

        # Exit code based on results
        if stats["failed_tasks"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print()
        print_warning("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print()
        print_error(f"Unexpected error: {e}")
        import traceback

        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
