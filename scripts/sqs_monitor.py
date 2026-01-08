#!/usr/bin/env python3
"""
SQS Queue Monitoring Tool

Monitor the status of SQS queues for VM Dataset Pipeline.

Usage:
    python sqs_monitor.py
    python sqs_monitor.py --watch  # Continuous monitoring
"""

import argparse
import os
import sys
import time
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')
SQS_DLQ_URL = os.environ.get('SQS_DLQ_URL', '')

# Colors
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_queue_stats(sqs_client, queue_url: str) -> dict:
    """Get queue statistics."""
    try:
        response = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                'ApproximateNumberOfMessages',
                'ApproximateNumberOfMessagesNotVisible',
                'ApproximateNumberOfMessagesDelayed'
            ]
        )
        
        attrs = response['Attributes']
        return {
            'available': int(attrs.get('ApproximateNumberOfMessages', 0)),
            'in_flight': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
            'delayed': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0))
        }
    except ClientError as e:
        print(f"Error getting queue stats: {e}")
        return {'available': 0, 'in_flight': 0, 'delayed': 0}


def print_queue_status(sqs_client, queue_url: str, queue_name: str):
    """Print queue status."""
    stats = get_queue_stats(sqs_client, queue_url)
    
    total = stats['available'] + stats['in_flight'] + stats['delayed']
    
    print(f"\n{Colors.BOLD}📊 {queue_name}{Colors.ENDC}")
    print(f"{'─' * 60}")
    
    # Available messages
    color = Colors.OKGREEN if stats['available'] > 0 else Colors.ENDC
    print(f"  Waiting:     {color}{stats['available']:>8,}{Colors.ENDC} messages")
    
    # In-flight messages
    color = Colors.WARNING if stats['in_flight'] > 0 else Colors.ENDC
    print(f"  Processing:  {color}{stats['in_flight']:>8,}{Colors.ENDC} messages")
    
    # Delayed messages
    if stats['delayed'] > 0:
        print(f"  Delayed:     {Colors.OKBLUE}{stats['delayed']:>8,}{Colors.ENDC} messages")
    
    print(f"  {Colors.BOLD}Total:       {total:>8,}{Colors.ENDC} messages")
    
    # Progress estimate
    if total > 0:
        progress = (stats['in_flight'] / total) * 100
        print(f"\n  Progress: {progress:.1f}% in flight")


def monitor_queues(watch: bool = False, interval: int = 10):
    """Monitor queue status."""
    sqs = boto3.client('sqs')
    
    if not SQS_QUEUE_URL:
        print(f"{Colors.FAIL}Error:{Colors.ENDC} SQS_QUEUE_URL not set")
        sys.exit(1)
    
    try:
        while True:
            if watch:
                clear_screen()
            
            print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
            print(f"{Colors.HEADER}{Colors.BOLD}VM Dataset Pipeline - Queue Monitor{Colors.ENDC}")
            print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
            print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Main queue
            print_queue_status(sqs, SQS_QUEUE_URL, "Main Queue (vm-dataset-tasks)")
            
            # DLQ if available
            if SQS_DLQ_URL:
                print_queue_status(sqs, SQS_DLQ_URL, "Dead Letter Queue")
            
            if not watch:
                break
            
            print(f"\n{Colors.ENDC}Refreshing in {interval} seconds... (Ctrl+C to exit)")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Monitoring stopped{Colors.ENDC}")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description='Monitor SQS queue status')
    parser.add_argument('--watch', '-w', action='store_true',
                        help='Continuous monitoring mode')
    parser.add_argument('--interval', '-i', type=int, default=10,
                        help='Refresh interval in seconds (default: 10)')
    
    args = parser.parse_args()
    
    monitor_queues(watch=args.watch, interval=args.interval)


if __name__ == '__main__':
    main()

