#!/bin/bash

# Check completion status for run_temp_3.sh generators
# Usage: ./check_temp_3.sh

echo "========================================================================"
echo "Checking Completion Status - run_temp_3.sh Generators"
echo "========================================================================"
echo ""

bucket="s3://vm-dataset-956728988776-us-east-2-20260115-084225/questions/"

check_generator() {
    local gen=$1
    local expected=$2
    
    count=$(aws s3 ls "${bucket}${gen}/" 2>/dev/null | grep '.tar.gz' | wc -l)
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
    
    printf "%-12s %-70s %5d / %5d tars (%3d%%) - Missing: %5d samples\n" \
        "$status" "$gen" "$count" "$((expected/100))" "$pct" "$missing"
}

echo "Checking all generators from run_temp_3.sh..."
echo "------------------------------------------------------------------------"

# O-series generators
check_generator "O-17_color_subtraction_data-generator" 10000
check_generator "O-18_glass_refraction_data-generator" 10000
check_generator "O-19_mirror_reflection_data-generator" 10000
check_generator "O-21_construction_blueprint_data-generator" 10000
check_generator "O-23_domino_chain_branch_path_prediction_data-generator" 10000
check_generator "O-24_domino_chain_gap_analysis_data-generator" 10000
check_generator "O-25_LEGO_construction_assembly_data-generator" 10000
check_generator "O-29_ballcolor_data-generator" 10000
check_generator "O-30_bookshelf_data-generator" 10000
check_generator "O-31_ball_eating_data-generator" 10000
check_generator "O-32_rolling_ball_data-generator" 10000
check_generator "O-33_counting_object_data-generator" 10000
check_generator "O-34_dot_to_dot_task_data-generator" 10000
check_generator "O-36_grid_shift_data-generator" 10000
check_generator "O-37_light_sequence_data-generator" 10000
check_generator "O-38_majority_color_data-generator" 10000
check_generator "O-44_rotation_puzzle_data-generator" 10000
check_generator "O-45_sequence_completion_data-generator" 10000
check_generator "O-47_sliding_puzzle_data-generator" 10000
check_generator "O-52_traffic_light_data-generator" 10000
check_generator "O-53_clock_data-generator" 10000
check_generator "O-55_rotation_data-generator" 10000
check_generator "O-66_animal_color_sorting_data-generator" 10000
check_generator "O-75_communicating_vessels_data-generator" 10000
check_generator "O-87_fluid_diffusion_reasoning_data-generator" 10000

# G-series generators
check_generator "G-44_bfs_data-generator" 10000
check_generator "G-157_separate_and_place_rhombuses_non_square_data-generator" 10000

echo ""
echo "========================================================================"
echo "Summary"
echo "========================================================================"

# Count statuses
complete=0
incomplete=0
missing=0

for gen in \
    "O-17_color_subtraction_data-generator" \
    "O-18_glass_refraction_data-generator" \
    "O-19_mirror_reflection_data-generator" \
    "O-21_construction_blueprint_data-generator" \
    "O-23_domino_chain_branch_path_prediction_data-generator" \
    "O-24_domino_chain_gap_analysis_data-generator" \
    "O-25_LEGO_construction_assembly_data-generator" \
    "O-29_ballcolor_data-generator" \
    "O-30_bookshelf_data-generator" \
    "O-31_ball_eating_data-generator" \
    "O-32_rolling_ball_data-generator" \
    "O-33_counting_object_data-generator" \
    "O-34_dot_to_dot_task_data-generator" \
    "O-36_grid_shift_data-generator" \
    "O-37_light_sequence_data-generator" \
    "O-38_majority_color_data-generator" \
    "O-44_rotation_puzzle_data-generator" \
    "O-45_sequence_completion_data-generator" \
    "O-47_sliding_puzzle_data-generator" \
    "O-52_traffic_light_data-generator" \
    "O-53_clock_data-generator" \
    "O-55_rotation_data-generator" \
    "O-66_animal_color_sorting_data-generator" \
    "O-75_communicating_vessels_data-generator" \
    "O-87_fluid_diffusion_reasoning_data-generator" \
    "G-44_bfs_data-generator" \
    "G-157_separate_and_place_rhombuses_non_square_data-generator"
do
    count=$(aws s3 ls "${bucket}${gen}/" 2>/dev/null | grep '.tar.gz' | wc -l)
    if [ $count -eq 100 ]; then
        complete=$((complete + 1))
    elif [ $count -eq 0 ]; then
        missing=$((missing + 1))
    else
        incomplete=$((incomplete + 1))
    fi
done

echo "Total generators: 27"
echo "  ✓ Complete:    $complete"
echo "  ⚠ Incomplete:  $incomplete"
echo "  ✗ Missing:     $missing"

echo ""
echo "========================================================================"
echo "Queue Status"
echo "========================================================================"
python scripts/monitor.py

echo ""
echo "========================================================================"
