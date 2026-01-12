# 🎬 VM Dataset Pipeline

**Scalable data generation for video reasoning models.**

Generate unlimited synthetic video-reasoning samples using AWS Lambda. Built for researchers who need reproducible, high-quality training data at scale.

---

## ✨ Highlights

- 🚀 **Infinite Scale** — Generate 10K to 1M+ samples using serverless Lambda
- 🎯 **50+ Task Types** — Puzzles, physics, object permanence, spatial reasoning
- 🔄 **Reproducible** — Deterministic generation with seed control
- 📦 **Modular** — Add new generators without changing infrastructure

## 🏗️ Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Submit    │ ───▶ │     SQS     │ ───▶ │   Lambda    │ ───▶ │     S3      │
│   Tasks     │      │    Queue    │      │  Container  │      │   Output    │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                    ┌───────────┴───────────┐
                                    │   50+ Generators      │
                                    │   (Physics, Puzzles,  │
                                    │    Logic, Spatial)    │
                                    └───────────────────────┘
```

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/LianyuHuang/vm-dataset-pipeline
cd vm-dataset-pipeline

# Install dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
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

### Deploy & Generate

```bash
# Deploy infrastructure
uv run cdk deploy

# Submit 10K samples per generator
python scripts/submit_tasks.py --generator all --samples 10000
```

## 📦 Output Format

Each sample contains:

```
{task_id}/
├── first_frame.png      # Initial state
├── final_frame.png      # Target state
├── prompt.txt           # Task description
├── rubric.txt           # Evaluation criteria
└── ground_truth.mp4     # Solution video (optional)
```

## 🧩 Generator Types

| Type | Examples | Memory | Use Case |
|------|----------|--------|----------|
| **O-** (Static) | Nonogram, Sudoku, Mazes | Low | Puzzles, logic tasks |
| **G-** (Dynamic) | Physics, Animation, Path planning | High | Video generation, simulation |

<details>
<summary><b>Memory Characteristics</b></summary>

**G- Generators** accumulate frames in memory for video generation:
```
Frame 1 → Frame 2 → ... → Frame N  (all in memory)
```

**O- Generators** process single images with immediate memory release:
```
Input → Process → Output → Release
```

Configure batch sizes in `scripts/generator_config.json`.

</details>

## 📚 Documentation

| Topic | Description |
|-------|-------------|
| [CLAUDE.md](./CLAUDE.md) | Development guidelines |
| [scripts/SQS_README.md](./scripts/SQS_README.md) | SQS operations guide |

## 🛠️ Development

```bash
uv run pytest                           # Run tests
uv run ruff check src/ scripts/         # Lint
uv run cdk deploy                       # Deploy changes
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OUTPUT_BUCKET` | Yes | S3 bucket for output |
| `SQS_QUEUE_URL` | Yes | SQS queue URL |
| `AWS_REGION` | No | Default: `us-east-2` |

### Lambda Settings

| Parameter | Value |
|-----------|-------|
| Memory | 10 GB |
| Timeout | 15 min |

## 🐛 Troubleshooting

<details>
<summary><b>Common Issues</b></summary>

**Docker not running**
```bash
# Start Docker Desktop before `cdk deploy`
```

**psutil missing**
```bash
uv sync --extra dev
```

**Node.js outdated**
```bash
brew install node@20
```

**Download specific generators**
```bash
# Edit scripts/download_all_repos.sh line 20:
grep -E '^O-([1-9]|[1-4][0-9]|50)_'  # O- generators
grep -E '^G-([1-9]|[1-4][0-9]|50)_'  # G- generators
```

</details>

## 📄 License

Apache-2.0

## 🔗 Related Projects

Part of the Video Reasoning research stack:
- **Data Engine** — This repository
- **Inference Engine** — Model inference pipeline
- **Evaluation Engine** — Benchmark evaluation
- **Training Kit** — Model training utilities
