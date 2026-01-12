<h1 align="center">VM Data Wheel</h1>

<p align="center">
  <b>Scalable data generation for video reasoning models using AWS Lambda.</b>
</p>

<p align="center">
  <a href="https://github.com/vm-dataset">
    <img alt="vm-dataset generators" src="https://img.shields.io/badge/generators-vm--dataset-181717?logo=github&logoColor=white" />
  </a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-3776ab?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/license-Apache%202.0-green" />
  <img alt="AWS Lambda" src="https://img.shields.io/badge/AWS-Lambda-FF9900?logo=awslambda&logoColor=white" />
</p>

<p align="center">
  <a href="#one-click-deploy">Deploy</a> •
  <a href="#what-is-vm-data-wheel">About</a> •
  <a href="#-getting-started">Quick Start</a> •
  <a href="#-architecture-overview">Docs</a>
</p>

---

<div align="center">

## One-Click Deploy

**Deploy to your AWS account in minutes — no local setup required.**

**🔜 Coming Soon**

<!-- 
<a href="https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=vm-data-wheel&templateURL=https://raw.githubusercontent.com/Video-Reason/VMDataWheel/main/cloudformation/VmDatasetPipelineStack.template.json">
  <img src="https://img.shields.io/badge/🚀_DEPLOY_NOW-00C853?style=for-the-badge" alt="Deploy Now" />
</a>
-->

</div>

---

## What is VM Data Wheel?

**VM Data Wheel** is a distributed data generation system built on AWS Lambda. It orchestrates 50+ generators from the [vm-dataset](https://github.com/vm-dataset) project to create high-quality training data for video reasoning models.

**Pip-installable package with Pydantic validation and modular architecture.**

---

## 🚀 Getting Started

### Step 1: Install Prerequisites

```bash
# Install Python 3.11+ (if not already installed)
python3 --version  # Should be 3.11 or higher

# Install UV (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install AWS CLI
brew install awscli  # macOS
# or: pip install awscli

# Install GitHub CLI
brew install gh  # macOS
# or: https://cli.github.com/

# Install Docker Desktop
# Download from: https://www.docker.com/products/docker-desktop/
```

### Step 2: Configure AWS

```bash
# Configure AWS credentials
aws configure

# It will ask for:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region (use: us-east-2)
# - Default output format (use: json)
```

### Step 3: Clone and Install

```bash
# Clone the repository
git clone https://github.com/Video-Reason/VMDataWheel
cd VMDataWheel

# Install the package with all dependencies
pip install -e ".[dev,cdk]"
```

### Step 4: Download Generators

```bash
# Authenticate with GitHub (first time only)
gh auth login

# Download all generator repositories
cd scripts
./download_all_repos.sh
cd ..

# This downloads 50+ generators to ./generators/
```

### Step 5: Deploy Infrastructure to AWS

```bash
# Make sure Docker Desktop is running first!

# Navigate to deployment directory
cd deployment

# Bootstrap CDK (first time only)
uv run cdk bootstrap

# Deploy the infrastructure
uv run cdk deploy

# Wait for deployment to complete (~5-10 minutes)
# Save the outputs that appear at the end:
#   - QueueUrl
#   - BucketName
#   - DlqUrl
```

**After deployment completes, you'll see:**
```
Outputs:
VmDatasetPipelineStack.QueueUrl = https://sqs.us-east-2.amazonaws.com/123456789/vm-dataset-pipeline-queue
VmDatasetPipelineStack.BucketName = vm-dataset-123456789-us-east-2
VmDatasetPipelineStack.DlqUrl = https://sqs.us-east-2.amazonaws.com/123456789/vm-dataset-pipeline-dlq
```

**Copy these values!** You'll need them in the next step.

### Step 6: Set Environment Variables

```bash
# Go back to project root
cd ..

# Set the queue URL and bucket from CDK outputs
export SQS_QUEUE_URL="https://sqs.us-east-2.amazonaws.com/123456789/vm-dataset-pipeline-queue"
export OUTPUT_BUCKET="vm-dataset-123456789-us-east-2"

# Optional: Set DLQ URL for monitoring failed tasks
export SQS_DLQ_URL="https://sqs.us-east-2.amazonaws.com/123456789/vm-dataset-pipeline-dlq"

# Optional: Save to .env file for persistence
echo "SQS_QUEUE_URL=$SQS_QUEUE_URL" > .env
echo "OUTPUT_BUCKET=$OUTPUT_BUCKET" >> .env
echo "SQS_DLQ_URL=$SQS_DLQ_URL" >> .env
```

### Step 7: Submit Your First Tasks

```bash
# Test with a single generator (100 samples)
python scripts/submit.py \
  --generator G-1_object_trajectory_data-generator \
  --samples 100 \
  --batch-size 10

# This will:
# - Create 10 SQS messages (10 samples each)
# - Send them to the queue
# - Lambda will automatically process them
```

### Step 8: Monitor Progress

```bash
# Watch queue status in real-time
python scripts/monitor.py --watch

# You'll see:
# - Messages waiting in queue
# - Messages being processed
# - Progress percentage
```

### Step 9: Download Results

```bash
# Once processing is complete, download the generated data
aws s3 sync s3://vm-dataset-123456789-us-east-2/data/v1/ ./results/

# Results structure:
# results/
# └── G-1_object_trajectory_data-generator/
#     ├── 00000/
#     │   ├── first_frame.png
#     │   ├── final_frame.png
#     │   ├── prompt.txt
#     │   └── ground_truth.mp4
#     ├── 00001/
#     └── ...
```

---

## 🎯 Common Workflows

### Generate Large Dataset (All Generators)

```bash
# Submit 10,000 samples for ALL generators
python scripts/submit.py \
  --generator all \
  --samples 10000 \
  --batch-size 100 \
  --seed 42

# Monitor progress
python scripts/monitor.py --watch --interval 10

# This creates 100,000+ SQS messages
# Lambda processes them in parallel (up to 990 concurrent)
# Estimated time: ~2-4 hours depending on generators
```

### Generate Specific Generator Types

```bash
# Only O- generators (puzzles, logic)
# First, edit scripts/download_all_repos.sh line 20:
# Change to: grep -E '^O-([1-9]|[1-4][0-9]|50)_'
cd scripts && ./download_all_repos.sh && cd ..

# Then submit tasks
python scripts/submit.py --generator all --samples 5000
```

### Check for Failed Tasks

```bash
# Monitor the Dead Letter Queue
python scripts/monitor.py --watch

# Look at the DLQ section
# If you see failed messages, they need investigation
```

---

## 📦 Using as a Library

You can import and use vmdatawheel in your own Python projects:

```python
from vmdatawheel.core.models import TaskMessage
from vmdatawheel.sqs.submitter import TaskSubmitter
from vmdatawheel.core.config import config

# Method 1: Submit using the submitter class
submitter = TaskSubmitter(queue_url="https://sqs.us-east-2.amazonaws.com/...")
result = submitter.submit_tasks(
    generators=["G-1_object_trajectory_data-generator"],
    total_samples=1000,
    batch_size=100,
    seed=42,
)
print(f"Submitted {result['total_successful']} tasks")

# Method 2: Create individual task messages
task = TaskMessage(
    type="G-1_object_trajectory_data-generator",
    num_samples=100,
    start_index=0,
    seed=42,
    output_format="files",
)

# Validate automatically with Pydantic
validated_json = task.model_dump_json()
# Use this JSON to send to SQS manually
```

---

## 🏗️ Architecture Overview

### What Gets Created

When you run `cdk deploy`, it creates:

1. **S3 Bucket** - Stores generated data
2. **SQS Queue** - Distributes tasks to workers
3. **Lambda Function** - Runs generators (10GB memory, 15min timeout)
4. **Dead Letter Queue** - Captures failed tasks for retry
5. **IAM Roles** - Permissions for Lambda to access S3/SQS

### How It Works

```
1. You run: python scripts/submit.py
   ↓
2. Creates task messages and sends to SQS Queue
   ↓
3. SQS automatically triggers Lambda (up to 990 concurrent)
   ↓
4. Lambda:
   - Validates message with Pydantic
   - Runs generator script
   - Uploads results to S3
   - Deletes message from queue
   ↓
5. If Lambda fails 3 times → message goes to DLQ
```

### Task Message Format

```json
{
  "type": "G-1_object_trajectory_data-generator",
  "num_samples": 100,
  "start_index": 0,
  "seed": 42,
  "output_format": "files"
}
```

All fields are validated by Pydantic. Invalid messages are rejected immediately.

---

## ⚙️ Configuration

### Required Environment Variables

```bash
export SQS_QUEUE_URL="https://sqs.us-east-2.amazonaws.com/.../vm-dataset-pipeline-queue"
export OUTPUT_BUCKET="vm-dataset-123456789-us-east-2"
```

### Optional Environment Variables

```bash
export AWS_REGION="us-east-2"              # Default region
export SQS_DLQ_URL="https://sqs..."        # For monitoring failed tasks
export GENERATORS_PATH="./generators"       # Local path to generators
```

### Lambda Configuration

Edit `deployment/cdk.json` to adjust:

```json
{
  "context": {
    "lambdaMemoryMB": 10240,           // 10 GB
    "lambdaTimeoutMinutes": 15,        // 15 minutes
    "sqsMaxConcurrency": 990           // Max parallel Lambdas
  }
}
```

---

## 🛠️ Available Scripts

### Submit Tasks

```bash
python scripts/submit.py --generator GENERATOR_NAME --samples NUM_SAMPLES

# Options:
#   --generator, -g    Generator name or "all" (required)
#   --samples, -n      Total samples per generator (default: 10000)
#   --batch-size, -b   Samples per Lambda task (default: 100)
#   --seed, -s         Random seed (optional)
#   --output-format    "files" or "tar" (default: files)
#   --bucket           Override output bucket (optional)

# Examples:
python scripts/submit.py -g all -n 10000
python scripts/submit.py -g G-1_object_trajectory_data-generator -n 1000 --seed 42
```

### Monitor Queue

```bash
python scripts/monitor.py

# Options:
#   --watch, -w        Continuous monitoring mode
#   --interval, -i     Refresh interval in seconds (default: 10)

# Example:
python scripts/monitor.py --watch --interval 5
```

### Download Generators

```bash
cd scripts
./download_all_repos.sh

# This downloads all O- and G- generators from vm-dataset organization
# To download specific types, edit line 20 of the script
```

### Update Generator Dependencies

```bash
cd scripts
./collect_requirements.sh

# This collects requirements.txt from all generators
# and updates ../requirements-all.txt
# Run this when generators are added or updated
```

---

## 🐛 Troubleshooting

### Docker Not Running

**Error:** `Cannot connect to the Docker daemon`

**Solution:** Start Docker Desktop application

### Module Not Found

**Error:** `ModuleNotFoundError: No module named 'pydantic'`

**Solution:**
```bash
pip install -e ".[dev,cdk]"
```

### AWS Credentials Not Configured

**Error:** `Unable to locate credentials`

**Solution:**
```bash
aws configure
# Enter your AWS Access Key ID and Secret Access Key
```

### Queue URL Not Set

**Error:** `SQS_QUEUE_URL environment variable not set`

**Solution:**
```bash
export SQS_QUEUE_URL="https://sqs.us-east-2.amazonaws.com/.../vm-dataset-pipeline-queue"
```

Get this value from CDK outputs after deployment.

### Generator Not Found

**Error:** `Generator not found: ./generators/G-1_object_trajectory_data-generator`

**Solution:**
```bash
cd scripts
./download_all_repos.sh
cd ..
```

### Node.js Version Too Old

**Error:** `Node version 19 is end of life`

**Solution:**
```bash
brew install node@20
```

---

## 🔧 Advanced Usage

### Update Infrastructure

```bash
# Make changes to deployment/cdk/stacks/pipeline_stack.py

# Preview changes
cd deployment && uv run cdk diff

# Apply changes
uv run cdk deploy
```

### Clean Up AWS Resources

```bash
cd deployment
uv run cdk destroy

# This deletes:
# - Lambda function
# - SQS queues
# - IAM roles
# Note: S3 bucket is retained (with your data)
```

### List Available Generators

```bash
ls generators/
# or
python scripts/submit.py --generator all --samples 0  # Will list and exit
```

---

## 📄 License

Apache-2.0

---

<p align="center">
  Part of the <a href="https://github.com/vm-dataset">vm-dataset</a> project
</p>
