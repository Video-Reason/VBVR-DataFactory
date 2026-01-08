#!/bin/bash
# Build and push Docker image to ECR

set -e

# Configuration - UPDATE THESE
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-YOUR_ACCOUNT_ID}"
AWS_REGION="${AWS_REGION:-us-east-2}"
REPO_NAME="vm-dataset-generator"

IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME"

echo "Building Docker image..."
cd "$(dirname "$0")/.."
docker build -t $REPO_NAME .

echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

echo "Creating ECR repository (if not exists)..."
aws ecr create-repository --repository-name $REPO_NAME --region $AWS_REGION 2>/dev/null || true

echo "Tagging image..."
docker tag $REPO_NAME:latest $IMAGE_URI:latest

echo "Pushing to ECR..."
docker push $IMAGE_URI:latest

echo ""
echo "Done!"
echo "Image URI: $IMAGE_URI:latest"
