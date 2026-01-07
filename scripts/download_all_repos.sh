#!/bin/bash
# Download all generator repos from vm-dataset organization

set -e

ORG="vm-dataset"
OUTPUT_DIR="../generators"

mkdir -p "$OUTPUT_DIR"

echo "Downloading all repos from $ORG..."

repos=$(gh repo list $ORG --limit 300 --json name -q '.[].name' | grep -iE 'generator|Generator')

total=$(echo "$repos" | wc -l | tr -d ' ')
count=0

for repo in $repos; do
    count=$((count + 1))
    echo "[$count/$total] $repo"

    if [ -d "$OUTPUT_DIR/$repo" ]; then
        echo "  Updating..."
        git -C "$OUTPUT_DIR/$repo" pull --quiet 2>/dev/null || true
    else
        gh repo clone "$ORG/$repo" "$OUTPUT_DIR/$repo" -- --depth 1 --quiet
    fi
done

echo ""
echo "Done! Downloaded $count repos to $OUTPUT_DIR/"
du -sh "$OUTPUT_DIR"
