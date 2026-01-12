"""CDK Stack for VM Dataset Pipeline infrastructure."""

import os

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_ecr_assets as ecr_assets,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_sqs as sqs,
)
from aws_cdk.aws_lambda_event_sources import SqsEventSource
from constructs import Construct

# Project root directory (where Dockerfile is located)
# deployment/cdk/stacks/pipeline_stack.py → go up 3 levels to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class PipelineStack(Stack):
    """CDK Stack defining the VM Dataset Pipeline infrastructure."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 Bucket for output data
        self.output_bucket = s3.Bucket(
            self,
            "OutputBucket",
            bucket_name=f"vm-dataset-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.RETAIN,
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        # Dead Letter Queue
        self.dlq = sqs.Queue(
            self,
            "DeadLetterQueue",
            queue_name="vm-dataset-pipeline-dlq",
            retention_period=Duration.days(14),
        )

        # Main SQS Queue
        # visibility_timeout should be slightly higher than Lambda timeout
        self.queue = sqs.Queue(
            self,
            "TaskQueue",
            queue_name="vm-dataset-pipeline-queue",
            visibility_timeout=Duration.minutes(16),
            retention_period=Duration.days(4),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.dlq,
            ),
        )

        # Lambda configuration from context
        lambda_memory = self.node.try_get_context("lambdaMemoryMB") or 10240
        lambda_timeout = self.node.try_get_context("lambdaTimeoutMinutes") or 15

        # Lambda Function
        self.lambda_function = lambda_.DockerImageFunction(
            self,
            "GeneratorFunction",
            function_name="vm-dataset-pipeline-generator",
            code=lambda_.DockerImageCode.from_image_asset(
                PROJECT_ROOT,
                platform=ecr_assets.Platform.LINUX_AMD64,
            ),
            memory_size=lambda_memory,
            timeout=Duration.minutes(lambda_timeout),
            environment={
                "OUTPUT_BUCKET": self.output_bucket.bucket_name,
                "GENERATORS_PATH": "/opt/generators",
            },
        )

        # Grant Lambda permissions
        self.output_bucket.grant_read_write(self.lambda_function)

        # Grant S3 write permission to all buckets
        self.lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:PutObject",
                    "s3:PutObjectAcl",
                    "s3:DeleteObject",
                    "s3:AbortMultipartUpload",
                ],
                resources=["arn:aws:s3:::*/*"],
            )
        )

        # Grant CloudWatch metrics permission
        self.lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )

        # Add SQS trigger (max_concurrency limits concurrent Lambda invocations from SQS)
        sqs_max_concurrency = self.node.try_get_context("sqsMaxConcurrency") or 990
        self.lambda_function.add_event_source(
            SqsEventSource(
                self.queue,
                batch_size=1,
                max_concurrency=sqs_max_concurrency,
            )
        )

        # Outputs
        CfnOutput(
            self,
            "QueueUrl",
            value=self.queue.queue_url,
            description="SQS Queue URL for submitting tasks",
        )
        CfnOutput(
            self,
            "DlqUrl",
            value=self.dlq.queue_url,
            description="Dead Letter Queue URL",
        )
        CfnOutput(
            self,
            "BucketName",
            value=self.output_bucket.bucket_name,
            description="S3 bucket for output data",
        )
        CfnOutput(
            self,
            "LambdaFunctionName",
            value=self.lambda_function.function_name,
            description="Lambda function name",
        )
