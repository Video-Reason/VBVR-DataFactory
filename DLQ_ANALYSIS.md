# Dead Letter Queue (DLQ) Analysis
**Date:** 2026-01-15 09:15 UTC
**Total Messages in DLQ:** 105

## Executive Summary

The DLQ contains 105 failed messages from Lambda processing, with **95% (100/105) failures** from a single generator: `G-41_grid_highest_cost_data-generator`. All failures occurred within a ~16 second window (08:51:21 - 08:51:37 UTC), suggesting a systematic issue rather than isolated failures.

## Key Findings

### 1. **Dominant Failure: G-41 Grid Highest Cost Generator**
- **Impact**: 100 out of 105 messages (95.2%)
- **Scope**: Complete batch failure (100 consecutive tasks from index 0-9900)
- **Pattern**: Every 100-sample increment failed: [0, 100, 200, 300, ..., 9900]
- **Seeds**: Sequential seeds from 435615170 to 435615269
- **Root Cause**: CalledProcessError - Generator script returning exit status 1

### 2. **Secondary Failures (5 messages)**
- G-32 (undirected_graph_navigation): 2 failures (indices 6600, 7500)
- G-16 (grid_go_through_block): 1 failure (index 100) - **Directory not empty error**
- G-33 (visual_jenga): 1 failure (index 100)
- G-40 (combined_objects_spinning): 1 failure (index 2300)

### 3. **Error Categories from CloudWatch Logs**

#### Primary Error Types:
1. **CalledProcessError** (42 occurrences, 84%)
   - Generator subprocess exits with non-zero status
   - Indicates generator script itself is failing
   - NO stdout/stderr captured in current implementation

2. **OSError: No space left on device** (3 occurrences, 6%)
   - Lambda /tmp disk full (512 MB limit)
   - Occurs during tar file creation
   - Affects tar output format

3. **OSError: Directory not empty** (2 occurrences, 4%)
   - File rename collision in validator.py
   - rename_samples() function trying to rename to existing directory

## Detailed Breakdown

### Generator Failures Distribution

| Generator | Failed Messages | Start Indices | Issue Type |
|-----------|----------------|---------------|------------|
| G-41_grid_highest_cost | 100 | 0-9900 (every 100) | Generator script failure |
| G-32_undirected_graph_navigation | 2 | 6600, 7500 | Generator script failure |
| G-16_grid_go_through_block | 1 | 100 | Directory rename conflict |
| G-33_visual_jenga | 1 | 100 | Generator script failure |
| G-40_combined_objects_spinning | 1 | 2300 | Unknown |

### Retry Behavior Analysis

```
Messages with 2 retries: 95 (90.5%)
Messages with 3 retries: 10 (9.5%)
```

- Most messages exhausted retries quickly (2 attempts)
- SQS DLQ maxReceiveCount appears to be 2-3
- No evidence of successful retries (all ended in DLQ)

### Timeline Analysis

```
First failure:  2026-01-15 08:51:21.585
Last failure:   2026-01-15 08:51:37.405
Duration:       15.82 seconds
```

- **Burst failure pattern**: All 105 failures within 16 seconds
- Suggests concurrent Lambda executions hitting same issue
- Likely triggered by a batch submission event

### Configuration Analysis

All failed messages share identical configuration:
- **Output Format**: `tar` (100%)
- **Output Bucket**: `null` (100%, using default from config)
- **Num Samples**: 100 per task
- **Seeds**: Provided (not random)

## Root Cause Analysis

### Primary Issue: G-41 Generator Script Failure

**Evidence:**
```
[ERROR] CalledProcessError: Command '['/var/lang/bin/python3.11', 
'examples/generate.py', '--num-samples', '100', '--seed', '66', 
'--output-dir', '/tmp/output_G-41_grid_highest_cost_data-generator_2']' 
returned non-zero exit status 1.
```

**Problem**: Generator script exits with error code 1, but:
- ❌ No stdout/stderr logged to CloudWatch
- ❌ Current GeneratorRunner captures output but only logs on success (debug level)
- ❌ On failure, CalledProcessError is raised but subprocess output is lost

**Location in Code:**
- `vmdatawheel/core/generator.py:95-102`
- Uses `subprocess.run()` with `capture_output=True, check=True`
- Captured output only logged if command succeeds (lines 105-108)

### Secondary Issue: Lambda Disk Space

**Evidence:**
```
[ERROR] OSError: [Errno 28] No space left on device
  File "/var/task/vmdatawheel/core/uploader.py", line 87
  with tarfile.open(tar_path, "w:gz") as tar:
```

**Problem**: /tmp directory full during tar creation
- Lambda /tmp limit: 512 MB
- Tar format stores files before uploading
- 100 samples with images can easily exceed 512 MB

### Tertiary Issue: Directory Rename Conflicts

**Evidence:**
```
[ERROR] OSError: [Errno 39] Directory not empty: 
'/tmp/output_G-16_grid_go_through_block_data-generator_2/
grid_go_through_block_task/grid_go_through_block_0001' -> 
'/tmp/output_G-16_grid_go_through_block_data-generator_2/
grid_go_through_block_task/grid_go_through_block_0100'
```

**Problem**: validator.py attempting to rename directory to one that exists
- `vmdatawheel/core/validator.py:145`
- Using `Path.rename()` which fails if target exists
- Likely concurrent processing or retry collision

## Recommendations

### Immediate Actions (Critical)

1. **Enable Generator Error Logging**
   - Modify `GeneratorRunner.run()` to log stdout/stderr on failure
   - Add exception context with captured output
   - Priority: CRITICAL - Cannot debug without this

2. **Investigate G-41 Generator**
   - Manually test with failed seeds: 435615170-435615269
   - Check generator's own logs/error handling
   - Verify dependencies and environment

3. **Review Lambda Resources**
   - Check if 512 MB /tmp is sufficient
   - Consider switching to `files` format instead of `tar` for large batches
   - Add disk space monitoring

### Short-term Fixes

1. **Fix Directory Rename Logic**
   - Replace `Path.rename()` with safe rename (check if exists first)
   - Add retry logic with small delay
   - Consider using `shutil.move()` with exist_ok behavior

2. **Add Pre-flight Checks**
   - Validate generator exists and is executable before queuing
   - Test generator with sample seed before batch submission
   - Add generator version/health check

3. **Improve Error Reporting**
   - Log full subprocess command on failure
   - Include working directory and environment
   - Add generator-specific error codes

### Long-term Improvements

1. **Enhanced Monitoring**
   - CloudWatch dashboard for generator failures by type
   - DLQ alarm when > 10 messages
   - Success rate metrics per generator

2. **Graceful Degradation**
   - Implement partial success handling
   - Allow uploading completed samples even if some fail
   - Add sample-level retry vs task-level retry

3. **Resource Management**
   - Stream tar files directly to S3 instead of writing to /tmp
   - Implement progressive cleanup during processing
   - Add memory/disk usage tracking

## DLQ Message Details

### Sample DLQ Message Structure
```json
{
  "message_id": "06403e8c-061a-437e-be27-4ec7ce21f773",
  "timestamp": "1768467097367",
  "receive_count": "2",
  "body": {
    "type": "G-41_grid_highest_cost_data-generator",
    "num_samples": 100,
    "start_index": 5100,
    "seed": 435615221,
    "output_format": "tar",
    "output_bucket": null
  },
  "attributes": {
    "DeadLetterQueueSourceArn": "arn:aws:sqs:us-east-2:956728988776:vm-dataset-pipeline-queue-20260115-084225"
  }
}
```

## Next Steps

### For Debugging G-41 Failures:

1. **Local Testing**
   ```bash
   cd /opt/generators/G-41_grid_highest_cost_data-generator
   python examples/generate.py --num-samples 100 --seed 435615170 --output-dir /tmp/test_output
   ```

2. **Check Generator Logs**
   - Look for generator-specific log files
   - Check for missing dependencies
   - Verify input parameter validation

3. **Deploy Fix**
   - Update GeneratorRunner to log errors
   - Redeploy Lambda function
   - Resubmit failed messages from DLQ

### For Resubmitting DLQ Messages:

The DLQ manager provides resubmission capability:
```python
from vmdatawheel.sqs.dlq import DLQManager
from vmdatawheel.core.config import config

dlq_manager = DLQManager(config.sqs_dlq_url)
results = dlq_manager.resubmit_messages(
    dlq_dir=Path('dlq_analysis_full'),
    target_queue_url=config.sqs_queue_url
)
```

**⚠️ Warning**: Do NOT resubmit until G-41 issue is resolved or messages will just fail again.

## Files Generated

- `dlq_analysis/` - First 10 DLQ messages (sample)
- `dlq_analysis_full/` - All 105 DLQ messages (complete analysis)
- Each message saved as: `YYYYMMDD_HHMMSS_{message_id}.json`

## Related Files

- `vmdatawheel/core/generator.py` - Generator execution (needs error logging fix)
- `vmdatawheel/core/validator.py` - Directory rename issue (line 145)
- `vmdatawheel/core/uploader.py` - Disk space issue during tar creation (line 87)
- `vmdatawheel/lambda_handler/handler.py` - Main Lambda entry point
- `vmdatawheel/sqs/dlq.py` - DLQ management utilities

---

**Analysis Generated:** 2026-01-15 09:15 UTC
**Data Source:** SQS DLQ + CloudWatch Logs
**Total Failed Tasks:** 105 messages = 10,500 samples not generated
