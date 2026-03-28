"""SVG composer — loads a template and injects dynamic content into slots."""

import base64
import textwrap
from pathlib import Path

import yaml
from lxml import etree

from app.config import settings

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
NSMAP = {"svg": SVG_NS, "xlink": XLINK_NS}


def load_template(template_path: str) -> tuple[etree._Element, dict]:
    """Load base.svg and config.yaml from a template directory.

    Returns (svg_root, config_dict).
    """
    tpl_dir = settings.templates_dir / template_path
    svg_path = tpl_dir / "base.svg"
    config_path = tpl_dir / "config.yaml"

    svg_root = etree.parse(str(svg_path)).getroot()
    with open(config_path) as f:
        config = yaml.safe_load(f)

    return svg_root, config


def compose(
    template_path: str,
    content: dict,
    chart_png: bytes | None = None,
) -> str:
    """Compose a complete SVG by injecting content into template slots.

    Args:
        template_path: e.g. "story/dark-01"
        content: {"title": "...", "body": "..."}
        chart_png: Raw PNG bytes for the chart slot

    Returns:
        Complete SVG string ready for rendering.
    """
    svg_root, config = load_template(template_path)
    slots = config.get("slots", {})

    # Collect elements, sorted by z_index (overlays behind by default)
    elements = []

    for slot_name, slot_def in slots.items():
        slot_type = slot_def.get("type")

        if slot_type == "overlay":
            el = _build_overlay(slot_def, slots, template_path)
            if el is not None:
                elements.append((slot_def.get("z_index", 0), el))

        elif slot_type == "image" and chart_png is not None:
            el = _build_image(slot_def, chart_png)
            elements.append((slot_def.get("z_index", 1), el))

        elif slot_type == "text":
            text_value = slot_def.get("static") or content.get(slot_name, "")
            if text_value:
                els = _build_text(slot_def, text_value)
                for el in els:
                    elements.append((slot_def.get("z_index", 2), el))

    # Sort by z_index and append to SVG
    elements.sort(key=lambda x: x[0])
    for _, el in elements:
        svg_root.append(el)

    return etree.tostring(svg_root, pretty_print=True, encoding="unicode")


def _build_text(slot_def: dict, text: str) -> list[etree._Element]:
    """Create SVG text elements for a text slot, with line wrapping."""
    font = slot_def.get("font", {})
    font_family = font.get("family", "Inter")
    font_weight = font.get("weight", 400)
    font_size = font.get("size", 22)
    color = slot_def.get("color", "#FFFFFF")
    line_height = slot_def.get("line_height", 1.4)
    max_width = slot_def.get("max_width", 660)
    max_lines = slot_def.get("max_lines", 10)
    x = slot_def["x"]
    y = slot_def["y"]

    # Estimate chars per line based on font size (rough: ~0.55 * font_size per char width)
    avg_char_width = font_size * 0.55
    chars_per_line = int(max_width / avg_char_width)
    wrapped = textwrap.wrap(text, width=chars_per_line)[:max_lines]

    elements = []
    for i, line in enumerate(wrapped):
        text_el = etree.SubElement(
            etree.Element("dummy"),  # Detached, will be appended later
            f"{{{SVG_NS}}}text",
        )
        # Build as standalone element
        text_el = etree.Element(f"{{{SVG_NS}}}text")
        text_el.text = line
        text_el.set("x", str(x))
        text_el.set("y", str(y + i * font_size * line_height))
        text_el.set("font-family", font_family)
        text_el.set("font-weight", str(font_weight))
        text_el.set("font-size", f"{font_size}px")
        text_el.set("fill", color)
        elements.append(text_el)

    return elements


def _build_image(slot_def: dict, png_bytes: bytes) -> etree._Element:
    """Create an SVG <image> element embedding a PNG as base64."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    img_el = etree.Element(f"{{{SVG_NS}}}image")
    img_el.set("x", str(slot_def["x"]))
    img_el.set("y", str(slot_def["y"]))
    img_el.set("width", str(slot_def["width"]))
    img_el.set("height", str(slot_def["height"]))
    img_el.set(f"{{{XLINK_NS}}}href", f"data:image/png;base64,{b64}")
    return img_el


def _build_overlay(slot_def: dict, all_slots: dict, template_path: str) -> etree._Element | None:
    """Create an SVG <image> element for an overlay, positioned relative to its anchor."""
    ref = slot_def.get("ref")
    if not ref:
        return None

    overlay_path = settings.templates_dir / ref
    if not overlay_path.exists():
        return None

    with open(overlay_path, "rb") as f:
        png_bytes = f.read()

    b64 = base64.b64encode(png_bytes).decode("ascii")

    # Position relative to anchor slot
    anchor_name = slot_def.get("anchor")
    anchor = all_slots.get(anchor_name, {})
    offset = slot_def.get("offset", {})
    size = slot_def.get("size", {})

    x = anchor.get("x", 0) + offset.get("x", 0)
    y = anchor.get("y", 0) + offset.get("y", 0)
    width = size.get("width", anchor.get("width", 100))
    height = size.get("height", anchor.get("height", 100))

    img_el = etree.Element(f"{{{SVG_NS}}}image")
    img_el.set("x", str(x))
    img_el.set("y", str(y))
    img_el.set("width", str(width))
    img_el.set("height", str(height))
    img_el.set(f"{{{XLINK_NS}}}href", f"data:image/png;base64,{b64}")
    return img_el
