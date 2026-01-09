# Project Guidelines

## Overview

AWS Lambda pipeline for generating VM dataset samples. Uses SQS for task distribution and S3 for output storage.

## Tech Stack

- Python 3.11+
- UV for package management
- AWS CDK for infrastructure
- pytest for testing
- Ruff for linting/formatting

## Commands

**Always use `uv run` for Python commands** (no system Python):

```bash
uv sync --extra dev --extra cdk          # Install dependencies
uv run pytest                             # Run tests
uv run ruff check src/ scripts/           # Lint
uv run ruff format src/ scripts/          # Format
uv run cdk deploy --profile <profile>     # Deploy (CDK needs --profile)
uv run python scripts/submit_tasks.py ... # Run scripts
```

## Code Style

- Line length: 120 characters
- Use type hints for function signatures
- Use f-strings for string formatting
- Use `logging` module instead of `print()` in `src/`
- No Chinese text in code or documentation

## Project Structure

```
src/           # Lambda source code (handler, generator, uploader, utils)
scripts/       # CLI utilities (submit_tasks, sqs_monitor, etc.)
cdk/           # CDK infrastructure code
tests/         # pytest tests
generators/    # Generator repos (gitignored, downloaded via scripts)
```

## Dependencies

- `pyproject.toml` - Pipeline dependencies (boto3, pytest, cdk, etc.)
- `requirements-all.txt` - All generator dependencies merged together

The Docker image includes all generator dependencies because a single Lambda instance may run any generator. Use `scripts/collect_requirements.sh` to update `requirements-all.txt` when generators change.

## Testing

- Run `uv run pytest` after making changes
- New features require tests
- Tests are in `tests/unit/`

## Git

- Do not include "Co-Authored-By" or AI-generated descriptions in commits
