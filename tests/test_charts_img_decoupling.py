"""Coverage for issue #17 — decouple /health and config from parked charts-img.

Acceptance criteria mapping:
  - AC1: GET /health does NOT probe charts-img (absent from dependency checks).
  - AC2: charts_img_base default is empty; invoking the chart client with it
         unset raises a clear config error naming the park (ADR 0017) and makes
         NO HTTP call.
  - AC3: with charts_img_base explicitly set, the client behaves as before
         (park is config-reversible) — it issues the POST to {base}/render.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services import charts_client


# ---------- AC1: /health never probes charts-img ----------


def test_ac1_health_does_not_probe_charts_img():
    """The set of URLs /health hits must not include a charts-img endpoint."""
    probed_urls = []

    class _FakeResponse:
        status_code = 200

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url):
            probed_urls.append(url)
            return _FakeResponse()

    with patch("app.main.httpx.AsyncClient", return_value=_FakeClient()):
        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert "charts-img" not in body["upstream"], "charts-img must be gone from /health"
    assert set(body["upstream"]) == {"data-api", "charts-api"}
    assert not any("charts-img" in u for u in probed_urls), (
        f"/health must not probe charts-img; probed: {probed_urls}"
    )


# ---------- AC2: empty default → loud config error, no HTTP call ----------


def test_ac2_charts_img_base_default_is_empty():
    """The parked default must be empty so the guard trips by default."""
    assert settings.__class__().charts_img_base == "", (
        "charts_img_base default must be empty (charts-img parked, ADR 0017)"
    )


def test_ac2_empty_base_raises_and_makes_no_http_call(monkeypatch):
    monkeypatch.setattr(settings, "charts_img_base", "")

    with patch("app.services.charts_client.httpx.AsyncClient") as mock_client_cls:
        with pytest.raises(RuntimeError) as exc:
            asyncio.run(
                charts_client.get_chart_png(
                    intent="trend",
                    metric="price",
                    entity_type="area",
                    entity_slug="dubai-marina",
                )
            )

    msg = str(exc.value)
    assert "charts-img" in msg
    assert "ADR 0017" in msg, "config error must name the park (ADR 0017)"
    # No HTTP client may be constructed when the base is empty.
    mock_client_cls.assert_not_called()


# ---------- AC3: explicit base → behaves as before (config-reversible) ----------


def test_ac3_explicit_base_still_posts_to_render(monkeypatch):
    monkeypatch.setattr(settings, "charts_img_base", "https://charts-img.example")

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.content = b"PNGBYTES"

    posted = {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def post(self, url, json):
            posted["url"] = url
            posted["json"] = json
            return mock_resp

    with patch("app.services.charts_client.httpx.AsyncClient", _FakeClient):
        result = asyncio.run(
            charts_client.get_chart_png(
                intent="trend",
                metric="price",
                entity_type="area",
                entity_slug="dubai-marina",
            )
        )

    assert result == b"PNGBYTES"
    assert posted["url"] == "https://charts-img.example/render"
    assert posted["json"]["mode"] == "static"
