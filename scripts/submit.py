#!/usr/bin/env python3
"""Submit generation tasks to SQS using vmdatawheel package.

Example:
    python scripts/submit.py --generator all --samples 10000
    python scripts/submit.py --generator chess-task-data-generator --samples 1000 --batch-size 100
"""

import argparse
import os
import random
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vmdatawheel.core.config import config
from vmdatawheel.sqs.submitter import TaskSubmitter


def get_all_generators() -> list[str]:
    """List all generator directories."""
    generators_path = Path(config.generators_path)
    if not generators_path.exists():
        print(f"❌ Generators path not found: {generators_path}")
        return []

    generators = [
        d.name
        for d in generators_path.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "examples" / "generate.py").exists()
    ]

    return sorted(generators)


def main():
    parser = argparse.ArgumentParser(
        description="Submit generation tasks to SQS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--generator", "-g", required=True, help='Generator name or "all" for all generators')
    parser.add_argument("--samples", "-n", type=int, default=10000, help="Total samples per generator (default: 10000)")
    parser.add_argument("--batch-size", "-b", type=int, default=100, help="Samples per Lambda task (default: 100)")
    parser.add_argument("--seed", "-s", type=int, default=None, help="Random seed (default: random)")
    parser.add_argument(
        "--output-format", choices=["files", "tar"], default="files", help='Output format: "files" (default) or "tar"'
    )
    parser.add_argument("--bucket", help="Override S3 bucket for output")

    args = parser.parse_args()

    # Validate environment
    if not config.sqs_queue_url:
        print("❌ SQS_QUEUE_URL environment variable not set")
        print("   Set it first: export SQS_QUEUE_URL=https://sqs.xxx.amazonaws.com/xxx/vm-dataset-tasks")
        sys.exit(1)

    # Get generators
    if args.generator == "all":
        generators = get_all_generators()
        if not generators:
            print(f"❌ No generators found in {config.generators_path}")
            print("   Make sure to run ./download_all_repos.sh first")
            sys.exit(1)
    else:
        generators = [args.generator]
        gen_path = Path(config.generators_path) / args.generator
        if not gen_path.exists():
            print(f"⚠️  Warning: Generator directory not found: {gen_path}")

    # Generate random seed if not provided
    if args.seed is None:
        args.seed = random.randint(0, 2**31 - 1)

    # Submit tasks
    print("\n" + "=" * 70)
    print("VMDataWheel - Task Submission")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Generators: {len(generators)}")
    print(f"  Samples per generator: {args.samples:,}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Random seed: {args.seed}")
    print(f"  Queue URL: {config.sqs_queue_url}")
    print()

    submitter = TaskSubmitter(config.sqs_queue_url)

    result = submitter.submit_tasks(
        generators=generators,
        total_samples=args.samples,
        batch_size=args.batch_size,
        seed=args.seed,
        output_format=args.output_format,
        output_bucket=args.bucket,
    )

    # Print results
    print("\n" + "=" * 70)
    print("Submission Summary")
    print("=" * 70)
    print(f"\nResults:")
    print(f"  Total tasks: {result['total_successful'] + result['total_failed']:,}")
    print(f"  ✅ Successful: {result['total_successful']:,}")
    print(f"  ❌ Failed: {result['total_failed']:,}")
    print(f"\nGenerators:")
    print(f"  Total: {result['total_generators']}")
    print(f"  ✅ Successful: {result['total_generators'] - len(result['failed_generators'])}")
    print(f"  ❌ Failed: {len(result['failed_generators'])}")

    if result['failed_generators']:
        print(f"\nFailed generators:")
        for gen in result['failed_generators']:
            print(f"  - {gen}")

    print()

    if result["total_failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

