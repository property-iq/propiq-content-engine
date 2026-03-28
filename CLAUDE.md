# CLAUDE.md — propiq-content-engine

## Purpose

Top-level content generation service for PropertyIQ. Consumes from all lower-level services (data-api, charts-api, charts-img, scout-news) and produces branded social media content packages ready for manual review and posting.

**Supersedes**: `propiq-reports-publisher` (removed)

## How It Works

```
propiq-data-api (metrics) ──────┐
propiq-charts-api (configs) ────┤
propiq-charts-img (chart PNGs) ─┤──▶ Content Engine ──▶ Content Packages ──▶ Manual review & post
propiq-scout-news (headlines) ──┘         │
                                    LLM generates text (Claude API)
                                    SVG templates produce images (Playwright)
```

### Generation Flow

1. Fetch area/building performance data from **data-api**
2. Request chart PNG from **charts-img** (via charts-api)
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
# POST /generate        - Generate a content package
# GET  /docs            - Swagger UI
```

## Environment Variables

See `.env.example`. Key variables:
- `DATA_API_BASE` — propiq-data-api URL
- `CHARTS_API_BASE` — propiq-charts-api URL
- `CHARTS_IMG_BASE` — propiq-charts-img URL
- `ANTHROPIC_MODEL` — Claude model (default: `claude-sonnet-4-6`)
- `VERTEX_PROJECT` — GCP project for Vertex AI (default: `crowdproperty-440707`)
- `VERTEX_REGION` — Vertex AI region (default: `us-east5`)
- `ANTHROPIC_API_KEY` — Direct API fallback key (optional, mounted from Secret Manager on Cloud Run)
- `OUTPUT_DIR` — Where content packages are written (default: `./output`)

### LLM Strategy
- **Primary**: Vertex AI via GCP ADC (no key needed, consolidated billing)
- **Fallback**: Direct Anthropic API on rate limit (429) or not found (404)
- **Secret**: `anthropic-api-key` in GCP Secret Manager, mounted via `--set-secrets` in Cloud Run
- Pattern matches `propiq-reports-api/app/clients/anthropic_client.py`

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
| propiq-charts-img | Static chart PNG images | REST (HTTP, binary) |
| BigQuery `scout_news.items` | News headlines, summaries, relevance scores | BigQuery client |
