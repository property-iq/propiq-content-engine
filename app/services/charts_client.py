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

    charts-img is PARKED (ADR 0017 — static PNG rendering moved to the
    consumer/NAR side), so ``charts_img_base`` defaults to empty. When it is
    empty we refuse loudly at call time rather than fire a silent HTTP request
    at a dead host. Set ``CHARTS_IMG_BASE`` explicitly to re-enable — the park
    is config-reversible. See issue #17.
    """
    if not settings.charts_img_base:
        raise RuntimeError(
            "charts-img is parked (ADR 0017): CHARTS_IMG_BASE is unset, so "
            "chart PNG rendering is disabled. Set CHARTS_IMG_BASE explicitly "
            "to re-enable. See issue #17."
        )

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
