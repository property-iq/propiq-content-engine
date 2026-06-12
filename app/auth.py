"""X-API-Key gate for paid generation endpoints.

Mirrors the in-house precedent set by ``propiq-reports-api`` (#221 / goal #81)
and ``propiq-charts-img/app/auth.py``: an app-level header check that
fails-closed on Cloud Run when the key secret is not yet provisioned, so
``POST /generate`` and ``POST /generate-daily`` cannot run paid LLM +
Playwright work unauthenticated.

Behavior:
  - Key configured        → enforce ``X-API-Key``; wrong/missing gets 401.
  - Key unset + Cloud Run → fail closed (401). ``K_SERVICE`` is the trigger
    because Cloud Run sets it automatically, so the code deploy alone closes
    the hole — no operator step needed to activate the gate. The operator
    sibling provisions the secret to restore *authenticated* access.
  - Key unset + local dev → open, preserving dev convenience.

See issue #7.
"""

import logging
import secrets

from fastapi import Header, HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


async def require_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> None:
    if settings.content_engine_api_key:
        if x_api_key is None or not secrets.compare_digest(
            x_api_key, settings.content_engine_api_key
        ):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        return
    if settings.is_production:
        raise HTTPException(status_code=401, detail="Generation auth is not configured")
