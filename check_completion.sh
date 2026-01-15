#!/bin/bash

# Check completion status of specific generators
# Usage: ./check_completion.sh

echo "========================================================================"
echo "Checking Completion Status"
echo "========================================================================"
echo ""

bucket="s3://vm-dataset-956728988776-us-east-2-20260115-084225/questions/"

check_generator() {
    local gen=$1
    local expected=$2
    
    count=$(aws s3 ls "${bucket}${gen}/" | grep '.tar.gz' | wc -l)
    samples=$((count * 100))
    pct=$((samples * 100 / expected))
    missing=$((expected - samples))
    
    if [ $count -eq $((expected / 100)) ]; then
        status="✓ COMPLETE"
    elif [ $count -eq 0 ]; then
        status="✗ MISSING"
    else
        status="⚠ INCOMPLETE"
    fi
    
    printf "%-12s %-60s %5d / %5d tars (%3d%%) - Missing: %5d samples\n" \
        "$status" "$gen" "$count" "$((expected/100))" "$pct" "$missing"
}

echo "Checking incomplete generators..."
echo "------------------------------------------------------------------------"

check_generator "G-16_grid_go_through_block_data-generator" 10000
check_generator "G-32_undirected_graph_navigation_data-generator" 10000
check_generator "G-33_visual_jenga_data-generator" 10000
check_generator "G-40_combined_objects_spinning_data-generator" 10000
check_generator "G-41_grid_highest_cost_data-generator" 10000

echo ""
echo "========================================================================"
echo "Queue Status"
echo "========================================================================"
python scripts/monitor.py

echo ""
echo "========================================================================"
echo "Specific Missing Ranges"
echo "========================================================================"

echo ""
echo "G-16 missing ranges:"
aws s3 ls "${bucket}G-16_grid_go_through_block_data-generator/" | \
    grep '.tar.gz' | \
    awk '{print $4}' | \
    sed 's/.*_0*\([0-9]*\)-0*\([0-9]*\)\.tar\.gz/\1/' | \
    sort -n > /tmp/g16_existing.txt

for i in {0..9900..100}; do
    printf "%d\n" $i
done > /tmp/g16_expected.txt

missing=$(comm -13 /tmp/g16_existing.txt /tmp/g16_expected.txt)
if [ -z "$missing" ]; then
    echo "  None - COMPLETE!"
else
    echo "$missing" | while read start; do
        end=$((start + 99))
        printf "  %05d-%05d.tar.gz\n" $start $end
    done
fi

echo ""
echo "G-32 missing ranges:"
aws s3 ls "${bucket}G-32_undirected_graph_navigation_data-generator/" | \
    grep '.tar.gz' | \
    awk '{print $4}' | \
    sed 's/.*_0*\([0-9]*\)-0*\([0-9]*\)\.tar\.gz/\1/' | \
    sort -n > /tmp/g32_existing.txt

for i in {0..9900..100}; do
    printf "%d\n" $i
done > /tmp/g32_expected.txt

missing=$(comm -13 /tmp/g32_existing.txt /tmp/g32_expected.txt)
if [ -z "$missing" ]; then
    echo "  None - COMPLETE!"
else
    echo "$missing" | while read start; do
        end=$((start + 99))
        printf "  %05d-%05d.tar.gz\n" $start $end
    done
fi

echo ""
echo "G-33 missing ranges:"
aws s3 ls "${bucket}G-33_visual_jenga_data-generator/" | \
    grep '.tar.gz' | \
    awk '{print $4}' | \
    sed 's/.*_0*\([0-9]*\)-0*\([0-9]*\)\.tar\.gz/\1/' | \
    sort -n > /tmp/g33_existing.txt

for i in {0..9900..100}; do
    printf "%d\n" $i
done > /tmp/g33_expected.txt

missing=$(comm -13 /tmp/g33_existing.txt /tmp/g33_expected.txt)
if [ -z "$missing" ]; then
    echo "  None - COMPLETE!"
else
    echo "$missing" | while read start; do
        end=$((start + 99))
        printf "  %05d-%05d.tar.gz\n" $start $end
    done
fi

echo ""
echo "G-40 missing ranges:"
aws s3 ls "${bucket}G-40_combined_objects_spinning_data-generator/" | \
    grep '.tar.gz' | \
    awk '{print $4}' | \
    sed 's/.*_0*\([0-9]*\)-0*\([0-9]*\)\.tar\.gz/\1/' | \
    sort -n > /tmp/g40_existing.txt

for i in {0..9900..100}; do
    printf "%d\n" $i
done > /tmp/g40_expected.txt

missing=$(comm -13 /tmp/g40_existing.txt /tmp/g40_expected.txt)
if [ -z "$missing" ]; then
    echo "  None - COMPLETE!"
else
    echo "$missing" | while read start; do
        end=$((start + 99))
        printf "  %05d-%05d.tar.gz\n" $start $end
    done
fi

echo ""
echo "G-41 status:"
count=$(aws s3 ls "${bucket}G-41_grid_highest_cost_data-generator/" 2>/dev/null | grep '.tar.gz' | wc -l)
if [ $count -eq 0 ]; then
    echo "  Still MISSING - 0 / 100 tars"
elif [ $count -eq 100 ]; then
    echo "  ✓ COMPLETE - 100 / 100 tars"
else
    echo "  ⚠ INCOMPLETE - $count / 100 tars"
fi

echo ""
echo "========================================================================"
