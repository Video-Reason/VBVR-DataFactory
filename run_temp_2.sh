#!/bin/bash

# Run 10,000 samples for specific generators (batch 2)
# Usage: ./run_temp_2.sh

set -e

GENERATORS=(
    "G-50_suppress_spurious_edges_data-generator"
    "G-51_predict_next_color_data-generator"
    "G-131_select_next_figure_increasing_size_sequence_data-generator"
    "G-132_find_fragment_for_gap_filling_data-generator"
    "G-133_select_next_figure_decreasing_size_sequence_data-generator"
    "G-134_select_next_figure_large_small_alternating_sequence_data-generator"
    "G-137_identify_figure_in_overlapping_area_data-generator"
    "G-138_spot_unique_non_repeated_color_data-generator"
    "G-141_identify_polygon_with_most_sides_data-generator"
    "G-143_select_box_with_most_dots_data-generator"
    "G-146_circle_all_squares_from_mixed_shapes_data-generator"
    "G-162_locate_twelve_o_clock_arrows_data-generator"
    "G-163_identify_one_and_nine_data-generator"
    "G-165_mark_tangent_point_after_motion_data-generator"
    "G-166_highlight_horizontal_lines_data-generator"
    "G-194_construct_concentric_ring_data-generator"
    "G-195_select_nearest_2_1_rectangle_data-generator"
    "G-198_mark_right_angled_triangles_data-generator"
    "G-199_locate_line_intersections_data-generator"
    "G-200_circle_maximum_value_data-generator"
    "G-214_mark_black_beads_data-generator"
    "O-1_color_mixing_data-generator"
    "O-3_symbol_reordering_data-generator"
    "O-4_symbol_substitution_data-generator"
    "O-7_shape_color_change_data-generator"
    "O-8_shape_rotation_data-generator"
    "O-10_shape_outline_fill_data-generator"
    "O-12_shape_color_then_scale_data-generator"
    "O-13_shape_outline_then_move_data-generator"
    "O-14_shape_scale_then_outline_data-generator"
    "O-15_ball_bounces_given_time_data-generator"
    "O-16_color_addition_data-generator"
)

SAMPLES=10000
BATCH_SIZE=100

echo "Starting task submission for ${#GENERATORS[@]} generators (batch 2)"
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
