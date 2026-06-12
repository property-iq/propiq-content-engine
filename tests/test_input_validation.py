"""Coverage for input validation on /generate and /generate-daily (issue #8).

The auth gate from #7 is open in dev (K_SERVICE unset, key unset), so these
tests run with no auth in front of the request — they exercise the request
boundary itself: malformed input returns 422 before any path is built, any
upstream is called, or any LLM/Playwright work runs.

Acceptance criteria mapping:
  - AC1: template traversal blocked (../../../etc/passwd → 422, no work runs).
  - AC2: template shape — story/dark-01 ok; "story" or "a/b/c" → 422.
  - AC3: category constrained (../evil → 422; market-insight → ok).
  - AC4: entity_slug constrained; the documented building-id form
         (dubai-marina--marina-pinnacle) passes — double-hyphen is just two
         consecutive hyphens in [a-z0-9-]+. "../../tmp/x" and "a/b" → 422.
  - AC5: length bounded — 500-char entity_slug → 422.
  - AC6: max_items clamped — 1000 → 422, 0 → 422, 5 → not 422.
  - AC7: constraints live in the model (pattern= + max_length= in schemas.py).
  - AC8: planner output validates — every GenerateRequest the planner emits
         constructs without ValidationError.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import models
from app.config import settings
from app.models.schemas import GenerateRequest


# ---------- helpers ----------


def _valid_body(**overrides) -> dict:
    """A minimally-valid /generate body — override any field per test."""
    body = {
        "category": "market-insight",
        "entity_type": "area",
        "entity_slug": "dubai-marina",
        "template": "story/dark-01",
    }
    body.update(overrides)
    return body


@pytest.fixture
def dev_open(monkeypatch):
    """Local-dev environment: K_SERVICE unset + key unset → auth is open,
    so a 422 cannot be masked by a 401. This is exactly the state issue #8's
    acceptance criteria specify."""
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setattr(settings, "content_engine_api_key", "")
    yield


@pytest.fixture
def patched_upstreams():
    """Patch every paid/side-effecting upstream so a passing validation does not
    actually call the network. Tests that expect 422 also use this to assert
    that the handler body never runs."""
    with (
        patch("app.routers.generate.data_client") as mock_data,
        patch("app.routers.generate.charts_client") as mock_charts,
        patch("app.routers.generate.llm") as mock_llm,
        patch("app.routers.generate.render_svg_to_png") as mock_render,
        patch("app.routers.generate.news_client") as mock_news,
        patch("app.routers.generate.plan_daily_content") as mock_plan,
    ):
        yield {
            "data": mock_data,
            "charts": mock_charts,
            "llm": mock_llm,
            "render": mock_render,
            "news": mock_news,
            "plan": mock_plan,
        }


def _assert_no_work_ran(mocks):
    mocks["data"].get_area_performance.assert_not_called()
    mocks["data"].get_building_performance.assert_not_called()
    mocks["data"].get_market_summary.assert_not_called()
    mocks["charts"].get_chart_png.assert_not_called()
    mocks["llm"].generate_copy.assert_not_called()
    mocks["render"].assert_not_called()
    mocks["news"].get_headlines_for_area.assert_not_called()
    mocks["news"].get_top_headlines.assert_not_called()
    mocks["plan"].assert_not_called()


# ---------- AC1: template traversal blocked ----------


def test_ac1_template_traversal_blocked(dev_open, patched_upstreams):
    from app.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/generate", json=_valid_body(template="../../../etc/passwd")
        )

    assert resp.status_code == 422
    _assert_no_work_ran(patched_upstreams)


def test_ac1_template_backslash_traversal_blocked(dev_open, patched_upstreams):
    from app.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/generate", json=_valid_body(template="story\\..\\..\\etc\\passwd")
        )

    assert resp.status_code == 422
    _assert_no_work_ran(patched_upstreams)


def test_ac1_template_null_byte_blocked(dev_open, patched_upstreams):
    from app.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/generate", json=_valid_body(template="story/dark-01\x00.png")
        )

    assert resp.status_code == 422
    _assert_no_work_ran(patched_upstreams)


# ---------- AC2: template shape ----------


def test_ac2_template_canonical_shape_accepted(dev_open, patched_upstreams):
    """story/dark-01 — the real template — must pass the pattern."""
    # No HTTP round-trip needed: assert the model accepts the value.
    req = GenerateRequest(**_valid_body(template="story/dark-01"))
    assert req.template == "story/dark-01"


def test_ac2_template_no_separator_rejected():
    """A bare format with no theme is invalid (would resolve to a format dir)."""
    with pytest.raises(ValidationError):
        GenerateRequest(**_valid_body(template="story"))


def test_ac2_template_too_deep_rejected():
    """More than one separator escapes the templates/{format}/{theme}/ layout."""
    with pytest.raises(ValidationError):
        GenerateRequest(**_valid_body(template="a/b/c"))


def test_ac2_template_leading_slash_rejected():
    """A leading slash would make the join absolute (templates_dir / req.template
    resolves to /...). The pattern forbids it."""
    with pytest.raises(ValidationError):
        GenerateRequest(**_valid_body(template="/etc/passwd"))


# ---------- AC3: category constrained ----------


def test_ac3_category_traversal_rejected():
    with pytest.raises(ValidationError):
        GenerateRequest(**_valid_body(category="../evil"))


def test_ac3_category_canonical_accepted():
    GenerateRequest(**_valid_body(category="market-insight"))
    GenerateRequest(**_valid_body(category="news-commentary"))
    GenerateRequest(**_valid_body(category="data-highlight"))
    GenerateRequest(**_valid_body(category="market-update"))


def test_ac3_category_uppercase_rejected():
    """The slug pattern is lowercase-only — protects against case-only
    differences sneaking into directory names on case-insensitive filesystems."""
    with pytest.raises(ValidationError):
        GenerateRequest(**_valid_body(category="Market-Insight"))


# ---------- AC4: entity_slug constrained ----------


def test_ac4_entity_slug_traversal_rejected():
    with pytest.raises(ValidationError):
        GenerateRequest(**_valid_body(entity_slug="../../tmp/x"))


def test_ac4_entity_slug_path_separator_rejected():
    with pytest.raises(ValidationError):
        GenerateRequest(**_valid_body(entity_slug="a/b"))


def test_ac4_entity_slug_area_form_accepted():
    GenerateRequest(**_valid_body(entity_slug="dubai-marina"))
    GenerateRequest(**_valid_body(entity_slug="jumeirah-village-circle"))


def test_ac4_entity_slug_building_id_form_accepted():
    """The documented building-id convention is {area-slug}--{building-slug}.
    Double-hyphen is two consecutive hyphens in [a-z0-9-]+; the pattern passes
    it. CLAUDE.md (propiq-data-api): 'Composite identifier: {area-slug}--{building-slug}'."""
    GenerateRequest(**_valid_body(entity_slug="dubai-marina--marina-pinnacle"))
    GenerateRequest(**_valid_body(entity_slug="dubai-marina--marina-gate-1"))


# ---------- AC5: length bounded ----------


def test_ac5_entity_slug_overlong_rejected():
    with pytest.raises(ValidationError):
        GenerateRequest(**_valid_body(entity_slug="a" * 500))


def test_ac5_category_overlong_rejected():
    with pytest.raises(ValidationError):
        GenerateRequest(**_valid_body(category="a" * 500))


def test_ac5_template_overlong_rejected():
    # Within the `^[a-z0-9]+/[a-z0-9-]+$` shape but past max_length.
    with pytest.raises(ValidationError):
        GenerateRequest(**_valid_body(template="story/" + "a" * 500))


# ---------- AC6: max_items clamped (folded from #9) ----------


def test_ac6_max_items_overlimit_rejected(dev_open, patched_upstreams):
    from app.main import app

    with TestClient(app) as client:
        resp = client.post("/generate-daily?max_items=1000")

    assert resp.status_code == 422
    _assert_no_work_ran(patched_upstreams)


def test_ac6_max_items_zero_rejected(dev_open, patched_upstreams):
    from app.main import app

    with TestClient(app) as client:
        resp = client.post("/generate-daily?max_items=0")

    assert resp.status_code == 422
    _assert_no_work_ran(patched_upstreams)


def test_ac6_max_items_negative_rejected(dev_open, patched_upstreams):
    from app.main import app

    with TestClient(app) as client:
        resp = client.post("/generate-daily?max_items=-5")

    assert resp.status_code == 422
    _assert_no_work_ran(patched_upstreams)


def test_ac6_max_items_default_accepted(dev_open, patched_upstreams):
    """Default value of 5 must not be 422'd — the planner is mocked so no
    actual generation runs. The only thing under test is that validation
    accepts the request shape and the handler proceeds past it."""
    patched_upstreams["plan"].return_value = []  # AsyncMock-compatible

    # plan_daily_content is an async function; AsyncMock handles awaitability
    # when set via patch(), but be explicit to avoid relying on autospec.
    async def _empty_plan(*args, **kwargs):
        return []

    patched_upstreams["plan"].side_effect = _empty_plan

    from app.main import app

    with TestClient(app) as client:
        resp = client.post("/generate-daily?max_items=5")

    assert resp.status_code != 422


def test_ac6_max_items_upper_bound_accepted(dev_open, patched_upstreams):
    async def _empty_plan(*args, **kwargs):
        return []

    patched_upstreams["plan"].side_effect = _empty_plan

    from app.main import app

    with TestClient(app) as client:
        resp = client.post("/generate-daily?max_items=20")

    assert resp.status_code != 422


# ---------- AC7: constraints live in the model ----------


def test_ac7_pattern_and_max_length_present_in_schemas():
    """A literal-source check protects against a future regression where
    constraints drift to ad-hoc handler checks (cf. constitution: 'Typed
    Pydantic models are the authoritative schema source.')."""
    src = Path(models.schemas.__file__).read_text()
    assert "pattern=" in src, "schemas.py must declare pattern= constraints"
    assert "max_length=" in src, "schemas.py must declare max_length= constraints"


# ---------- AC8: planner output still validates ----------


@pytest.mark.parametrize(
    "category,entity_type,entity_slug,metric,chart_intent",
    [
        # Mirrors app/engine/planner.py:36-46 (market-wide trend)
        ("market-update", "market", "dubai", "price", "trend"),
        # Mirrors planner.py:54-66 (top movers by price growth — area slugs)
        ("market-insight", "area", "dubai-marina", "price", "trend"),
        ("market-insight", "area", "business-bay", "price", "trend"),
        # Mirrors planner.py:71-92 (news-driven, area or market)
        ("news-commentary", "area", "dubai-marina", "price", "trend"),
        ("news-commentary", "market", "dubai", "price", "trend"),
        # Mirrors planner.py:96-114 (high-volume area)
        ("data-highlight", "area", "dubai-marina", "volume", "hbar"),
    ],
)
def test_ac8_planner_emitted_requests_validate(
    category, entity_type, entity_slug, metric, chart_intent
):
    """Every shape the planner is wired to emit must round-trip through
    validation. If this fails, the planner is generating values the request
    boundary refuses — file a separate planner defect rather than weakening
    the pattern (see Notes in issue #8)."""
    GenerateRequest(
        category=category,
        entity_type=entity_type,
        entity_slug=entity_slug,
        template="story/dark-01",
        metric=metric,
        chart_intent=chart_intent,
    )
