import httpx

from app.config import settings


async def get_chart_png(
    intent: str,
    metric: str,
    entity_type: str,
    entity_slug: str,
    property_type: str = "ALL",
    period_type: str = "monthly",
) -> bytes:
    """Fetch a rendered chart PNG from charts-img.

    Charts-img accepts the same request format as charts-api and returns
    a PNG directly (it calls charts-api internally).
    """
    chart_request = {
        "intent": intent,
        "metric": metric,
        "entities": [{"type": entity_type, "identifier": entity_slug}],
        "time_filter": {"period_type": period_type},
        "property_filter": {"property_type": property_type},
        "mode": "static",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.charts_img_base}/render",
            json=chart_request,
        )
        resp.raise_for_status()
        return resp.content
