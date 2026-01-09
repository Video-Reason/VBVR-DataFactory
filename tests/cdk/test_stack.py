"""Tests for CDK stack."""

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from cdk.stacks.pipeline_stack import PipelineStack


@pytest.fixture
def template():
    """Create CDK template for testing."""
    app = cdk.App()
    stack = PipelineStack(app, "TestStack")
    return Template.from_stack(stack)


class TestPipelineStack:
    """Tests for PipelineStack."""

    def test_s3_bucket_created(self, template):
        """Test that S3 bucket is created."""
        template.resource_count_is("AWS::S3::Bucket", 1)

    def test_sqs_queues_created(self, template):
        """Test that SQS queues are created (main + DLQ)."""
        template.resource_count_is("AWS::SQS::Queue", 2)

    def test_lambda_function_created(self, template):
        """Test that Lambda function is created."""
        template.resource_count_is("AWS::Lambda::Function", 1)

    def test_lambda_has_sqs_event_source(self, template):
        """Test that Lambda has SQS event source mapping."""
        template.resource_count_is("AWS::Lambda::EventSourceMapping", 1)

    def test_lambda_memory_size(self, template):
        """Test Lambda memory configuration."""
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {"MemorySize": 10240},
        )

    def test_lambda_timeout(self, template):
        """Test Lambda timeout configuration."""
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {"Timeout": 900},  # 15 minutes in seconds
        )
