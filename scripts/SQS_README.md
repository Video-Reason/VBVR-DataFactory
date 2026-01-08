# SQS Task Submission Scripts

Enhanced SQS task submission and monitoring tools for VM Dataset Pipeline.

## 📋 Overview

This directory contains scripts for managing SQS-based task distribution:

- **`submit_tasks.py`** - Submit generation tasks to SQS with progress tracking
- **`sqs_monitor.py`** - Monitor queue status in real-time
- **`sqs_utils.py`** - Utility functions for queue management

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Required: Set SQS queue URL
export SQS_QUEUE_URL="https://sqs.us-east-2.amazonaws.com/956728988776/vm-dataset-tasks"

# Optional: Set DLQ URL for monitoring
export SQS_DLQ_URL="https://sqs.us-east-2.amazonaws.com/956728988776/vm-dataset-tasks-dlq"

# Optional: Set generators path (default: ../generators)
export GENERATORS_PATH="../generators"
```

### 2. Install Dependencies

```bash
pip install boto3 tqdm
```

**Note:** `tqdm` is optional but recommended for progress bars.

### 3. Submit Tasks

```bash
# Submit for all generators
python submit_tasks.py --generator all --samples 10000

# Submit for a specific generator
python submit_tasks.py --generator chess-task-data-generator --samples 10000

# Dry run to test
python submit_tasks.py --generator all --samples 1000 --dry-run
```

---

## 📚 Detailed Usage

### submit_tasks.py

**Enhanced task submission script with:**
- ✅ Beautiful progress bars with ETA
- ✅ Automatic retry on failures (3 attempts)
- ✅ Detailed statistics and reporting
- ✅ Dry-run mode for testing
- ✅ Verbose logging option
- ✅ Color-coded output

#### Basic Usage

```bash
# Submit 10,000 samples for all generators
python submit_tasks.py --generator all --samples 10000

# Submit with custom batch size
python submit_tasks.py --generator all --samples 10000 --batch-size 500

# Submit with custom seed
python submit_tasks.py --generator all --samples 10000 --seed 123
```

#### Advanced Options

```bash
# Dry run (don't actually send messages)
python submit_tasks.py --generator all --samples 10000 --dry-run

# Verbose output
python submit_tasks.py --generator all --samples 10000 --verbose

# Combine options
python submit_tasks.py \
    --generator all \
    --samples 10000 \
    --batch-size 500 \
    --seed 123 \
    --verbose
```

#### Command-Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--generator` | Generator name or "all" | *required* |
| `--samples` | Samples per generator | 10000 |
| `--batch-size` | Samples per Lambda task | 1000 |
| `--seed` | Random seed | 42 |
| `--dry-run` | Test without sending | false |
| `--verbose`, `-v` | Enable verbose output | false |

#### Output Example

```
======================================================================
              VM Dataset Pipeline - Task Submission
======================================================================

Configuration:
  • Generators: 200
  • Samples per generator: 10,000
  • Batch size: 1000
  • Tasks per generator: 10
  • Total tasks: 2,000
  • Random seed: 42
  • Queue URL: https://sqs.us-east-2.amazonaws.com/.../vm-dataset-tasks

Generators: 100%|████████████████| 200/200 [05:23<00:00,  1.62s/gen]

======================================================================
                        Submission Summary
======================================================================

Results:
  • Total tasks: 2,000
  • Successful: 2,000
  • Failed: 0
  • Success rate: 100.0%

Generators:
  • Total: 200
  • Successful: 200
  • Failed: 0

Performance:
  • Duration: 323.4 seconds (5.4 minutes)
  • Throughput: 6.2 tasks/second

✓ ALL TASKS SUBMITTED SUCCESSFULLY!
```

---

### sqs_monitor.py

**Monitor queue status in real-time.**

#### Usage

```bash
# Single snapshot
python sqs_monitor.py

# Continuous monitoring (refresh every 10 seconds)
python sqs_monitor.py --watch

# Custom refresh interval
python sqs_monitor.py --watch --interval 5
```

#### Output Example

```
============================================================
        VM Dataset Pipeline - Queue Monitor
============================================================

2026-01-07 11:30:45

📊 Main Queue (vm-dataset-tasks)
────────────────────────────────────────────────────────────
  Waiting:          1,234 messages
  Processing:         156 messages
  Total:            1,390 messages

  Progress: 11.2% in flight

📊 Dead Letter Queue
────────────────────────────────────────────────────────────
  Waiting:              0 messages
  Processing:           0 messages
  Total:                0 messages

Refreshing in 10 seconds... (Ctrl+C to exit)
```

---

### sqs_utils.py

**Utility functions for queue management.**

#### Commands

**1. Count Messages**

```bash
python sqs_utils.py count
```

Output:
```
Message Counts:
  Available:   1,234
  In-flight:   156
  Delayed:     0
  Total:       1,390
```

**2. Peek at Message**

```bash
# View a message (without removing it)
python sqs_utils.py peek

# View and delete a message
python sqs_utils.py peek --delete
```

Output:
```
Message Body:
{
  "type": "chess-task-data-generator",
  "start_index": 0,
  "num_samples": 1000,
  "seed": 42
}

Message ID: abc123...
MD5: def456...

(Message will return to queue after visibility timeout)
```

**3. Purge Queue**

```bash
# Purge with confirmation
python sqs_utils.py purge

# Force purge (no confirmation)
python sqs_utils.py purge --force
```

⚠️ **WARNING:** This deletes ALL messages from the queue!

---

## 🎯 Common Workflows

### Workflow 1: Full Pipeline Submission

Submit tasks for all 200 generators (2 million samples):

```bash
# 1. Set environment
export SQS_QUEUE_URL="https://sqs.us-east-2.amazonaws.com/956728988776/vm-dataset-tasks"

# 2. Test with dry run first
python submit_tasks.py --generator all --samples 10000 --dry-run

# 3. Submit for real
python submit_tasks.py --generator all --samples 10000

# 4. Monitor progress
python sqs_monitor.py --watch
```

### Workflow 2: Single Generator Testing

Test with a single generator:

```bash
# 1. Submit small batch
python submit_tasks.py \
    --generator chess-task-data-generator \
    --samples 100 \
    --batch-size 10

# 2. Check queue status
python sqs_utils.py count

# 3. Peek at a message
python sqs_utils.py peek

# 4. Monitor processing
python sqs_monitor.py --watch
```

### Workflow 3: Recovery from Failures

If tasks fail and end up in DLQ:

```bash
# 1. Check DLQ
export SQS_QUEUE_URL="<your-dlq-url>"
python sqs_utils.py count

# 2. Inspect failed messages
python sqs_utils.py peek

# 3. Resubmit if needed
# (Manually fix issues and resubmit)
```

---

## 📊 Message Format

Tasks are submitted as JSON messages:

```json
{
  "type": "chess-task-data-generator",
  "start_index": 0,
  "num_samples": 1000,
  "seed": 42
}
```

**Fields:**
- `type`: Generator name (matches directory in `generators/`)
- `start_index`: Starting index for global task IDs
- `num_samples`: Number of samples to generate in this batch
- `seed`: Random seed for reproducibility

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `SQS_QUEUE_URL` | Main SQS queue URL | Yes | - |
| `SQS_DLQ_URL` | Dead letter queue URL | No | - |
| `GENERATORS_PATH` | Path to generators | No | `../generators` |

### Recommended Settings

**For 200 generators × 10K samples:**

```bash
python submit_tasks.py \
    --generator all \
    --samples 10000 \
    --batch-size 1000 \
    --seed 42
```

This creates:
- **2,000 total tasks** (200 generators × 10 tasks each)
- **Each task generates 1,000 samples**
- **2 million total samples**

**Batch size considerations:**
- Smaller batches (100-500): More tasks, faster start, better parallelism
- Larger batches (1000-2000): Fewer tasks, better efficiency, less overhead
- **Recommended: 1000** (good balance)

---

## 🐛 Troubleshooting

### Issue: "SQS_QUEUE_URL not set"

**Solution:**
```bash
export SQS_QUEUE_URL="https://sqs.us-east-2.amazonaws.com/956728988776/vm-dataset-tasks"
```

### Issue: Messages not being processed

**Check:**
1. Lambda function deployed and active
2. SQS event source mapping enabled
3. Lambda has permissions to read from SQS
4. Lambda timeout (should be 15 minutes)

```bash
# Check queue status
python sqs_monitor.py

# Check if messages are in DLQ
export SQS_QUEUE_URL="<your-dlq-url>"
python sqs_utils.py count
```

### Issue: High failure rate

**Investigate:**
```bash
# 1. Check DLQ for error patterns
export SQS_QUEUE_URL="<your-dlq-url>"
python sqs_utils.py peek

# 2. Check Lambda logs
aws logs tail /aws/lambda/vm-dataset-generator --follow

# 3. Reduce batch size
python submit_tasks.py --generator all --samples 10000 --batch-size 500
```

### Issue: Slow submission

**Optimize:**
```bash
# Install tqdm for progress bars
pip install tqdm

# Use larger SQS batches (already at max 10)
# Consider running from EC2 for better network speed
```

---

## 📈 Performance

### Submission Speed

**Local machine:**
- ~5-10 tasks/second
- 2,000 tasks in ~5 minutes

**EC2 instance (same region):**
- ~20-50 tasks/second
- 2,000 tasks in ~1 minute

### Cost Estimation

**SQS Costs:**
```
Requests: 2,000 tasks × $0.0000004 = $0.0008
```

**Lambda Costs (assuming 1000 samples/task, 2 min/task):**
```
Compute: 2,000 × 120s × 1024MB × $0.0000166667 = $4.00
Requests: 2,000 × $0.0000002 = $0.0004

Total Lambda: ~$4.00
```

**S3 Costs:**
```
PUT requests: 6M files × $0.005/1000 = $30
Storage: 300GB × $0.023/GB = $6.90/month

Total S3: ~$37 (first month)
```

**Total: ~$41** for 2 million samples

---

## 🎓 Best Practices

### 1. Always Test First

```bash
# Start with dry run
python submit_tasks.py --generator all --samples 1000 --dry-run

# Test with single generator
python submit_tasks.py --generator chess-task-data-generator --samples 100

# Then scale up
python submit_tasks.py --generator all --samples 10000
```

### 2. Monitor Progress

```bash
# Watch queue in separate terminal
python sqs_monitor.py --watch
```

### 3. Handle Failures Gracefully

- Check DLQ regularly
- Set up CloudWatch alarms
- Review Lambda logs for errors

### 4. Use Version Control

```bash
# Track configuration changes
git log scripts/submit_tasks.py
```

---

## 🔄 Updates and Changes

### v2.0 (Enhanced Version)

**New Features:**
- ✅ Progress bars with ETA
- ✅ Automatic retry (3 attempts)
- ✅ Detailed statistics
- ✅ Dry-run mode
- ✅ Verbose logging
- ✅ Color-coded output
- ✅ Better error handling

**Breaking Changes:**
- None (backward compatible)

**Migration:**
```bash
# Old usage still works
python submit_tasks.py --generator all --samples 10000

# New features are opt-in
python submit_tasks.py --generator all --samples 10000 --verbose --dry-run
```

---

## 📞 Support

For issues or questions:
1. Check CloudWatch Logs for Lambda errors
2. Monitor SQS queue status
3. Review this documentation
4. Check project README.md

---

## 📝 License

Part of VM Dataset Pipeline project.

---

**Last Updated:** 2026-01-07  
**Maintainer:** Your team  
**Version:** 2.0

