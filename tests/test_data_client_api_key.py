"""#25: content-engine's data_client attaches X-API-Key for data-api's REST
auth (infra#22). No-op when DATA_API_KEY is unset. Third internal client for
the flip sequence (reports-api#284 + charts-api#508 are the other two)."""

import asyncio

import httpx

from app.config import settings
from app.services import data_client

# Real class captured before any monkeypatch, so the recorder factory below
# doesn't recurse into the patched httpx.AsyncClient.
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def test_headers_present_when_key_set(monkeypatch):
    monkeypatch.setattr(settings, "data_api_key", "test-key-123")
    assert data_client._headers()["X-API-Key"] == "test-key-123"


def test_headers_empty_when_key_unset(monkeypatch):
    monkeypatch.setattr(settings, "data_api_key", "")
    assert "X-API-Key" not in data_client._headers()


class _Recorder:
    def __init__(self):
        self.requests: list[httpx.Request] = []

    def _handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"ok": True})

    def client(self, **_kwargs):
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(self._handler))


def test_request_carries_key_when_set(monkeypatch):
    monkeypatch.setattr(settings, "data_api_key", "test-key-123")
    rec = _Recorder()
    monkeypatch.setattr(data_client.httpx, "AsyncClient", rec.client)

    asyncio.run(data_client.get_area_performance("dubai-marina"))
    asyncio.run(data_client.get_market_summary())

    assert len(rec.requests) == 2
    for req in rec.requests:
        assert req.headers["X-API-Key"] == "test-key-123"


def test_no_key_header_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "data_api_key", "")
    rec = _Recorder()
    monkeypatch.setattr(data_client.httpx, "AsyncClient", rec.client)

    asyncio.run(data_client.get_building_performance("dubai-marina--marina-gate-1"))

    assert "X-API-Key" not in rec.requests[0].headers
