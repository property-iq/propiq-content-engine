import httpx
from fastapi import FastAPI

from app.config import settings
from app.models.schemas import HealthResponse
from app.routers.generate import router as generate_router

app = FastAPI(
    title="PropertyIQ Content Engine",
    description="Social media content generation — LLM text + branded SVG templates + chart PNGs",
    version="0.1.0",
)

app.include_router(generate_router)


@app.get("/health", response_model=HealthResponse)
async def health():
    upstream = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in [
            ("data-api", f"{settings.data_api_base}/health"),
            ("charts-api", f"{settings.charts_api_base}/health"),
            ("charts-img", f"{settings.charts_img_base}/health"),
        ]:
            try:
                resp = await client.get(url)
                upstream[name] = "ok" if resp.status_code == 200 else f"error ({resp.status_code})"
            except Exception as e:
                upstream[name] = f"unreachable ({type(e).__name__})"

    return HealthResponse(
        status="ok" if all(v == "ok" for v in upstream.values()) else "degraded",
        upstream=upstream,
    )
