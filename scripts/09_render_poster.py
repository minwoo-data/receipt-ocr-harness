"""09_render_poster.py - Render poster/poster.html to a print PDF (17 x 11 in)
and a PNG preview with headless Chromium (Playwright).

    python scripts/09_render_poster.py
Outputs:
    poster/Park_Minwoo_MISM_ReceiptOCR.pdf   (vector, fonts embedded)
    poster/preview.png                        (150 dpi raster for a quick look)
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "poster" / "poster.html"
PDF = ROOT / "poster" / "Park_Minwoo_MISM_ReceiptOCR.pdf"
PNG = ROOT / "poster" / "preview.png"


def main() -> None:
    scale = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 17 * 96, "height": 11 * 96}, device_scale_factor=1.5)
        page.goto(HTML.resolve().as_uri())
        page.wait_for_load_state("networkidle")
        page.emulate_media(media="print")
        page.pdf(path=str(PDF), width="17in", height="11in", print_background=True, prefer_css_page_size=True,
                 scale=scale, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        page.emulate_media(media="screen")
        page.screenshot(path=str(PNG), full_page=False)
        # Overflow check: anything taller than the page is a layout bug.
        h = page.evaluate("document.querySelector('.page').scrollHeight")
        browser.close()
    print(f"pdf: {PDF}\npng: {PNG}\npage scrollHeight px: {h} (page box is {11*96} px)")
    if h > 11 * 96 + 2:
        print("WARNING: content overflows the 11in page height")


if __name__ == "__main__":
    main()
