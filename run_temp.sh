#!/bin/bash

# Run 10,000 samples for specific generators
# Usage: ./run_temp.sh

set -e

GENERATORS=(
    "G-1_object_trajectory_data-generator"
    "G-2_reorder_objects_data-generator"
    "G-3_stable_sort_data-generator"
    "G-4_identify_objects_data-generator"
    "G-5_multi_object_placement_data-generator"
    "G-6_resize_object-data-generator"
    "G-7_return_to_correct_bin_data-generator"
    "G-8_track_object_movement_data-generator"
    "G-9_identify_objects_in_region_data-generator"
    "G-11_handle_object_reappearance_data-generator"
    "G-12_grid_obtaining_award_data-generator"
    "G-13_grid_number_sequence_data-generator"
    "G-14_grid_color_sequence-data-generator"
    "G-15_grid_avoid_obstacles_data-generator"
    "G-16_grid_go_through_block_data-generator"
    "G-17_grid_avoid_red_block_data-generator"
    "G-18_grid_shortest_path_data-generator"
    "G-19_sort_objects_by_rule_data-generator"
    "G-21_multiple_occlusions_vertical_data-generator"
    "G-22_attention_shift_same_data-generator"
    "G-23_combined_objects_no_spin_data-generator"
    "G-25_seperate_object_spinning_data-generator"
    "G-26_maintain_object_identity_different_objects_data-generator"
    "G-27_read_the_chart_data_semantic_comprehension_data-generator"
    "G-29_chart_extreme_with_data_data-generator"
    "G-30_chart_extreme_without_data_data-generator"
    "G-31_directed_graph_navigation_data-generator"
    "G-32_undirected_graph_navigation_data-generator"
    "G-33_visual_jenga_data-generator"
    "G-34_object_packing_data-generator"
    "G-35_hit_target_after_bounce_data-generator"
    "G-36_multiple_occlusions_horizontal_data-generator"
    "G-37_symmetry_random_data-generator"
    "G-38_symmetry_shape_data-generator"
    "G-39_attention_shift_different_data-generator"
    "G-40_combined_objects_spinning_data-generator"
    "G-41_grid_highest_cost_data-generator"
    "G-42_grid_lowest_cost_data-generator"
    "G-43_understand_scene_structure_data-generator"
    "G-45_key_door_matching_data-generator"
    "G-46_find_keys_and_open_doors_data-generator"
    "G-48_multiple_bounces_data-generator"
    "G-49_complete_missing_contour_segments_data-generator"
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
