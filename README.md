# vm-dataset-pipeline

Distributed data generation system for vm-dataset generators using AWS Lambda.

## Overview

- **200 generators** from vm-dataset organization
- **10K samples** per generator
- **2 million total samples**
- **~4 minutes** to generate all (with 1000 Lambda concurrency)

## Architecture

```
Docker Image (all code + dependencies)
        │
        ▼
ECR ──▶ Lambda (1000 concurrency, 15min timeout) ◀── SQS
                      │
                      ▼
                   S3 Output
```

## Quick Start

### 1. Setup

```bash
# Clone this repo
gh repo clone vm-dataset-pipeline
cd vm-dataset-pipeline

# Download all generator repos
cd scripts
./download_all_repos.sh
```

### 2. Build & Push Docker Image

```bash
# Set AWS credentials
export AWS_ACCOUNT_ID=your-account-id
export AWS_REGION=us-west-2

# Build and push
./build_and_push.sh
```

### 3. Create AWS Resources

**SQS Queue:**
- Name: `vm-dataset-tasks`
- Visibility Timeout: 900 seconds
- Dead Letter Queue: `vm-dataset-tasks-dlq`

**S3 Bucket:**
- Name: `vm-dataset-outputs`

**Lambda Function:**
- Name: `vm-dataset-generator`
- Image: ECR `vm-dataset-generator:latest`
- Memory: 1024 MB
- Timeout: 15 minutes
- Concurrency: 1000
- Trigger: SQS `vm-dataset-tasks`
- Environment: `OUTPUT_BUCKET=vm-dataset-outputs`

### 4. Submit Tasks

```bash
export SQS_QUEUE_URL=https://sqs.xxx.amazonaws.com/xxx/vm-dataset-tasks

# Submit tasks for all generators
python submit_tasks.py --generator all --samples 10000 --batch-size 1000

# Or submit for a specific generator
python submit_tasks.py --generator chess-task-data-generator --samples 10000
```

### 5. Download Results

```bash
aws s3 sync s3://vm-dataset-outputs ./results
```

## Configuration

### Lambda

| Parameter | Value |
|-----------|-------|
| Memory | 1024 MB |
| Timeout | 15 minutes (900s) |
| Concurrency | 1000 |

### SQS

| Parameter | Value |
|-----------|-------|
| Visibility Timeout | 900 seconds |
| Max Retries | 3 |

### Task Format

```json
{
  "type": "chess-task-data-generator",
  "start_index": 0,
  "num_samples": 1000,
  "seed": 42
}
```

## Cost Estimate

| Item | Cost |
|------|------|
| Lambda (2M samples × 2s × 1GB) | ~$35 |
| S3 Storage (~340GB) | ~$8/month |
| SQS (2K messages) | <$0.01 |
| ECR (~3GB image) | ~$0.30/month |

## Generator Code Changes Required

Each generator's `core/base_generator.py` needs:

1. Add `start_index` parameter support
2. Use per-task seed: `random.seed(base_seed + index)`

## File Structure

```
vm-dataset-pipeline/
├── Dockerfile
├── requirements-all.txt
├── lambda_handler.py
├── generators/              # Downloaded repos (gitignored)
│   ├── chess-task-data-generator/
│   ├── maze-data-generator/
│   └── ...
└── scripts/
    ├── download_all_repos.sh
    ├── collect_requirements.sh
    ├── build_and_push.sh
    └── submit_tasks.py
```
