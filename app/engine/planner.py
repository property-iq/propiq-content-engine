"""Content planner — decides what content to generate each day.

Queries upstream services to find noteworthy data points:
- Areas with biggest price movements
- High-volume areas
- Top-scoring news headlines
- Market-wide trends

Returns a list of GenerateRequest objects ready for the generate endpoint.
"""

import logging

from app.models.schemas import GenerateRequest
from app.services import data_client, news_client

logger = logging.getLogger(__name__)


async def plan_daily_content(
    max_items: int = 5,
    template: str = "story/dark-01",
) -> list[GenerateRequest]:
    """Generate a plan of content pieces for today.

    Strategy:
    1. Get top-performing areas (biggest price movers) → market-insight
    2. Get highest-volume areas → data-highlight
    3. Get top news headlines → news-commentary
    4. Market-wide trend → market-update

    Returns list of GenerateRequest objects.
    """
    items: list[GenerateRequest] = []

    # 1. Market-wide trend (always include one)
    items.append(
        GenerateRequest(
            category="market-update",
            entity_type="market",
            entity_slug="dubai",
            template=template,
            metric="price",
            chart_intent="trend",
        )
    )

    # 2. Top movers by price growth
    try:
        perf_data = await data_client.get_area_performance_bulk(
            sort_by="price_change", limit=3
        )
        areas = perf_data.get("data", [])
        for area in areas[:2]:
            slug = area.get("slug") or area.get("area_slug")
            if slug:
                items.append(
                    GenerateRequest(
                        category="market-insight",
                        entity_type="area",
                        entity_slug=slug,
                        template=template,
                        metric="price",
                        chart_intent="trend",
                    )
                )
    except Exception as e:
        logger.warning("Failed to fetch top movers: %s", e)

    # 3. News-driven content
    try:
        headlines = news_client.get_top_headlines(limit=3, min_relevance=0.8)
        for headline in headlines[:1]:
            # Use the first area mentioned in the headline, or fall back to market
            areas = headline.get("areas", [])
            if areas:
                slug = areas[0].lower().replace(" ", "-")
                entity_type = "area"
            else:
                slug = "dubai"
                entity_type = "market"

            items.append(
                GenerateRequest(
                    category="news-commentary",
                    entity_type=entity_type,
                    entity_slug=slug,
                    template=template,
                    metric="price",
                    chart_intent="trend",
                )
            )
    except Exception as e:
        logger.warning("Failed to fetch news for planning: %s", e)

    # 4. High-volume area
    try:
        vol_data = await data_client.get_area_performance_bulk(
            sort_by="transaction_count", limit=1
        )
        areas = vol_data.get("data", [])
        for area in areas[:1]:
            slug = area.get("slug") or area.get("area_slug")
            if slug:
                items.append(
                    GenerateRequest(
                        category="data-highlight",
                        entity_type="area",
                        entity_slug=slug,
                        template=template,
                        metric="volume",
                        chart_intent="hbar",
                    )
                )
    except Exception as e:
        logger.warning("Failed to fetch volume leaders: %s", e)

    return items[:max_items]
