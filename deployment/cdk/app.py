#!/usr/bin/env python3
"""CDK application entry point."""

import aws_cdk as cdk

from deployment.cdk.stacks.pipeline_stack import PipelineStack

app = cdk.App()

PipelineStack(
    app,
    "VBVRDataFactoryPipelineStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-2",
    ),
)

app.synth()
