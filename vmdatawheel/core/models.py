"""Pydantic models - Single source of truth for data structures.

NO try-catch blocks - Pydantic validates automatically and raises ValidationError.
"""

from pydantic import BaseModel, Field


class TaskMessage(BaseModel):
    """SQS task message schema."""

    type: str = Field(..., min_length=1, description="Generator name")
    num_samples: int = Field(..., gt=0, le=1000, description="Number of samples to generate")
    start_index: int = Field(default=0, ge=0, description="Starting sample index")
    seed: int | None = Field(default=None, ge=0, description="Random seed for reproducibility")
    output_format: str = Field(default="files", pattern="^(files|tar)$", description="Output format")
    output_bucket: str | None = Field(default=None, description="Override S3 bucket")


class TaskResult(BaseModel):
    """Task execution result."""

    generator: str
    samples_uploaded: int
    sample_ids: list[str]
    tar_files: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Sample validation result."""

    sample_id: str
    valid: bool
    missing_required: list[str] = Field(default_factory=list)
    extra_files: list[str] = Field(default_factory=list)
    file_sizes: dict[str, int] = Field(default_factory=dict)


class GeneratorMetrics(BaseModel):
    """Generator performance metrics."""

    generator: str
    samples_generated: int
    duration_seconds: float
    peak_memory_mb: float
    seconds_per_sample: float

