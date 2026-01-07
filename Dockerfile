FROM public.ecr.aws/lambda/python:3.11

# System dependencies (required by cairosvg)
RUN yum install -y cairo pango

# Python dependencies
COPY requirements-all.txt .
RUN pip install -r requirements-all.txt

# All generator code
COPY generators/ /opt/generators/

# Lambda handler
COPY lambda_handler.py .

CMD ["lambda_handler.handler"]
