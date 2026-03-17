# propiq-content-engine

Daily social media content generation for PropertyIQ. LLM generates text; branded SVG templates produce image creatives.

## How It Works

```
scout-news (headlines) ──┐
charts-img (PNG charts) ──┤──▶ Content Engine ──▶ Content Packages ──▶ Martin reviews & posts
data-api (metrics) ───────┘         │
                              LLM generates text
                              Templates produce images
```

## Template System

Templates are SVG files exported from Adobe Illustrator. The engine injects dynamic content (text, charts, overlays) into defined slot positions, then renders to PNG via Puppeteer.

### Directory Structure

```
templates/
├── formats/                    # Base templates (SVG backgrounds)
│   ├── story/                  # 1080×1920 (9:16) — IG Stories, Reels
│   │   ├── dark-01.svg
│   │   └── dark-02.svg
│   ├── post/                   # 1080×1080 (1:1) — IG Posts, FB
│   │   └── dark-01.svg
│   └── banner/                 # 1200×675 (16:9) — X/Twitter
│       └── dark-01.svg
├── overlays/                   # Reusable design elements (PNG/SVG)
│   ├── chart-highlight-gold.png
│   └── ...
├── references/                 # Filled examples (visual reference only, not used by system)
│   └── story-dark-01-filled.svg
└── slots.yaml                  # Slot definitions per template
```

### Naming Convention

| Component | Pattern | Example |
|-----------|---------|---------|
| Format dirs | `{shape}` | `story`, `post`, `banner` |
| Templates | `{theme}-{nn}.svg` | `dark-01.svg`, `light-02.svg` |
| Overlays | `{function}-{color}.{ext}` | `chart-highlight-gold.png` |
| References | `{format}-{template}-filled.svg` | `story-dark-01-filled.svg` |

### Formats

| Format | Dimensions | Aspect | Platforms |
|--------|-----------|--------|-----------|
| `story` | 1080×1920 | 9:16 | IG Stories, Reels, TikTok, WhatsApp Status |
| `post` | 1080×1080 | 1:1 | IG Posts, FB Posts, Telegram |
| `banner` | 1200×675 | 16:9 | X/Twitter, LinkedIn, Telegram |

### Slot System

Each template has named slots defined in `slots.yaml`:

- **text** — title, body, source attribution, branding
- **image** — chart PNG from charts-img
- **overlay** — design elements (highlights, dividers) positioned relative to other slots

### Adding a New Template

1. Design in Illustrator (use one artboard per template variant)
2. Export as SVG — background/static elements only, no text content
3. Place SVG in `templates/formats/{format}/{theme}-{nn}.svg`
4. Save a filled reference in `templates/references/`
5. Define slot positions in `templates/slots.yaml`

## Content Categories

| Category | Sources | Output |
|----------|---------|--------|
| Market Insight | chart + data-api metrics | Chart creative + insight text |
| News Commentary | scout-news headline | News creative + analysis text |
| Data Highlight | data-api surprising stat | Stat creative + context text |
| Market Update | multiple charts + metrics | Summary creative + overview text |
| Educational | curated content | Infographic + explainer text |

## Output

Each generation produces a content package:
```
output/2026-03-18/
├── market-insight-01/
│   ├── story.png           # 1080×1920
│   ├── post.png            # 1080×1080
│   ├── banner.png          # 1200×675
│   ├── caption-ig.md       # Instagram caption
│   ├── caption-x.md        # X/Twitter text
│   ├── caption-telegram.md # Telegram text
│   └── metadata.json       # Source refs, generation params
```

## Tech Stack

- **Python / FastAPI** — content generation logic
- **Puppeteer** — SVG → PNG rendering
- **Gemini Flash** — LLM text generation
- **GCS** — generated content storage
