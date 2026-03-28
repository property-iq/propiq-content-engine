import httpx

from app.config import settings


async def get_area_performance(slug: str, period: str = "T12M", property_type: str = "ALL") -> dict:
    """Fetch current performance metrics for an area."""
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.get(
            f"{settings.data_api_base}/api/areas/{slug}/performance",
            params={"period": period, "property_type": property_type},
        )
        resp.raise_for_status()
        return resp.json()


async def get_area_history(slug: str, period_type: str = "monthly", property_type: str = "ALL") -> dict:
    """Fetch historical time series for an area."""
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.get(
            f"{settings.data_api_base}/api/areas/{slug}/history",
            params={"period_type": period_type, "property_type": property_type},
        )
        resp.raise_for_status()
        return resp.json()


async def get_building_performance(building_id: str, period: str = "T12M") -> dict:
    """Fetch current performance metrics for a building."""
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.get(
            f"{settings.data_api_base}/api/buildings/{building_id}/performance",
            params={"period": period},
        )
        resp.raise_for_status()
        return resp.json()


async def get_area_performance_bulk(
    sort_by: str = "transaction_count",
    limit: int = 5,
    period: str = "T12M",
    property_type: str = "ALL",
) -> dict:
    """Fetch bulk area performance, sorted by a metric."""
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.get(
            f"{settings.data_api_base}/api/areas/performance/all",
            params={
                "period": period,
                "property_type": property_type,
                "sort_by": sort_by,
                "limit": limit,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_market_summary(period: str = "T12M", property_type: str = "ALL") -> dict:
    """Fetch market-wide summary."""
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.get(
            f"{settings.data_api_base}/api/market",
            params={"period": period, "property_type": property_type},
        )
        resp.raise_for_status()
        return resp.json()
