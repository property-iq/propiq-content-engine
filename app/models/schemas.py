from typing import Optional

from pydantic import BaseModel, Field


# Path-component patterns — these flow unvalidated into filesystem paths in
# app/routers/generate.py (template loaded via settings.templates_dir / req.template;
# output written to settings.output_dir / today / f"{category}-{entity_slug}").
# Excluding `/` (beyond the single template separator), `..`, `\`, leading `/`,
# and null bytes makes path traversal structurally impossible post-validation.
# See issue #8.
_SLUG_PATTERN = r"^[a-z0-9-]+$"
_TEMPLATE_PATTERN = r"^[a-z0-9]+/[a-z0-9-]+$"


class GenerateRequest(BaseModel):
    category: str = Field(
        ...,
        description="Content category",
        examples=["market-insight", "news-commentary", "data-highlight"],
        pattern=_SLUG_PATTERN,
        max_length=64,
    )
    entity_type: str = Field(
        ...,
        description="Entity type to feature",
        examples=["area", "building", "developer", "market"],
    )
    entity_slug: str = Field(
        ...,
        description="Entity slug identifier",
        examples=["dubai-marina", "jumeirah-village-circle"],
        pattern=_SLUG_PATTERN,
        max_length=128,
    )
    template: str = Field(
        default="story/dark-01",
        description="Template path relative to templates/",
        pattern=_TEMPLATE_PATTERN,
        max_length=64,
    )
    metric: str = Field(
        default="price",
        description="Primary metric to visualize",
        examples=["price", "volume", "growth", "yield", "rent"],
    )
    chart_intent: str = Field(
        default="trend",
        description="Chart intent for charts-api",
        examples=["trend", "hbar", "scatter", "boxplot", "matrix", "table", "quadrant"],
    )
    period: str = Field(
        default="T12M",
        description="Data period",
        examples=["T3M", "T6M", "T12M"],
    )
    property_type: str = Field(
        default="ALL",
        description="Property type filter",
        examples=["ALL", "Apartment", "Villa"],
    )


class ContentPackage(BaseModel):
    output_dir: str = Field(..., description="Path to generated content package")
    image_path: str = Field(..., description="Path to rendered PNG")
    caption_ig: str = Field(..., description="Instagram caption")
    caption_x: str = Field(..., description="X/Twitter caption")
    metadata: dict = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    status: str = "ok"
    package: ContentPackage


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "propiq-content-engine"
    version: str = "0.1.0"
    upstream: dict = Field(default_factory=dict)
