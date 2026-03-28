"""Content generation endpoint — orchestrates the full pipeline."""

import json
import logging
from datetime import date
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.engine.composer import compose
from app.engine.planner import plan_daily_content
from app.engine.renderer import render_svg_to_png
from app.models.schemas import ContentPackage, GenerateRequest, GenerateResponse
from app.services import charts_client, data_client, llm, news_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generate"])


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    """Generate a content package from data + charts + LLM copy."""

    # 1. Load template config for dimensions and prompt
    tpl_dir = settings.templates_dir / req.template
    config_path = tpl_dir / "config.yaml"
    if not config_path.exists():
        raise HTTPException(404, f"Template not found: {req.template}")

    with open(config_path) as f:
        tpl_config = yaml.safe_load(f)

    dimensions = tpl_config["meta"]["dimensions"]
    prompt_template = tpl_config.get("prompt", "")

    # 2. Fetch data from upstream services
    try:
        if req.entity_type == "area":
            performance = await data_client.get_area_performance(
                req.entity_slug, req.period, req.property_type
            )
        elif req.entity_type == "building":
            performance = await data_client.get_building_performance(
                req.entity_slug, req.period
            )
        elif req.entity_type == "market":
            performance = await data_client.get_market_summary(
                req.period, req.property_type
            )
        else:
            raise HTTPException(400, f"Unsupported entity_type: {req.entity_type}")
    except Exception as e:
        logger.error("Failed to fetch performance data: %s", e)
        raise HTTPException(502, f"Data API error: {e}")

    # 3. Fetch chart PNG
    try:
        chart_png = await charts_client.get_chart_png(
            intent=req.chart_intent,
            metric=req.metric,
            entity_type=req.entity_type,
            entity_slug=req.entity_slug,
            property_type=req.property_type,
        )
    except Exception as e:
        logger.error("Failed to fetch chart PNG: %s", e)
        raise HTTPException(502, f"Charts API error: {e}")

    # 4. Fetch related news (best-effort, don't fail if unavailable)
    headlines = []
    try:
        if req.entity_type == "area":
            headlines = news_client.get_headlines_for_area(req.entity_slug, limit=3)
        else:
            headlines = news_client.get_top_headlines(limit=3)
    except Exception as e:
        logger.warning("News fetch failed (non-fatal): %s", e)

    # 5. Generate text via LLM
    context_data = {
        "entity_type": req.entity_type,
        "entity_slug": req.entity_slug,
        "category": req.category,
        "metric": req.metric,
        "period": req.period,
        "property_type": req.property_type,
        "performance": performance.get("data", performance),
        "headlines": [
            {"title": h.get("title"), "summary": h.get("summary")}
            for h in headlines[:3]
        ],
    }

    try:
        copy = await llm.generate_copy(prompt_template, context_data)
    except Exception as e:
        logger.error("LLM generation failed: %s", e)
        raise HTTPException(502, f"LLM error: {e}")

    # 6. Compose SVG
    svg_content = compose(
        template_path=req.template,
        content={"title": copy["title"], "body": copy["body"]},
        chart_png=chart_png,
    )

    # 7. Render to PNG
    png_bytes = await render_svg_to_png(
        svg_content,
        width=dimensions["width"],
        height=dimensions["height"],
    )

    # 8. Write output package
    today = date.today().isoformat()
    package_dir = settings.output_dir / today / f"{req.category}-{req.entity_slug}"
    package_dir.mkdir(parents=True, exist_ok=True)

    # Determine format name from template path
    format_name = req.template.split("/")[0]  # e.g. "story"
    image_path = package_dir / f"{format_name}.png"
    image_path.write_bytes(png_bytes)

    caption_ig = copy.get("caption_ig", "")
    caption_x = copy.get("caption_x", "")
    (package_dir / "caption-ig.md").write_text(caption_ig)
    (package_dir / "caption-x.md").write_text(caption_x)

    metadata = {
        "generated_at": date.today().isoformat(),
        "template": req.template,
        "category": req.category,
        "entity_type": req.entity_type,
        "entity_slug": req.entity_slug,
        "metric": req.metric,
        "period": req.period,
        "property_type": req.property_type,
        "title": copy["title"],
        "body": copy["body"],
    }
    (package_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    return GenerateResponse(
        status="ok",
        package=ContentPackage(
            output_dir=str(package_dir),
            image_path=str(image_path),
            caption_ig=caption_ig,
            caption_x=caption_x,
            metadata=metadata,
        ),
    )


@router.post("/generate-daily")
async def generate_daily(max_items: int = 5, template: str = "story/dark-01"):
    """Auto-generate a batch of content for today.

    The planner queries upstream services to find noteworthy data points,
    then generates content packages for each.
    """
    plan = await plan_daily_content(max_items=max_items, template=template)

    results = []
    errors = []

    for req in plan:
        try:
            result = await generate(req)
            results.append({
                "category": req.category,
                "entity": f"{req.entity_type}/{req.entity_slug}",
                "status": "ok",
                "output_dir": result.package.output_dir,
            })
        except Exception as e:
            logger.error("Failed to generate %s/%s: %s", req.category, req.entity_slug, e)
            errors.append({
                "category": req.category,
                "entity": f"{req.entity_type}/{req.entity_slug}",
                "error": str(e),
            })

    return {
        "status": "ok" if not errors else "partial",
        "planned": len(plan),
        "generated": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }
