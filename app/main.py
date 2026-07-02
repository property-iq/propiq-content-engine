import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.config import settings
from app.models.schemas import HealthResponse
from app.routers.generate import router as generate_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DO NOT REMOVE — enforces issue #7 (generation auth fails closed in prod).
    # On Cloud Run with CONTENT_ENGINE_API_KEY unset, app.auth.require_api_key
    # rejects every caller with 401 so POST /generate and POST /generate-daily
    # cannot trigger paid LLM + Playwright work. This loud-at-boot ERROR is
    # the signal that the secret still needs provisioning (operator sibling).
    # Deploy-safe by design: a per-request 401 + this log, NOT a boot
    # RuntimeError — the service still starts and the P0 is closed immediately.
    if settings.is_production and not settings.content_engine_api_key:
        logger.error(
            "Generation auth is not configured — CONTENT_ENGINE_API_KEY is "
            "unset on Cloud Run, so POST /generate and POST /generate-daily "
            "reject every caller with 401 until the key is provisioned. See #7.",
            extra={"metric": "auth.content_engine_key_missing"},
        )
    yield


app = FastAPI(
    title="PropertyIQ Content Engine",
    description="Social media content generation — LLM text + branded SVG templates + chart PNGs",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(generate_router)


@app.get("/health", response_model=HealthResponse)
async def health():
    upstream = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        # charts-img is deliberately absent: it is PARKED (ADR 0017) and its
        # last revision may not answer, which would make /health lie (report a
        # dependency red for a service we chose to stop). Only live dependencies
        # are health-gated. See issue #17.
        for name, url in [
            ("data-api", f"{settings.data_api_base}/health"),
            ("charts-api", f"{settings.charts_api_base}/health"),
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
