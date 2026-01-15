#!/bin/bash

# Complete missing samples from DLQ analysis
# Strategy: Use smaller batches for safety
# Usage: ./complete_missing.sh [test|small|full]

set -e

MODE="${1:-test}"

echo "========================================================================"
echo "VMDataWheel - Complete Missing Samples"
echo "========================================================================"
echo "Mode: $MODE"
echo ""

case $MODE in
    test)
        echo "TEST MODE - Submitting 20 samples in 1 batch for G-41"
        echo "This will test if the generator works after fixes"
        echo "----------------------------------------"
        
        python scripts/submit.py \
            --generator "G-41_grid_highest_cost_data-generator" \
            --samples 20 \
            --batch-size 20 \
            --seed 435615170 \
            --output-format tar
        
        echo ""
        echo "✓ Test batch submitted"
        echo ""
        echo "Next steps:"
        echo "  1. Monitor: python scripts/monitor.py"
        echo "  2. Check CloudWatch logs for errors"
        echo "  3. Verify S3 upload: aws s3 ls s3://vm-dataset-956728988776-us-east-2-20260115-084225/questions/G-41_grid_highest_cost_data-generator/"
        echo "  4. If successful, run: ./complete_missing.sh small"
        ;;
    
    small)
        echo "SMALL BATCH MODE - Conservative approach"
        echo "Submitting G-41 first 400 samples in batches of 20"
        echo "----------------------------------------"
        echo ""
        
        # G-41: First 400 samples in batches of 20 (20 messages)
        echo "Submitting G-41: First 400 samples (20 batches of 20)"
        python scripts/submit.py \
            --generator "G-41_grid_highest_cost_data-generator" \
            --samples 400 \
            --batch-size 20 \
            --seed 435615170 \
            --output-format tar
        
        echo ""
        echo "✓ G-41 first 400 samples submitted"
        echo ""
        echo "Waiting 60 seconds before checking status..."
        sleep 60
        
        python scripts/monitor.py
        
        echo ""
        echo "Next steps:"
        echo "  1. Verify these 400 samples uploaded successfully"
        echo "  2. Check DLQ is empty or has expected messages"
        echo "  3. If successful, run: ./complete_missing.sh full"
        ;;
    
    full)
        echo "FULL RESUBMISSION - All missing samples"
        echo "Using batch size of 20 for maximum safety"
        echo "Note: Will resubmit ALL 10k samples for each generator"
        echo "       (S3 will overwrite existing files)"
        echo "----------------------------------------"
        echo ""
        
        # G-41: All 10,000 samples in batches of 20 (500 messages)
        echo "Submitting G-41: All 10,000 samples (500 batches of 20)"
        python scripts/submit.py \
            --generator "G-41_grid_highest_cost_data-generator" \
            --samples 10000 \
            --batch-size 20 \
            --seed 435615170 \
            --output-format tar
        
        echo "✓ Submitted G-41"
        echo "----------------------------------------"
        
        # G-16: All 10k samples (will overwrite 9900 existing, add 100 missing)
        echo "Submitting G-16: All 10,000 samples (500 batches of 20)"
        python scripts/submit.py \
            --generator "G-16_grid_go_through_block_data-generator" \
            --samples 10000 \
            --batch-size 20 \
            --seed 150878176 \
            --output-format tar
        
        echo "✓ Submitted G-16"
        echo "----------------------------------------"
        
        # G-32: All 10k samples
        echo "Submitting G-32: All 10,000 samples (500 batches of 20)"
        python scripts/submit.py \
            --generator "G-32_undirected_graph_navigation_data-generator" \
            --samples 10000 \
            --batch-size 20 \
            --seed 484679478 \
            --output-format tar
        
        echo "✓ Submitted G-32"
        echo "----------------------------------------"
        
        # G-33: All 10k samples
        echo "Submitting G-33: All 10,000 samples (500 batches of 20)"
        python scripts/submit.py \
            --generator "G-33_visual_jenga_data-generator" \
            --samples 10000 \
            --batch-size 20 \
            --seed 915165316 \
            --output-format tar
        
        echo "✓ Submitted G-33"
        echo "----------------------------------------"
        
        # G-40: All 10k samples
        echo "Submitting G-40: All 10,000 samples (500 batches of 20)"
        python scripts/submit.py \
            --generator "G-40_combined_objects_spinning_data-generator" \
            --samples 10000 \
            --batch-size 20 \
            --seed 848843640 \
            --output-format tar
        
        echo "✓ Submitted G-40"
        echo "----------------------------------------"
        
        echo ""
        echo "All missing generators re-submitted!"
        echo ""
        echo "Summary:"
        echo "  G-41: 500 batches (10,000 samples - all new)"
        echo "  G-16: 500 batches (10,000 samples - 100 new, 9900 overwrite)"
        echo "  G-32: 500 batches (10,000 samples - 200 new, 9800 overwrite)"
        echo "  G-33: 500 batches (10,000 samples - 100 new, 9900 overwrite)"
        echo "  G-40: 500 batches (10,000 samples - 100 new, 9900 overwrite)"
        echo "  Total: 2,500 messages (50,000 samples total, 10,500 actually missing)"
        echo ""
        echo "Monitor progress:"
        echo "  python scripts/monitor.py --watch"
        ;;
    
    *)
        echo "Invalid mode: $MODE"
        echo ""
        echo "Usage: ./complete_missing.sh [test|small|full]"
        echo ""
        echo "Modes:"
        echo "  test  - Submit 1 test batch (20 samples) for G-41"
        echo "  small - Submit first 400 samples of G-41 (20 batches of 20)"
        echo "  full  - Submit ALL missing generators (20 samples per batch)"
        echo ""
        echo "Recommended workflow:"
        echo "  1. Fix code issues first (generator.py, validator.py)"
        echo "  2. Redeploy Lambda"
        echo "  3. Run: ./complete_missing.sh test"
        echo "  4. Verify test succeeded"
        echo "  5. Run: ./complete_missing.sh small"
        echo "  6. Verify 400 samples succeeded"
        echo "  7. Run: ./complete_missing.sh full"
        exit 1
        ;;
esac

echo ""
echo "========================================================================"
