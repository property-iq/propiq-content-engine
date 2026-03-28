# propiq-content-engine

Social media content generation for PropertyIQ. Consumes from all lower-level services (data-api, charts-api, charts-img, scout-news), generates branded visual content packages ready for manual review and posting.

Supersedes `propiq-reports-publisher`.

## How It Works

```
propiq-data-api (metrics) ──────┐
propiq-charts-api (configs) ────┤
propiq-charts-img (chart PNGs) ─┤──▶ Content Engine ──▶ Content Packages ──▶ Martin reviews & posts
propiq-scout-news (headlines) ──┘         │
                                    LLM generates text (Claude API)
                                    SVG templates produce images (Playwright)
```

## Quick Start

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
uvicorn app.main:app --reload --port 8000

# Check health
curl http://localhost:8000/health

# Generate content
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "category": "market-insight",
    "entity_type": "area",
    "entity_slug": "dubai-marina",
    "template": "story/dark-01",
    "metric": "price",
    "chart_intent": "trend"
  }'
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health + upstream connectivity |
| `/generate` | POST | Generate a content package |
| `/docs` | GET | Swagger UI |

### POST /generate

**Request:**
```json
{
  "category": "market-insight",
  "entity_type": "area",
  "entity_slug": "dubai-marina",
  "template": "story/dark-01",
  "metric": "price",
  "chart_intent": "trend",
  "period": "T12M",
  "property_type": "ALL"
}
```

**Categories:** `market-insight`, `news-commentary`, `data-highlight`, `market-update`, `educational`

**Response:** Content package with PNG path, captions, and metadata.

## Template System

Each template is a self-contained directory with three files:

```
templates/{format}/{theme}-{nn}/
├── base.svg          # Background template (static layers from Illustrator)
├── config.yaml       # Slot positions + LLM prompt + metadata
└── reference.svg     # Filled example (visual reference, not used by system)
```

### Formats

| Format | Dimensions | Aspect | Platforms |
|--------|-----------|--------|-----------|
| `story` | 1080x1920 | 9:16 | IG Stories, Reels, WhatsApp Status |
| `post` | 1080x1080 | 1:1 | IG Posts, FB, Telegram |
| `banner` | 1200x675 | 16:9 | X/Twitter, LinkedIn |

### Adding a New Template

1. Design in Illustrator
2. Export background as SVG -> `base.svg`
3. Export filled example -> `reference.svg`
4. Define slots, prompt, and metadata -> `config.yaml`
5. Place in `templates/{format}/{theme}-{nn}/`

## Output

```
output/2026-03-28/
├── market-insight-dubai-marina/
│   ├── story.png
│   ├── caption-ig.md
│   ├── caption-x.md
│   └── metadata.json
```

## Project Structure

```
propiq-content-engine/
├── app/
│   ├── main.py                  # FastAPI app + /health
│   ���── config.py                # Settings (pydantic-settings)
│   ├── routers/
│   │   └── generate.py          # POST /generate endpoint
│   ├── services/
│   │   ├── data_client.py       # propiq-data-api client
│   │   ├── charts_client.py     # propiq-charts-api + charts-img client
│   │   ├── news_client.py       # BigQuery scout_news client
│   │   └── llm.py               # Claude API for text generation
│   ├── engine/
│   │   ├── composer.py          # SVG template + slot injection
│   │   └── renderer.py          # Playwright SVG -> PNG
│   └── models/
│       └── schemas.py           # Pydantic request/response models
├── templates/                   # SVG templates + configs
├── output/                      # Generated content (git-ignored)
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Content Categories

| Category | Sources | Description |
|----------|---------|-------------|
| `market-insight` | chart + data-api | Chart with headline + insight |
| `news-commentary` | scout-news | News headline + analysis |
| `data-highlight` | data-api | Big stat + context |
| `market-update` | charts + metrics | Weekly/monthly summary |
| `educational` | curated | RE concepts explained |
