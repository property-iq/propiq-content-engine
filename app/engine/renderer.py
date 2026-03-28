"""PNG renderer — uses Playwright to render composite SVG to PNG."""

import tempfile
from pathlib import Path

from playwright.async_api import async_playwright


async def render_svg_to_png(svg_content: str, width: int, height: int) -> bytes:
    """Render an SVG string to PNG bytes using Playwright.

    Args:
        svg_content: Complete SVG markup
        width: Output width in pixels
        height: Output height in pixels

    Returns:
        PNG image bytes
    """
    # Write SVG to temp file for Playwright to load
    with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False) as f:
        f.write(svg_content)
        svg_path = f.name

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": width, "height": height},
            )

            await page.goto(f"file://{svg_path}")

            # Wait for any embedded images to load
            await page.wait_for_load_state("networkidle")

            png_bytes = await page.screenshot(
                type="png",
                clip={"x": 0, "y": 0, "width": width, "height": height},
            )

            await browser.close()

        return png_bytes
    finally:
        Path(svg_path).unlink(missing_ok=True)
