#!/bin/bash

# Run 10,000 samples for specific generators
# Usage: ./run_temp_3.sh

set -e

GENERATORS=(
    "O-17_color_subtraction_data-generator"
    "O-18_glass_refraction_data-generator"
    "O-19_mirror_reflection_data-generator"
    "O-21_construction_blueprint_data-generator"
    "O-23_domino_chain_branch_path_prediction_data-generator"
    "O-24_domino_chain_gap_analysis_data-generator"
    "O-25_LEGO_construction_assembly_data-generator"
    "O-29_ballcolor_data-generator"
    "O-30_bookshelf_data-generator"
    "O-31_ball_eating_data-generator"
    "O-32_rolling_ball_data-generator"
    "O-33_counting_object_data-generator"
    "O-34_dot_to_dot_task_data-generator"
    "O-36_grid_shift_data-generator"
    "O-37_light_sequence_data-generator"
    "O-38_majority_color_data-generator"
    "O-44_rotation_puzzle_data-generator"
    "O-45_sequence_completion_data-generator"
    "O-47_sliding_puzzle_data-generator"
    "O-52_traffic_light_data-generator"
    "O-53_clock_data-generator"
    "O-55_rotation_data-generator"
    "O-66_animal_color_sorting_data-generator"
    "O-75_communicating_vessels_data-generator"
    "O-87_fluid_diffusion_reasoning_data-generator"
    "G-44_bfs_data-generator"
    "G-157_separate_and_place_rhombuses_non_square_data-generator"
)

SAMPLES=10000
BATCH_SIZE=100

echo "Starting task submission for ${#GENERATORS[@]} generators"
echo "Samples per generator: $SAMPLES"
echo "Batch size: $BATCH_SIZE"
echo "Output format: tar"
echo "----------------------------------------"

for generator in "${GENERATORS[@]}"; do
    echo "Submitting tasks for: $generator"
    python scripts/submit.py \
        --generator "$generator" \
        --samples $SAMPLES \
        --batch-size $BATCH_SIZE \
        --output-format tar
    
    echo "✓ Submitted $generator"
    echo "----------------------------------------"
done

echo "All tasks submitted successfully!"
echo "Total generators: ${#GENERATORS[@]}"
echo "Total samples: $((${#GENERATORS[@]} * $SAMPLES))"
echo ""
echo "Monitor progress with:"
echo "  python scripts/monitor.py --watch"
