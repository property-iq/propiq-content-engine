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
    """Fetch a rendered chart PNG from charts-img via charts-api.

    The charts-img service renders Chart.js configs from charts-api into
    Economist-style PNG images with the PropertyIQ brand bar.
    """
    # Build the charts-api render request
    chart_request = {
        "intent": intent,
        "metric": metric,
        "entity_type": entity_type,
        "entities": [entity_slug],
        "filters": {"property_type": property_type, "period_type": period_type},
        "mode": "static",
    }

    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        # Get chart config from charts-api
        config_resp = await client.post(
            f"{settings.charts_api_base}/charts/render",
            json=chart_request,
        )
        config_resp.raise_for_status()
        chart_data = config_resp.json()

        # Get the chart slug for charts-img
        slug = chart_data.get("meta", {}).get("slug")
        if not slug:
            raise ValueError("Charts API did not return a slug for PNG rendering")

        # Render PNG via charts-img
        img_resp = await client.get(
            f"{settings.charts_img_base}/render/{slug}",
            params={"preset": "whatsapp"},
        )
        img_resp.raise_for_status()
        return img_resp.content
