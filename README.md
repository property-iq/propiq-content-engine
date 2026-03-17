# propiq-content-engine

Daily social media content generation for PropertyIQ. LLM generates text; branded SVG templates produce image creatives. Manual review and posting.

## How It Works

```
scout-news (headlines) ──┐
charts-img (PNG charts) ──┤──▶ Content Engine ──▶ Content Packages ──▶ Martin reviews & posts
data-api (metrics) ───────┘         │
                              LLM generates text
                              Templates produce images
```

## Template System

Each template is a self-contained directory with three files:

```
templates/{format}/{theme}-{nn}/
├── base.svg          # Background template (static layers from Illustrator)
├── config.yaml       # Slot positions + LLM prompt + metadata
└── reference.svg     # Filled example (visual reference, not used by system)
```

### Directory Structure

```
templates/
├── story/                        # 1080×1920 (9:16) — IG Stories, Reels
│   ├── dark-01/
│   │   ├── base.svg
│   │   ├── config.yaml
│   │   └── reference.svg
│   └── dark-02/
│       └── ...
├── post/                         # 1080×1080 (1:1) — IG Posts, FB
│   └── dark-01/
│       └── ...
├── banner/                       # 1200×675 (16:9) — X/Twitter
│   └── dark-01/
│       └── ...
└── overlays/                     # Reusable design elements
    └── chart-highlight-gold.png
```

### Adding a New Template

1. Design in Illustrator
2. Export background as SVG → `base.svg`
3. Export filled example → `reference.svg`
4. Define slots, prompt, and metadata → `config.yaml`
5. Place in `templates/{format}/{theme}-{nn}/`

### config.yaml Structure

```yaml
meta:
  format: story              # story | post | banner
  dimensions: { width: 1080, height: 1920 }
  viewbox: { width: 810, height: 1440 }
  theme: dark
  categories: [market-insight, data-highlight]

prompt: |
  LLM instructions for generating text content...
  Include style guide, examples, constraints.

slots:
  title:
    type: text               # text | image | overlay
    x: 76
    y: 450
    max_width: 660
    font: { family: Inter, weight: 700, size: 44 }
    color: "#FFFFFF"
  chart:
    type: image
    x: 76
    y: 873
    width: 658
    height: 200
  chart_highlight:
    type: overlay
    ref: overlays/chart-highlight-gold.png
    anchor: chart
    offset: { x: -10, y: -10 }
```

## Rendering Pipeline

```
1. Load base.svg (static background)
2. Layer overlays (highlights, decorative elements)
3. Embed chart PNG from charts-img
4. Render text into slots (SVG text elements)
5. Puppeteer renders composite → final PNG
```

## Formats

| Format | Dimensions | Aspect | Platforms |
|--------|-----------|--------|-----------|
| `story` | 1080×1920 | 9:16 | IG Stories, Reels, WhatsApp Status |
| `post` | 1080×1080 | 1:1 | IG Posts, FB, Telegram |
| `banner` | 1200×675 | 16:9 | X/Twitter, LinkedIn |

## Content Categories

| Category | Sources | Description |
|----------|---------|-------------|
| market-insight | chart + data-api | Chart with headline + insight |
| news-commentary | scout-news | News headline + analysis |
| data-highlight | data-api | Big stat + context |
| market-update | charts + metrics | Weekly/monthly summary |
| educational | curated | RE concepts explained |

## Output

```
output/2026-03-18/
├── market-insight-01/
│   ├── story.png
│   ├── post.png
│   ├── banner.png
│   ├── caption-ig.md
│   ├── caption-x.md
│   └── metadata.json
```
