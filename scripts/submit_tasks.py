#!/usr/bin/env python3
"""
Submit generation tasks to SQS queue.

Usage:
    python submit_tasks.py --generator chess-task-data-generator --samples 10000
    python submit_tasks.py --generator all --samples 10000
"""

import argparse
import json
import os
import boto3

SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')
GENERATORS_PATH = os.environ.get('GENERATORS_PATH', '../generators')


def get_all_generators():
    """List all generator directories."""
    if not os.path.exists(GENERATORS_PATH):
        print(f"Warning: {GENERATORS_PATH} not found")
        return []
    return [d for d in os.listdir(GENERATORS_PATH)
            if os.path.isdir(os.path.join(GENERATORS_PATH, d))]


def submit_tasks(generator: str, total_samples: int, batch_size: int, seed: int):
    """Submit generation tasks to SQS."""
    sqs = boto3.client('sqs')

    if generator == 'all':
        generators = get_all_generators()
    else:
        generators = [generator]

    print(f"Submitting tasks for {len(generators)} generator(s)...")
    print(f"  Samples per generator: {total_samples}")
    print(f"  Batch size: {batch_size}")
    print(f"  Tasks per generator: {total_samples // batch_size}")
    print(f"  Total tasks: {len(generators) * (total_samples // batch_size)}")
    print()

    total_submitted = 0

    for gen in generators:
        messages = []

        for start in range(0, total_samples, batch_size):
            messages.append({
                'Id': f'{gen}_{start}',
                'MessageBody': json.dumps({
                    'type': gen,
                    'start_index': start,
                    'num_samples': min(batch_size, total_samples - start),
                    'seed': seed
                })
            })

            # SQS allows max 10 messages per batch
            if len(messages) == 10:
                sqs.send_message_batch(QueueUrl=SQS_QUEUE_URL, Entries=messages)
                total_submitted += len(messages)
                messages = []

        # Send remaining messages
        if messages:
            sqs.send_message_batch(QueueUrl=SQS_QUEUE_URL, Entries=messages)
            total_submitted += len(messages)

        print(f"  Submitted: {gen}")

    print()
    print(f"Done! Submitted {total_submitted} tasks to SQS")


def main():
    parser = argparse.ArgumentParser(description='Submit generation tasks to SQS')
    parser.add_argument('--generator', required=True,
                        help='Generator name or "all" for all generators')
    parser.add_argument('--samples', type=int, default=10000,
                        help='Total samples per generator (default: 10000)')
    parser.add_argument('--batch-size', type=int, default=1000,
                        help='Samples per Lambda task (default: 1000)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed (default: 42)')

    args = parser.parse_args()

    if not SQS_QUEUE_URL:
        print("Error: SQS_QUEUE_URL environment variable not set")
        print("Export it first: export SQS_QUEUE_URL=https://sqs.xxx.amazonaws.com/xxx/vm-dataset-tasks")
        exit(1)

    submit_tasks(args.generator, args.samples, args.batch_size, args.seed)


if __name__ == '__main__':
    main()
