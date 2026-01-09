# vm-dataset-pipeline

Distributed data generation system for vm-dataset generators using AWS Lambda.

## Overview

- **50 generators** from vm-dataset organization
- **10K samples** per generator
- **500K total samples**

## Architecture

```
Docker Image (all code + dependencies)
        │
        ▼
ECR ──▶ Lambda (15min timeout) ◀── SQS
                      │
                      ▼
                   S3 Output
```

## Project Structure

```
vm-dataset-pipeline/
├── src/                          # Lambda code
│   ├── __init__.py
│   ├── config.py                 # Configuration (.env support)
│   ├── handler.py                # Lambda entry point
│   ├── generator.py              # Generator execution + retry logic
│   ├── uploader.py               # S3 upload (tar / direct)
│   └── utils.py                  # Utility functions
│
├── cdk/                          # CDK infrastructure
│   ├── app.py                    # CDK entry point
│   └── stacks/
│       └── pipeline_stack.py     # Lambda, SQS, S3 resource definitions
│
├── tests/                        # Tests
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_generator.py
│   │   ├── test_uploader.py
│   │   └── test_utils.py
│   └── cdk/
│       └── test_stack.py
│
├── generators/                   # Generator code (gitignored)
├── scripts/                      # Utility scripts
│   ├── common.py                 # Shared config (.env support)
│   ├── submit_tasks.py           # Submit tasks to SQS
│   ├── sqs_monitor.py            # Monitor queue status
│   ├── sqs_utils.py              # SQS tools (purge/count/peek)
│   ├── download_dlq_messages.py  # Download DLQ messages
│   └── push_dlq_to_sqs.py        # Resend DLQ messages
├── Dockerfile                    # Lambda container image
├── pyproject.toml                # UV + Python project config
├── cdk.json                      # CDK config
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- [UV](https://github.com/astral-sh/uv) package manager
- [AWS CLI](https://aws.amazon.com/cli/) configured
- [GitHub CLI](https://cli.github.com/) (for downloading generator repos)
- Docker

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install AWS CLI (macOS)
brew install awscli
# For other platforms, see: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

# Configure AWS credentials
aws configure
# Or use named profile:
aws configure --profile your-profile-name

# Install GitHub CLI (macOS)
brew install gh
# For other platforms, see: https://cli.github.com/

# Authenticate GitHub CLI
gh auth login
```

> **Note**: CDK is installed automatically via `uv sync --extra cdk`, no separate installation needed.

### 1. Setup Development Environment

```bash
# Clone this repo
git clone https://github.com/your-org/vm-dataset-pipeline
cd vm-dataset-pipeline

# Install dependencies with UV
uv sync --extra dev --extra cdk

# Install pre-commit hooks
uv run pre-commit install

# Setup environment variables
cp .env.example .env
# Edit .env with your settings:
#   AWS_PROFILE=your-profile-name  (if using named profile)
#   SQS_QUEUE_URL=...              (after CDK deploy)

# Download all generator repos
cd scripts
./download_all_repos.sh
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OUTPUT_BUCKET` | Yes | - | S3 bucket for output data |
| `AWS_REGION` | No | `us-east-2` | AWS region |
| `AWS_PROFILE` | No | - | AWS CLI profile name |
| `GENERATORS_PATH` | No | `/opt/generators` | Path to generators |
| `SQS_QUEUE_URL` | No | - | SQS queue URL (for scripts) |
| `SQS_DLQ_URL` | No | - | SQS Dead Letter Queue URL (for monitoring) |

### 2. Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src

# Run specific test file
uv run pytest tests/unit/test_utils.py -v
```

### 3. Deploy with CDK

> **Note**: CDK doesn't read `.env` file. Use `--profile` flag or set `AWS_PROFILE` environment variable.

```bash
# Set AWS profile (or use --profile flag for each command)
export AWS_PROFILE=your-profile-name

# Bootstrap CDK (first time only)
uv run cdk bootstrap

# Deploy stack (builds Docker image automatically)
uv run cdk deploy

# Destroy stack
uv run cdk destroy
```

After deploy, update `.env` with the output values:
```bash
SQS_QUEUE_URL=https://sqs.us-east-2.amazonaws.com/xxx/vm-dataset-pipeline-queue
SQS_DLQ_URL=https://sqs.us-east-2.amazonaws.com/xxx/vm-dataset-pipeline-dlq
```

### 4. Update Lambda (After Code Changes)

After modifying code in `src/`, redeploy to update Lambda:

```bash
uv run cdk deploy
```

This rebuilds the Docker image and updates the Lambda function automatically.

### 5. Submit Tasks

```bash
export SQS_QUEUE_URL=https://sqs.xxx.amazonaws.com/xxx/vm-dataset-pipeline-queue

# Submit tasks for all generators
python scripts/submit_tasks.py --generator all --samples 10000

# Or submit for a specific generator
python scripts/submit_tasks.py --generator chess-task-data-generator --samples 10000
```

### 6. Download Results

```bash
aws s3 sync s3://vm-dataset-xxx ./results
```

## UV Commands

```bash
uv sync                    # Install dependencies
uv sync --extra dev        # Install dev dependencies
uv sync --extra cdk        # Install CDK dependencies
uv run pytest              # Run tests
uv run cdk synth           # Generate CloudFormation template
uv run cdk deploy          # Deploy CDK
```

## Scripts

All scripts support `.env` file configuration.

### submit_tasks.py - Submit Tasks

```bash
# Submit all generators
python scripts/submit_tasks.py --generator all --samples 10000

# Submit single generator
python scripts/submit_tasks.py --generator chess-task-data-generator --samples 10000

# Dry run (no actual send)
python scripts/submit_tasks.py --generator all --samples 1000 --dry-run
```

### sqs_monitor.py - Monitor Queue

```bash
# View queue status
python scripts/sqs_monitor.py

# Continuous monitoring
python scripts/sqs_monitor.py --watch
```

### sqs_utils.py - SQS Tools

```bash
# Count messages
python scripts/sqs_utils.py count

# Peek at a message
python scripts/sqs_utils.py peek

# Purge queue
python scripts/sqs_utils.py purge
```

### DLQ Handling

```bash
# Download DLQ messages to local directory
python scripts/download_dlq_messages.py --output DLQ

# Resend DLQ messages (seed will be randomly generated)
python scripts/push_dlq_to_sqs.py --dlq-dir DLQ

# Dry run
python scripts/push_dlq_to_sqs.py --dlq-dir DLQ --dry-run
```

## Configuration

### Lambda

| Parameter | Value |
|-----------|-------|
| Memory | 10 GB |
| Timeout | 15 minutes (900s) |

### SQS

| Parameter | Value |
|-----------|-------|
| Visibility Timeout | 960 seconds (16 min) |
| Max Retries | 3 |

### Task Format

```json
{
  "type": "chess-task-data-generator",
  "start_index": 0,
  "num_samples": 100,
  "seed": 42,
  "output_format": "files"
}
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `type` | Yes | - | Generator name |
| `start_index` | No | `0` | Starting index for global sample IDs |
| `num_samples` | Yes | - | Number of samples to generate (recommended <= 100) |
| `seed` | No | random | Random seed (Lambda generates if not provided) |
| `output_format` | No | `"files"` | `"files"` for individual files, `"tar"` for tar.gz archive |

## Output Structure

Each generator produces samples in the following structure:

```
data/questions/{domain}_task/{task_id}/
├── first_frame.png      # Initial state image (REQUIRED)
├── final_frame.png      # Target state image (OPTIONAL but recommended)
├── prompt.txt           # Task prompt (REQUIRED)
├── rubric.txt           # Scoring rubric (REQUIRED)
└── ground_truth.mp4     # Solution video (OPTIONAL)
```

Lambda renames `task_id` with global index based on `start_index`, so S3 output will be:

```
s3://vm-dataset-xxx/data/v1/{generator}/{global_task_id}/...
```

Or when using tar mode:

```
s3://vm-dataset-xxx/data/v1/{generator}/{generator}_{start}_{end}.tar.gz
```
