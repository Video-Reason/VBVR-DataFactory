#!/bin/bash
# Collect all requirements.txt from VBVR-DataFactory repos

set -e

if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed."
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

ORG="VBVR-DataFactory"
OUTPUT_FILE="../requirements-all.txt"
TEMP_DIR=$(mktemp -d)

echo "Collecting requirements from $ORG repos..."

# Filter: G-1 to G-50 only
repos=$(gh repo list $ORG --limit 300 --json name -q '.[].name' | grep -E '^G-([1-9]|[1-4][0-9]|50)_')

for repo in $repos; do
    echo -n "  $repo: "
    if gh api "repos/$ORG/$repo/contents/requirements.txt" --jq '.content' 2>/dev/null | base64 -d > "$TEMP_DIR/$repo.txt" 2>/dev/null; then
        echo "found"
    else
        rm -f "$TEMP_DIR/$repo.txt"
        echo "no requirements.txt"
    fi
done

echo ""
echo "Merging and deduplicating..."

cat "$TEMP_DIR"/*.txt 2>/dev/null | \
    grep -v '^#' | \
    grep -v '^$' | \
    grep -v '^\s*$' | \
    sed 's/[[:space:]]*$//' | \
    sort -u > "$OUTPUT_FILE.raw"

echo "Raw dependencies saved to $OUTPUT_FILE.raw"
echo "Please manually review and update $OUTPUT_FILE"

rm -rf "$TEMP_DIR"
