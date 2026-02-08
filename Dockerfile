FROM public.ecr.aws/lambda/python:3.11

# System dependencies (required by cairosvg and for building packages)
RUN yum install -y cairo pango gcc gcc-c++ make python3-devel

# Python dependencies
# Note: awscli not installed to avoid boto3/botocore version conflicts
# AWS Lambda runtime already includes AWS CLI if needed
COPY requirements-all.txt .
RUN pip install --upgrade pip && \
    pip install "numpy>=1.26.0,<2.0.0" && \
    pip install "pyarrow<17.0.0" && \
    pip install -r requirements-all.txt

# All generator code
COPY generators/ /opt/generators/

# Lambda handler module
COPY vbvrdatafactory/ ./vbvrdatafactory/

CMD ["vbvrdatafactory.lambda_handler.handler.handler"]
