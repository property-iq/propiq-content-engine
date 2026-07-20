# CLAUDE.md — propiq-content-engine

## Purpose

Top-level content generation service for PropertyIQ. Consumes from lower-level services (data-api, charts-api, scout-news) and produces branded social media content packages ready for manual review and posting. The charts-img dependency is **PARKED** (ADR 0017 — static PNG rendering moved to the consumer/NAR side); its client is dormant behind a loud config guard (#17).

**Supersedes**: `propiq-reports-publisher` (removed)

## How It Works

```
propiq-data-api (metrics) ──────────────────┐
propiq-charts-api (configs) ────────────────┤──▶ Content Engine ──▶ Content Packages ──▶ Manual review & post
propiq-scout-news (headlines) ──────────────┘         │
propiq-charts-img (chart PNGs) — PARKED,        LLM generates text (Claude API)
  ADR 0017; dormant, see #17                    SVG templates produce images (Playwright)
```

### Generation Flow

1. Fetch area/building performance data from **data-api**
2. Request chart PNG from **charts-img** — **currently PARKED** (ADR 0017): the PNG-fetch client is dormant behind a loud config guard and refuses unless `CHARTS_IMG_BASE` is explicitly set (config-reversible, see #17)
3. Query **BigQuery** `scout_news.items` for relevant headlines
4. Call **Claude API** with template prompt + data context → title + body copy
5. Load SVG template, inject text + chart into slots → composite SVG
6. Render composite SVG to PNG via **Playwright**
7. Write output package: PNG + captions + metadata

## Template System

Each template is a self-contained directory:

```
templates/{format}/{theme}-{nn}/
├── base.svg          # Static SVG background (from Illustrator)
├── config.yaml       # Slot positions + LLM prompt + metadata
└── reference.svg     # Filled visual reference (design review only)
```

### Formats

| Format | Dimensions | Aspect | Platforms |
|--------|-----------|--------|-----------|
| `story` | 1080×1920 | 9:16 | IG Stories, Reels, WhatsApp Status |
| `post` | 1080×1080 | 1:1 | IG Posts, FB, Telegram |
| `banner` | 1200×675 | 16:9 | X/Twitter, LinkedIn |

### config.yaml Slot Types

- `text` — Dynamic text with font, color, position, line wrapping
- `image` — Chart PNG embedding (base64 in SVG)
- `overlay` — Design elements positioned relative to other slots

### Content Categories

| Category | Sources | Description |
|----------|---------|-------------|
| `market-insight` | chart + data-api | Chart with headline + insight |
| `news-commentary` | scout-news | News headline + analysis |
| `data-highlight` | data-api | Big stat + context |
| `market-update` | charts + metrics | Weekly/monthly summary |
| `educational` | curated | RE concepts explained |

## Development

```bash
cd propiq-content-engine

# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Run
uvicorn app.main:app --reload --port 8000

# Endpoints
# GET  /health          - Service health + upstream connectivity
# POST /generate        - Generate a content package (X-API-Key)
# POST /generate-daily  - Generate the daily content plan (X-API-Key)
# GET  /docs            - Swagger UI
```

Both `POST` endpoints are gated by `X-API-Key` (`app/auth.py`, issue #7): key configured →
enforced; key unset on Cloud Run → **fail closed** (401); key unset locally → open for dev.

## Environment Variables

See `.env.example`. Key variables:
- `DATA_API_BASE` — propiq-data-api URL
- `CHARTS_API_BASE` — propiq-charts-api URL
- `CHARTS_IMG_BASE` — **empty by default**: charts-img is PARKED (ADR 0017); the chart client refuses loudly rather than call a dead host. Set a URL only to re-enable (the park is config-reversible — see #17)
- `ANTHROPIC_MODEL` — Claude model (default: `claude-sonnet-4-6`)
- `VERTEX_PROJECT` — GCP project for Vertex AI (default: `crowdproperty-440707`)
- `VERTEX_REGION` — Vertex AI region (default: `us-east5`)
- `ANTHROPIC_API_KEY` — Direct API fallback key (optional, mounted from Secret Manager on Cloud Run)
- `CONTENT_ENGINE_API_KEY` — X-API-Key for `POST /generate` and `POST /generate-daily` (`app/auth.py`, issue #7). Fail-closed on Cloud Run when unset; mounted from Secret Manager
- `OUTPUT_DIR` — Where content packages are written (default: `./output`)

### LLM Strategy
- **Primary**: Vertex AI via GCP ADC (no key needed, consolidated billing)
- **Fallback**: Direct Anthropic API on rate limit (429) or not found (404)
- **Secret**: `anthropic-api-key` in GCP Secret Manager, mounted via `--set-secrets` in Cloud Run
- Pattern originally mirrored `propiq-reports-api/app/clients/anthropic_client.py` — but reports-api has since diverged: it added `PROPIQ_SKIP_VERTEX` and its production runs direct-only. content-engine has no skip flag (tracked in #21)

## Critical Rules

1. **Template structure is sacred** — Each template must have exactly 3 files: `base.svg`, `config.yaml`, `reference.svg`
2. **Slot coordinates use viewBox units** — Not pixel dimensions. The viewBox is defined in config.yaml `meta.viewbox`
3. **LLM prompts live in config.yaml** — Never hardcode prompts in Python. Each template defines its own prompt
4. **Output is always a package** — Never output a bare PNG. Always include caption files and metadata.json
5. **Manual review workflow** — This service generates content; it never posts automatically

## Upstream Dependencies

| Service | What we consume | Protocol |
|---------|----------------|----------|
| propiq-data-api | Area/building performance, market stats | REST (HTTP) |
| propiq-charts-api | Chart.js configurations | REST (HTTP) |
| propiq-charts-img | **PARKED** (ADR 0017) — dormant PNG client, config-reversible via `CHARTS_IMG_BASE` (#17); absent from `/health` checks | REST (HTTP, binary) when re-enabled |
| BigQuery `scout_news.items` | News headlines, summaries, relevance scores | BigQuery client |
