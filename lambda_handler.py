import os
import sys
import json
import shutil
import subprocess
import re
import gc
import tarfile
import boto3
from pathlib import Path

# Initialize S3 client with default region
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-2'))

OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'vm-dataset-test')
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
    results = []

    for record in records:
        try:
            if 'body' in record:
                task = json.loads(record['body'])
            else:
                task = record

            result = process_task(task)
            results.append(result)
        except Exception as e:
            print(f"Error processing record: {e}")
            raise

    return {'status': 'ok', 'processed': len(records), 'results': results}


def process_task(task):
    """Process a single generation task."""
    task_type = task['type']
    num_samples = task['num_samples']
    start_index = task.get('start_index', 0)  # Starting index for task IDs
    seed = task.get('seed')  # Optional seed parameter
    
    # For large batches, process in smaller chunks to avoid memory issues
    BATCH_SIZE = 100  # Process 100 samples at a time
    total_uploaded = 0
    all_sample_ids = []
    all_tar_files = []

    if num_samples > BATCH_SIZE:
        print(f"Large batch detected ({num_samples} samples). Processing in batches of {BATCH_SIZE}")
        
        for batch_start in range(0, num_samples, BATCH_SIZE):
            batch_size = min(BATCH_SIZE, num_samples - batch_start)
            batch_start_index = start_index + batch_start
            
            print(f"Processing batch: {batch_start}/{num_samples} (samples {batch_start_index} to {batch_start_index + batch_size - 1})")
            
            # Process this batch
            batch_result = process_batch(
                task_type=task_type,
                num_samples=batch_size,
                start_index=batch_start_index,
                seed=seed,
                batch_num=batch_start // BATCH_SIZE
            )
            
            total_uploaded += batch_result['samples_uploaded']
            all_sample_ids.extend(batch_result['sample_ids'])
            if batch_result.get('tar_file'):
                all_tar_files.append(batch_result['tar_file'])

            # Force garbage collection after each batch
            gc.collect()
            print(f"Batch complete. Total uploaded so far: {total_uploaded}/{num_samples}")
        
        return {
            'generator': task_type,
            'samples_uploaded': total_uploaded,
            'sample_ids': all_sample_ids,
            'tar_files': all_tar_files
        }
    else:
        # Small batch, process normally
        result = process_batch(task_type, num_samples, start_index, seed, 0)
        # Convert single tar_file to tar_files list for consistency
        if result.get('tar_file'):
            result['tar_files'] = [result.pop('tar_file')]
        return result


def process_batch(task_type, num_samples, start_index, seed, batch_num):
    """Process a single batch of samples."""
    # Find generator directory
    generator_path = os.path.join(GENERATORS_PATH, task_type)
    if not os.path.exists(generator_path):
        raise ValueError(f"Generator not found: {task_type} at {generator_path}")
    
    # Use batch-specific output directory to avoid conflicts
    output_dir = f'/tmp/output_{task_type}_{os.getpid()}_batch{batch_num}'
    
    # Build command: python examples/generate.py --num-samples {num_samples}
    cmd = [sys.executable, 'examples/generate.py', '--num-samples', str(num_samples)]
    
    # Add seed if provided (adjust seed for each batch to maintain reproducibility)
    if seed is not None:
        # Use different seed for each batch to maintain overall reproducibility
        batch_seed = seed + batch_num * 10000 if seed is not None else None
        cmd.extend(['--seed', str(batch_seed)])
    
    # Add output directory
    cmd.extend(['--output', output_dir])
    
    print(f"Running command: {' '.join(cmd)}")
    print(f"Working directory: {generator_path}")
    
    # Run generator
    try:
        result = subprocess.run(
            cmd,
            cwd=generator_path,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Generator completed successfully")
        if result.stdout:
            print(f"Generator stdout (first 500 chars): {result.stdout[:500]}")
        if result.stderr:
            print(f"Generator stderr (first 500 chars): {result.stderr[:500]}")
    except subprocess.CalledProcessError as e:
        print(f"Generator failed with return code {e.returncode}")
        print(f"stdout: {e.stdout[:1000] if e.stdout else 'None'}")
        print(f"stderr: {e.stderr[:1000] if e.stderr else 'None'}")
        print(f"Command that failed: {' '.join(cmd)}")
        print(f"Working directory: {generator_path}")
        raise
    
    # Check output directory (minimal logging to save memory)
    output_path = Path(output_dir)
    print(f"Checking output directory: {output_dir}")
    print(f"Output directory exists: {output_path.exists()}")
    
    # Find generated task directories (avoid listing all files to save memory)
    # Based on OutputWriter, files are created at: output_dir/{domain}_task/{task_id}/
    # We need to search recursively for _task directories
    
    questions_dir = None
    
    # First, try to find _task directories directly under output_path
    # Use iterator to avoid loading all paths into memory
    print(f"Searching for _task directories in: {output_path}")
    if output_path.exists():
        # Look for _task directories recursively using iterator
        _task_iterator = output_path.rglob('*_task')
        for item in _task_iterator:
            if item.is_dir():
                print(f"Found _task directory at: {item}")
                # Use the parent directory as base (which should contain the _task dirs)
                questions_dir = item.parent
                print(f"Using base directory: {questions_dir}")
                break
        
        # If not found by _task pattern, try finding by task files (limit search depth)
        if not questions_dir:
            print(f"Searching for task files (png/txt/mp4) in: {output_path}")
            # Limit search to avoid memory issues - only check first few files
            file_iterator = output_path.rglob('*')
            checked = 0
            max_checks = 100  # Limit initial search
            for item in file_iterator:
                if checked >= max_checks:
                    break
                checked += 1
                if item.is_file() and item.suffix in ['.png', '.txt', '.mp4']:
                    # Found a task file, find the _task directory in its path
                    current = item.parent
                    while current != output_path.parent and current != output_path:
                        if current.name.endswith('_task'):
                            questions_dir = current.parent
                            print(f"Found _task via file {item}, using base: {questions_dir}")
                            break
                        current = current.parent
                    if questions_dir:
                        break
    
    # Fallback: use output_path directly
    if not questions_dir:
        print(f"Using output_path as fallback: {output_path}")
        questions_dir = output_path
    
    uploaded_samples = []
    tar_file = None

    if questions_dir and questions_dir.exists():
        print(f"Using questions directory: {questions_dir}")
        # Find all domain_task directories (recursively if needed)
        # Process files one by one to minimize memory usage
        found_any = False
        
        # Use rglob iterator to avoid loading all paths into memory
        for item in questions_dir.rglob('*'):
            if item.is_dir() and item.name.endswith('_task'):
                domain_task_dir = item
                print(f"Found domain_task directory: {domain_task_dir}")
                
                # Process each task_id directory immediately
                try:
                    task_dirs = list(domain_task_dir.iterdir())
                    # Sort task directories to ensure consistent ordering
                    # Extract numeric part for sorting if possible
                    def get_sort_key(path):
                        name = path.name
                        # Try to extract number from task ID (e.g., "task_0" -> 0, "0" -> 0)
                        try:
                            # Try to extract last number from the name
                            numbers = re.findall(r'\d+', name)
                            if numbers:
                                return int(numbers[-1])
                        except:
                            pass
                        return name  # Fallback to string sort
                    
                    task_dirs.sort(key=get_sort_key)
                except Exception as e:
                    print(f"Error listing task dirs in {domain_task_dir}: {e}")
                    continue
                
                # Process tasks in order, mapping to global IDs starting from start_index
                local_index = 0
                renamed_samples = []

                for task_id_dir in task_dirs:
                    if not task_id_dir.is_dir():
                        continue

                    original_task_id = task_id_dir.name

                    # Quick check if directory has task files (without loading all)
                    has_files = False
                    try:
                        for _ in task_id_dir.glob('*.png'):
                            has_files = True
                            break
                        if not has_files:
                            for _ in task_id_dir.glob('*.txt'):
                                has_files = True
                                break
                        if not has_files:
                            for _ in task_id_dir.glob('*.mp4'):
                                has_files = True
                                break
                    except Exception as e:
                        print(f"Error checking files in {task_id_dir}: {e}")
                        continue

                    if not has_files:
                        print(f"Skipping empty directory: {task_id_dir}")
                        # Clean up empty directory
                        try:
                            task_id_dir.rmdir()
                        except:
                            pass
                        continue

                    # Only map to global ID if directory has files
                    # Map to global ID: start_index + local_index
                    global_task_id_int = start_index + local_index
                    # Format as zero-padded 5-digit string (e.g., 1 -> "00001", 12 -> "00012", 123 -> "00123")
                    sample_id = f"{global_task_id_int:05d}"

                    print(f"Mapping local task {original_task_id} to global ID {sample_id} (start_index={start_index})")

                    # Rename directory to global sample_id
                    new_dir = task_id_dir.parent / sample_id
                    try:
                        task_id_dir.rename(new_dir)
                        renamed_samples.append(sample_id)
                        local_index += 1
                        found_any = True
                        print(f"Renamed {original_task_id} to {sample_id}")
                    except Exception as e:
                        print(f"Error renaming {task_id_dir} to {new_dir}: {e}")
                        raise

                # After renaming all directories, create tar archive and upload
                if renamed_samples:
                    end_index = start_index + len(renamed_samples) - 1
                    tar_filename = f"{task_type}_{start_index}_{end_index}.tar.gz"
                    tar_path = f"/tmp/{tar_filename}"

                    # Create tar archive from domain_task_dir
                    try:
                        create_tar_archive(str(domain_task_dir), tar_path)

                        # Upload to S3
                        s3_key = f"data/v1/{task_type}/{tar_filename}"
                        upload_tar_to_s3(tar_path, OUTPUT_BUCKET, s3_key)

                        # Record uploaded samples
                        for sample_id in renamed_samples:
                            uploaded_samples.append({
                                'sample_id': sample_id,
                                'files_uploaded': 0  # Files are in tar now
                            })

                        print(f"Created and uploaded tar with {len(renamed_samples)} samples")
                        tar_file = tar_filename

                        # Force garbage collection
                        gc.collect()
                    except Exception as e:
                        print(f"Error creating/uploading tar: {e}")
                        raise
        
        if not found_any:
            print(f"Warning: No task directories with files found in {questions_dir}")
            raise ValueError(f"No task files found in output directory: {questions_dir}")
    else:
        # Simplified error message to save memory
        error_msg = f"Cannot process output: questions_dir={questions_dir}\n"
        error_msg += f"Output directory exists: {output_path.exists()}\n"
        if not output_path.exists():
            error_msg += f"Output directory {output_dir} does not exist.\n"
        error_msg += f"This usually means the generator did not produce any output files.\n"
        print(error_msg)
        raise ValueError(error_msg)
    
    # Cleanup - remove entire output directory
    try:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
            print(f"Cleaned up output directory: {output_dir}")
    except Exception as e:
        print(f"Warning: Failed to clean up {output_dir}: {e}")
    
    # Force final garbage collection
    gc.collect()
    
    print(f"Batch complete: uploaded {len(uploaded_samples)} samples")
    
    return {
        'generator': task_type,
        'samples_uploaded': len(uploaded_samples),
        'sample_ids': [s['sample_id'] for s in uploaded_samples],
        'tar_file': tar_file
    }


def upload_directory_to_s3(local_dir, bucket, s3_prefix):
    """
    Upload all files in a directory to S3, deleting each file after successful upload.
    This helps reduce memory usage by freeing up disk space immediately.
    
    Args:
        local_dir: Path to local directory
        bucket: S3 bucket name
        s3_prefix: S3 key prefix (e.g., "data/v1/generator_name/sample_id/")
    
    Returns:
        Number of files uploaded
    """
    local_path = Path(local_dir)
    upload_count = 0
    files_to_delete = []
    
    # First pass: collect all files and upload them
    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            # Get relative path from local_dir
            relative_path = file_path.relative_to(local_path)
            s3_key = s3_prefix + str(relative_path).replace('\\', '/')
            
            # Upload file
            try:
                s3.upload_file(str(file_path), bucket, s3_key)
                upload_count += 1
                print(f"Uploaded: s3://{bucket}/{s3_key}")
                # Mark file for deletion after successful upload
                files_to_delete.append(file_path)
            except Exception as e:
                print(f"Error uploading {file_path} to s3://{bucket}/{s3_key}: {e}")
                raise
    
    # Second pass: delete uploaded files to free memory/disk space
    for file_path in files_to_delete:
        try:
            file_path.unlink()
            print(f"Deleted local file: {file_path}")
        except Exception as e:
            print(f"Warning: Failed to delete {file_path}: {e}")
    
    return upload_count


def create_tar_archive(source_dir, tar_path):
    """
    Create a tar.gz archive from a directory.

    Args:
        source_dir: Path to the source directory to archive
        tar_path: Path where the tar.gz file will be created

    Returns:
        Path to the created tar.gz file
    """
    source_path = Path(source_dir)
    with tarfile.open(tar_path, 'w:gz') as tar:
        for item in source_path.iterdir():
            tar.add(str(item), arcname=item.name)
    print(f"Created tar archive: {tar_path}")
    return tar_path


def upload_tar_to_s3(tar_path, bucket, s3_key):
    """
    Upload a tar file to S3 and delete the local file after successful upload.

    Args:
        tar_path: Path to the local tar file
        bucket: S3 bucket name
        s3_key: S3 key (full path including filename)

    Returns:
        S3 URI of the uploaded file
    """
    s3.upload_file(str(tar_path), bucket, s3_key)
    s3_uri = f"s3://{bucket}/{s3_key}"
    print(f"Uploaded tar to: {s3_uri}")

    # Clean up local tar file
    try:
        os.remove(tar_path)
        print(f"Deleted local tar file: {tar_path}")
    except Exception as e:
        print(f"Warning: Failed to delete local tar file {tar_path}: {e}")

    return s3_uri
