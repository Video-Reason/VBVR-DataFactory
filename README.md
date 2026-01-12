<!-- OPTIONAL BANNER -->
<p align="center">
  <!-- Put a banner at assets/banner.png if you want -->
  <!-- <img src="assets/banner.png" alt="VM Data Wheel banner" width="900" /> -->
</p>

<h1 align="center">VM Data Wheel</h1>

<p align="center">
  <b>Distributed data generation system for vm-dataset generators using AWS Lambda.</b>
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
  <a href="#-one-click-deploy">Deploy</a> •
  <a href="#-what-is-vm-data-wheel">What is it?</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-example-generators">Examples</a> •
  <a href="#-documentation">Docs</a>
</p>

<br>

---


<div align="center">

## ☁️ One-Click Deploy

**Deploy to your AWS account in minutes — no installation required.**

<br>

<a href="https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=vm-data-wheel&templateURL=https://raw.githubusercontent.com/Video-Reason/VMDataWheel/main/cloudformation/VmDatasetPipelineStack.template.json">
  <img src="https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png" alt="Launch Stack" height="40" />
</a>

<br>
<br>

| 🪣 S3 Bucket | 📬 SQS Queue | ⚡ Lambda (3GB) | 🔁 DLQ |
|:------------:|:------------:|:----------------:|:------:|
| Output storage | Task queue | 50+ generators | Auto-retry |

</div>

<details>
<summary><b>📋 After deployment — How to use</b></summary>

<br>

**1. Get outputs** from CloudFormation console → Outputs tab:
- `QueueUrl` — Your SQS queue URL
- `BucketName` — Your S3 output bucket

**2. Submit tasks:**
```bash
# Install boto3
pip install boto3

# Submit 10K samples for all generators
python scripts/submit_tasks.py \
  --queue-url <YOUR_QUEUE_URL> \
  --generator all \
  --samples 10000
```

**3. Download results:**
```bash
aws s3 sync s3://<YOUR_BUCKET_NAME> ./results
```

</details>

<br>

---

## 🎯 What is VM Data Wheel?

VM Data Wheel is a **scalable data generation framework** that produces synthetic video-reasoning samples for training and evaluating video generation models. Submit tasks to SQS, and Lambda workers generate samples in parallel — from 10K to millions of samples with zero infrastructure management.

```python
# Generate 10K samples for all 50+ generators
python scripts/submit_tasks.py --generator all --samples 10000

# Monitor progress
python scripts/sqs_monitor.py --watch

# Download results
aws s3 sync s3://vm-dataset-xxx ./results
```

Each generated sample includes:

```text
{task_id}/
├── first_frame.png      # Initial state image
├── final_frame.png      # Target state image
├── prompt.txt           # Task description
├── rubric.txt           # Evaluation criteria
└── ground_truth.mp4     # Solution video (optional)
```

<br>

---

## ✨ Why use this?

1. **Infinite scale with zero ops**
   - Generate 10K to 1M+ samples using serverless Lambda
   - No GPU clusters to manage, no infrastructure headaches
   - Pay only for what you use

2. **Perfect reproducibility**
   - Deterministic generation with seed control
   - Same seed = same data, always
   - Version-controlled generators

3. **50+ diverse task types**
   - Physics simulations, puzzles, spatial reasoning
   - Object permanence, counting, logic gates
   - Easy to add new generators

4. **Production-ready pipeline**
   - Dead-letter queue for failed tasks
   - Automatic retries with exponential backoff
   - Real-time monitoring dashboard

<br>

---

## 🚀 Quick Start

> **Note:** This section is for developers who want to modify the code. For simple deployment, use [One-Click Deploy](#-one-click-deploy) above.

<br>

<a href="https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=vm-data-wheel&templateURL=https://raw.githubusercontent.com/Video-Reason/VMDataWheel/main/cloudformation/VmDatasetPipelineStack.template.json">
  <img src="https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png" alt="Launch Stack" height="40" />
</a>

<br>

### Prerequisites

| Tool | Installation |
|------|--------------|
| Python 3.11+ | — |
| [UV](https://github.com/astral-sh/uv) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [AWS CLI](https://aws.amazon.com/cli/) | `brew install awscli` |
| [GitHub CLI](https://cli.github.com/) | `brew install gh` |
| Docker | [Download](https://www.docker.com/products/docker-desktop/) |

### Installation

```bash
# Clone
git clone https://github.com/Video-Reason/VMDataWheel
cd VMDataWheel

# Install dependencies
uv sync --extra dev --extra cdk

# Download generators
cd scripts && ./download_all_repos.sh && cd ..
```

### Local Testing

```bash
# Start Web UI
uv run python scripts/test_server.py
# Open http://localhost:8000
```

### Deploy to AWS

```bash
export AWS_PROFILE=your-profile-name

# Bootstrap (first time only)
uv run cdk bootstrap

# Deploy
uv run cdk deploy
```

<br>

---

## 🧩 Example Generators

Expand each category below to see example generators:

<details>
<summary><b>🧠 Puzzles & Logic</b></summary>

| Generator | Description |
|-----------|-------------|
| `O-41_nonogram` | Solve nonogram puzzles from row/column hints |
| `O-sudoku` | Complete Sudoku grids |
| `O-maze` | Find path through mazes |
| `O-logic_gates` | Evaluate logic circuit outputs |

</details>

<details>
<summary><b>⚡ Physics & Motion</b></summary>

| Generator | Description |
|-----------|-------------|
| `G-object_trajectory` | Predict object motion paths |
| `G-collision` | Simulate object collisions |
| `G-gravity` | Objects falling under gravity |
| `G-bounce` | Ball bouncing physics |

</details>

<details>
<summary><b>👁️ Spatial & Visual</b></summary>

| Generator | Description |
|-----------|-------------|
| `O-42_object_permanence` | Track objects behind occluders |
| `O-43_object_subtraction` | Count remaining objects |
| `O-shape_transform` | Identify shape transformations |
| `O-color_mixing` | Predict color combinations |

</details>

<details>
<summary><b>🔢 Counting & Math</b></summary>

| Generator | Description |
|-----------|-------------|
| `O-counting` | Count objects in scene |
| `O-arithmetic` | Visual arithmetic problems |
| `O-sequence` | Complete number sequences |

</details>

<br>

---

## 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐   │
│   │  Submit  │ ───▶ │   SQS    │ ───▶ │  Lambda  │ ───▶ │    S3    │   │
│   │  Tasks   │      │  Queue   │      │ Container│      │  Output  │   │
│   └──────────┘      └──────────┘      └──────────┘      └──────────┘   │
│                           │                 │                           │
│                           ▼                 ▼                           │
│                     ┌──────────┐      ┌──────────┐                     │
│                     │   DLQ    │      │ 50+ Gens │                     │
│                     │ (Retry)  │      │ in Image │                     │
│                     └──────────┘      └──────────┘                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Generator Types

| Type | Description | Memory | Examples |
|:----:|-------------|:------:|----------|
| **O-** | Static/Logic tasks | 🟢 Low | Puzzles, counting, logic |
| **G-** | Dynamic/Physics tasks | 🟡 High | Animation, simulation |

<details>
<summary><b>Memory characteristics</b></summary>

**G- Generators** accumulate video frames in memory:
```
Frame 1 → Frame 2 → ... → Frame N  (all in memory before encoding)
```

**O- Generators** process and release immediately:
```
Input → Process → Output → Release ♻️
```

Configure batch sizes per generator in `scripts/generator_config.json`.

</details>

<br>

---

## 📚 Documentation

| Resource | Description |
|----------|-------------|
| [CLAUDE.md](./CLAUDE.md) | Development guidelines & code style |
| [scripts/SQS_README.md](./scripts/SQS_README.md) | SQS operations & monitoring |

### Configuration

<details>
<summary><b>Environment Variables</b></summary>

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `OUTPUT_BUCKET` | ✓ | — | S3 bucket for output data |
| `SQS_QUEUE_URL` | ✓ | — | SQS queue URL |
| `AWS_REGION` | | `us-east-2` | AWS region |
| `AWS_PROFILE` | | — | AWS CLI profile name |
| `GENERATORS_PATH` | | `/opt/generators` | Path to generators |
| `SQS_DLQ_URL` | | — | Dead Letter Queue URL |

</details>

<details>
<summary><b>Lambda Settings</b></summary>

| Parameter | Value |
|-----------|-------|
| Memory | 10 GB |
| Timeout | 15 min |
| Runtime | Python 3.11 (Container) |

</details>

<details>
<summary><b>SQS Settings</b></summary>

| Parameter | Value |
|-----------|-------|
| Visibility Timeout | 16 min |
| Max Retries | 3 |
| DLQ | Enabled |

</details>

<details>
<summary><b>Task Message Format</b></summary>

```json
{
  "type": "chess-task-data-generator",
  "start_index": 0,
  "num_samples": 100,
  "seed": 42,
  "output_format": "files",
  "output_bucket": "my-output-bucket"
}
```

| Field | Required | Default | Description |
|-------|:--------:|---------|-------------|
| `type` | ✓ | — | Generator name |
| `start_index` | | `0` | Starting index for sample IDs |
| `num_samples` | ✓ | — | Samples to generate (≤100 recommended) |
| `seed` | | random | Random seed for reproducibility |
| `output_format` | | `files` | `files` or `tar` |
| `output_bucket` | ✓ | — | S3 bucket for output data |

</details>

<br>

---

## 🛠️ Scripts Reference

| Script | Description | Example |
|--------|-------------|---------|
| `submit_tasks.py` | Submit tasks to SQS | `--generator all --samples 10000` |
| `sqs_monitor.py` | Monitor queue status | `--watch` |
| `sqs_utils.py` | Queue tools | `count`, `peek`, `purge` |
| `test_server.py` | Local test Web UI | Opens at :8000 |
| `local_test.py` | CLI testing | `--generator all --samples 3` |
| `download_dlq_messages.py` | Download failed tasks | `--output DLQ` |
| `push_dlq_to_sqs.py` | Retry failed tasks | `--dlq-dir DLQ` |

<br>

---

## 🐛 Troubleshooting

<details>
<summary><b>Docker not running</b></summary>

Start Docker Desktop before running `cdk deploy`.

</details>

<details>
<summary><b>psutil missing after uv sync</b></summary>

```bash
uv add psutil
```

</details>

<details>
<summary><b>Node.js version outdated</b></summary>

Node 19 is EOL. Upgrade to Node 20+:

```bash
brew install node@20
```

</details>

<details>
<summary><b>Download specific generator types</b></summary>

Edit `scripts/download_all_repos.sh` line 20:

```bash
# O- generators (puzzles, logic)
grep -E '^O-([1-9]|[1-4][0-9]|50)_'

# G- generators (physics, animation)
grep -E '^G-([1-9]|[1-4][0-9]|50)_'
```

</details>

<br>

---

## 📂 Project Structure

```text
vm-data-wheel/
├── src/                          # Lambda source code
│   ├── handler.py                # Lambda entry point
│   ├── generator.py              # Generator execution
│   ├── uploader.py               # S3 upload logic
│   └── config.py                 # Configuration
├── cdk/                          # CDK infrastructure
│   └── stacks/pipeline_stack.py  # Lambda, SQS, S3 definitions
├── cloudformation/               # One-click deploy template
│   └── VmDatasetPipelineStack.template.json
├── scripts/                      # CLI utilities
│   ├── submit_tasks.py           # Task submission
│   ├── sqs_monitor.py            # Queue monitoring
│   ├── test_server.py            # Local test UI
│   └── static/                   # Web UI assets
├── tests/                        # Unit tests
├── generators/                   # Generator repos (gitignored)
├── Dockerfile                    # Lambda container
└── pyproject.toml                # Dependencies
```

<br>

---

## 🤝 Contributing

Contributions are welcome! Please see [CLAUDE.md](./CLAUDE.md) for development guidelines.

```bash
# Setup
uv sync --extra dev --extra cdk
uv run pre-commit install

# Test
uv run pytest

# Lint
uv run ruff check src/ scripts/
```

<br>

---

## 📄 License

Apache-2.0 — See [LICENSE](./LICENSE) for details.

<br>

---

<p align="center">
  <sub>Part of the <a href="https://github.com/vm-dataset">vm-dataset</a> project</sub>
</p>
