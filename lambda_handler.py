import os
import sys
import json
import shutil
import subprocess
import boto3

s3 = boto3.client('s3')

OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'vm-dataset-outputs')
GENERATORS_PATH = '/opt/generators'


def handler(event, context):
    """
    Lambda handler for generating dataset samples.

    Expected event format (from SQS):
    {
        "type": "chess-task-data-generator",
        "start_index": 0,
        "num_samples": 1000,
        "seed": 42
    }
    """
    # Handle SQS batch
    records = event.get('Records', [event])

    for record in records:
        if 'body' in record:
            task = json.loads(record['body'])
        else:
            task = record

        process_task(task)

    return {'status': 'ok', 'processed': len(records)}


def process_task(task):
    """Process a single generation task."""
    task_type = task['type']
    start_index = task['start_index']
    num_samples = task['num_samples']
    seed = task['seed']

    generator_path = os.path.join(GENERATORS_PATH, task_type)
    output_dir = f'/tmp/output_{task_type}_{start_index}'

    # Run generator
    subprocess.run([
        sys.executable, 'examples/generate.py',
        '--num-samples', str(num_samples),
        '--start-index', str(start_index),
        '--seed', str(seed),
        '--output', output_dir
    ], cwd=generator_path, check=True)

    # Package output
    zip_name = f'{start_index:06d}_{start_index + num_samples - 1:06d}'
    zip_path = f'/tmp/{zip_name}'
    shutil.make_archive(zip_path, 'zip', output_dir)

    # Upload to S3
    s3_key = f'{task_type}/{zip_name}.zip'
    s3.upload_file(f'{zip_path}.zip', OUTPUT_BUCKET, s3_key)

    # Cleanup
    shutil.rmtree(output_dir, ignore_errors=True)
    os.remove(f'{zip_path}.zip')

    print(f'Completed: {task_type} [{start_index}-{start_index + num_samples - 1}]')
