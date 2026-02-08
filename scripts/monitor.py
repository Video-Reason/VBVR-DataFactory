#!/usr/bin/env python3
"""Monitor SQS queue status using vbvrdatafactory package.

Example:
    python scripts/monitor.py
    python scripts/monitor.py --watch --interval 5
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vbvrdatafactory.core.config import config
from vbvrdatafactory.sqs.monitor import QueueMonitor


def clear_screen():
    """Clear terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def print_queue_status(stats: dict, name: str):
    """Print queue status."""
    print(f"\n📊 {name}")
    print("─" * 60)
    print(f"  Waiting:     {stats['available']:>8,} messages")
    print(f"  Processing:  {stats['in_flight']:>8,} messages")
    print(f"  Delayed:     {stats['delayed']:>8,} messages")

    total = stats["available"] + stats["in_flight"] + stats["delayed"]
    print(f"  Total:       {total:>8,} messages")

    if total > 0 and stats["in_flight"] > 0:
        progress = (stats["in_flight"] / total) * 100
        print(f"\n  Progress: {progress:.1f}% in flight")


def main():
    parser = argparse.ArgumentParser(description="Monitor SQS queue status")
    parser.add_argument("--watch", "-w", action="store_true", help="Continuous monitoring mode")
    parser.add_argument("--interval", "-i", type=int, default=10, help="Refresh interval in seconds (default: 10)")

    args = parser.parse_args()

    if not config.sqs_queue_url:
        print("❌ SQS_QUEUE_URL environment variable not set")
        sys.exit(1)

    monitor = QueueMonitor(config.sqs_queue_url, config.sqs_dlq_url)

    while True:
        if args.watch:
            clear_screen()

        print("\n" + "=" * 60)
        print("VBVR-DataFactory - Queue Monitor")
        print("=" * 60)
        print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        status = monitor.get_status()

        # Main queue
        print_queue_status(status["main_queue"], "Main Queue")

        # DLQ if available
        if status["dlq"]:
            print_queue_status(status["dlq"], "Dead Letter Queue")

        if not args.watch:
            break

        print(f"\nRefreshing in {args.interval} seconds... (Ctrl+C to exit)")
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoring stopped")
        sys.exit(0)

