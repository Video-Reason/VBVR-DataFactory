#!/usr/bin/env python3
"""
SQS Utility Functions

Common utilities for SQS operations.

Usage:
    python sqs_utils.py purge        # Clear all messages from queue
    python sqs_utils.py count        # Count messages
    python sqs_utils.py peek         # View a sample message
"""

import argparse
import json
import os
import sys
import boto3
from botocore.exceptions import ClientError

SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')


def purge_queue(queue_url: str, confirm: bool = True) -> bool:
    """
    Purge all messages from queue.
    
    Args:
        queue_url: SQS queue URL
        confirm: Require confirmation before purging
    
    Returns:
        True if successful
    """
    if confirm:
        print(f"⚠️  WARNING: This will delete ALL messages from the queue!")
        print(f"   Queue: {queue_url}")
        response = input("   Type 'yes' to confirm: ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return False
    
    sqs = boto3.client('sqs')
    
    try:
        sqs.purge_queue(QueueUrl=queue_url)
        print("✓ Queue purged successfully")
        return True
    except ClientError as e:
        print(f"✗ Error purging queue: {e}")
        return False


def count_messages(queue_url: str) -> dict:
    """Count messages in queue."""
    sqs = boto3.client('sqs')
    
    try:
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                'ApproximateNumberOfMessages',
                'ApproximateNumberOfMessagesNotVisible',
                'ApproximateNumberOfMessagesDelayed'
            ]
        )
        
        attrs = response['Attributes']
        counts = {
            'available': int(attrs.get('ApproximateNumberOfMessages', 0)),
            'in_flight': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
            'delayed': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0))
        }
        
        counts['total'] = counts['available'] + counts['in_flight'] + counts['delayed']
        
        print(f"Message Counts:")
        print(f"  Available:   {counts['available']:,}")
        print(f"  In-flight:   {counts['in_flight']:,}")
        print(f"  Delayed:     {counts['delayed']:,}")
        print(f"  Total:       {counts['total']:,}")
        
        return counts
        
    except ClientError as e:
        print(f"✗ Error counting messages: {e}")
        return {}


def peek_message(queue_url: str, delete: bool = False):
    """
    Peek at a message without removing it (or optionally remove it).
    
    Args:
        queue_url: SQS queue URL
        delete: If True, delete the message after reading
    """
    sqs = boto3.client('sqs')
    
    try:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=2
        )
        
        messages = response.get('Messages', [])
        
        if not messages:
            print("No messages available in queue")
            return
        
        message = messages[0]
        receipt_handle = message['ReceiptHandle']
        
        # Parse message body
        try:
            body = json.loads(message['Body'])
            print("Message Body:")
            print(json.dumps(body, indent=2))
        except json.JSONDecodeError:
            print("Message Body (raw):")
            print(message['Body'])
        
        # Message attributes
        print(f"\nMessage ID: {message['MessageId']}")
        print(f"MD5: {message['MD5OfBody']}")
        
        if delete:
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
            print("\n✓ Message deleted from queue")
        else:
            print("\n(Message will return to queue after visibility timeout)")
            
    except ClientError as e:
        print(f"✗ Error peeking at message: {e}")


def main():
    parser = argparse.ArgumentParser(description='SQS utility functions')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Purge command
    purge_parser = subparsers.add_parser('purge', help='Purge all messages from queue')
    purge_parser.add_argument('--force', action='store_true',
                             help='Skip confirmation prompt')
    
    # Count command
    subparsers.add_parser('count', help='Count messages in queue')
    
    # Peek command
    peek_parser = subparsers.add_parser('peek', help='View a sample message')
    peek_parser.add_argument('--delete', action='store_true',
                            help='Delete the message after viewing')
    
    args = parser.parse_args()
    
    if not SQS_QUEUE_URL:
        print("✗ Error: SQS_QUEUE_URL not set")
        print("  Set it: export SQS_QUEUE_URL=https://sqs.xxx.amazonaws.com/xxx/vm-dataset-tasks")
        sys.exit(1)
    
    if args.command == 'purge':
        purge_queue(SQS_QUEUE_URL, confirm=not args.force)
    elif args.command == 'count':
        count_messages(SQS_QUEUE_URL)
    elif args.command == 'peek':
        peek_message(SQS_QUEUE_URL, delete=args.delete)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

