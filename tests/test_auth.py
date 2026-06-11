"""Coverage for app/auth.py — the X-API-Key gate on /generate + /generate-daily.

Acceptance criteria mapping (issue #7):
  - AC1: prod (K_SERVICE set) + key unset → POST /generate is 401, handler never runs.
  - AC2: same → POST /generate-daily is 401.
  - AC3: prod + key="s3cret" → wrong/missing 401; correct key passes.
  - AC4: dev (K_SERVICE unset) + key unset → require_api_key is open.
  - AC5: prod + key unset → startup ERROR with metric=auth.content_engine_key_missing.
  - AC6: app/auth.py uses ``secrets.compare_digest`` (no ``==`` on the secret).
  - AC7: prod + key unset → GET /health is NOT 401 (probes must not require auth).
"""

import asyncio
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import auth
from app.config import settings


# ---------- helpers ----------


def _build_request_body() -> dict:
    """A minimally-valid GenerateRequest body. The auth dep should reject
    before the body is even parsed against business logic, but FastAPI parses
    the model before running endpoint deps — keep this valid so a 401 isn't
    masked by a 422."""
    return {
        "category": "market-insight",
        "entity_type": "area",
        "entity_slug": "dubai-marina",
    }


@pytest.fixture
def prod_no_key(monkeypatch):
    """Cloud Run environment with the secret not yet provisioned."""
    monkeypatch.setenv("K_SERVICE", "propiq-content-engine")
    monkeypatch.setattr(settings, "content_engine_api_key", "")
    yield


@pytest.fixture
def prod_with_key(monkeypatch):
    """Cloud Run environment with the key configured."""
    monkeypatch.setenv("K_SERVICE", "propiq-content-engine")
    monkeypatch.setattr(settings, "content_engine_api_key", "s3cret")
    yield


@pytest.fixture
def dev_no_key(monkeypatch):
    """Local dev — no K_SERVICE, no key."""
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setattr(settings, "content_engine_api_key", "")
    yield


# ---------- AC1: /generate is 401 in prod when key unset, body never runs ----------


def test_ac1_generate_401_in_prod_when_key_unset_and_body_never_runs(prod_no_key):
    # Patch every paid upstream + side-effecting service. If the auth dep
    # short-circuits correctly, none of these are called.
    with (
        patch("app.routers.generate.data_client") as mock_data,
        patch("app.routers.generate.charts_client") as mock_charts,
        patch("app.routers.generate.llm") as mock_llm,
        patch("app.routers.generate.render_svg_to_png") as mock_render,
        patch("app.routers.generate.news_client") as mock_news,
    ):
        from app.main import app

        with TestClient(app) as client:
            resp = client.post("/generate", json=_build_request_body())

    assert resp.status_code == 401
    mock_data.get_area_performance.assert_not_called()
    mock_data.get_building_performance.assert_not_called()
    mock_data.get_market_summary.assert_not_called()
    mock_charts.get_chart_png.assert_not_called()
    mock_llm.generate_copy.assert_not_called()
    mock_render.assert_not_called()
    mock_news.get_headlines_for_area.assert_not_called()
    mock_news.get_top_headlines.assert_not_called()


# ---------- AC2: /generate-daily is also 401 in prod when key unset ----------


def test_ac2_generate_daily_401_in_prod_when_key_unset(prod_no_key):
    with (
        patch("app.routers.generate.plan_daily_content") as mock_plan,
    ):
        from app.main import app

        with TestClient(app) as client:
            resp = client.post("/generate-daily")

    assert resp.status_code == 401
    mock_plan.assert_not_called()


# ---------- AC3: correct key passes, wrong/missing rejected ----------


def test_ac3_correct_key_passes(prod_with_key):
    asyncio.run(auth.require_api_key(x_api_key="s3cret"))  # no raise


def test_ac3_wrong_key_rejected(prod_with_key):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth.require_api_key(x_api_key="wrong"))
    assert exc.value.status_code == 401


def test_ac3_missing_key_rejected(prod_with_key):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth.require_api_key(x_api_key=None))
    assert exc.value.status_code == 401


# ---------- AC4: dev convenience preserved (open locally) ----------


def test_ac4_dev_open_when_no_k_service_and_no_key(dev_no_key):
    asyncio.run(auth.require_api_key(x_api_key=None))  # no raise — dev stays open


# ---------- AC5: loud, deploy-safe operator signal at startup ----------


def test_ac5_startup_error_when_prod_and_key_unset(prod_no_key, caplog):
    caplog.set_level(logging.ERROR, logger="app.main")
    from app.main import app

    with TestClient(app):  # triggers the lifespan startup
        pass

    matches = [
        r
        for r in caplog.records
        if getattr(r, "metric", None) == "auth.content_engine_key_missing"
    ]
    assert matches, "expected an ERROR with metric=auth.content_engine_key_missing"
    assert matches[0].levelno == logging.ERROR


# ---------- AC6: constant-time comparison ----------


def test_ac6_auth_uses_compare_digest():
    """A literal-source check protects against a future regression to ``==``."""
    src = Path(auth.__file__).read_text()
    assert "compare_digest" in src, "app/auth.py must use secrets.compare_digest"


# ---------- AC7: /health stays open ----------


def test_ac7_health_not_401_in_prod_when_key_unset(prod_no_key):
    """Probes (Cloud Run health checks, k8s liveness) must not require auth."""
    with (
        # Avoid making real upstream calls — patch httpx and let the handler
        # complete normally; we only care that auth didn't reject it.
        patch("app.main.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_ctx = mock_client_cls.return_value
        mock_ctx.__aenter__.return_value.get.side_effect = Exception("upstream skipped")
        mock_ctx.__aexit__.return_value = None

        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/health")

    assert resp.status_code != 401, "auth must not gate /health"
