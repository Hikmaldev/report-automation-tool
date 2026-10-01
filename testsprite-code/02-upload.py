"""TestSprite FE test (Playwright, async): upload accepts a CSV and reports a broken file."""
import asyncio
import os
import re

from playwright.async_api import async_playwright, expect

GOOD_CSV = (
    "Order ID,Order Date,Customer Name,Region,Qty.,Revenue\n"
    'ORD-1,09/01/2026,Acme Inc,north,2,"$1,240.00"\n'
    'ORD-2,2026-09-02,Beta Co,south,3,"\u20ac 3.040,00"\n'
    "ORD-3,31/09/2026,Gamma Ltd,north,4,not available\n"
).encode("utf-8")

BROKEN_CSV = b"Order ID,Order Date,Customer Name\nORD-1,09/01/2026,Acme Inc\nORD-2,2026-09-02\n"


async def run_test() -> None:
    target = os.environ.get("TARGET_URL", "http://127.0.0.1:8501")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(f"{target}/upload", wait_until="networkidle")

            # Attach both files in one upload (good + malformed).
            await page.set_input_files(
                'input[type="file"]',
                [
                    {"name": "sales.csv", "mimeType": "text/csv", "buffer": GOOD_CSV},
                    {"name": "broken.csv", "mimeType": "text/csv", "buffer": BROKEN_CSV},
                ],
            )

            await expect(page.get_by_text("Files ready to process")).to_be_visible(timeout=30000)
            await expect(page.get_by_text(re.compile(r"sales\.csv"))).to_be_visible()
            await expect(page.get_by_text(re.compile(r"3 rows"))).to_be_visible()

            # The malformed file surfaces a plain-language error (no traceback).
            await expect(page.get_by_text("could not be read")).to_be_visible(timeout=30000)
            await expect(page.get_by_text(re.compile(r"broken\.csv"))).to_be_visible()
            # No traceback markers on the page.
            assert "Traceback" not in await page.locator("body").inner_text()

            await expect(
                page.get_by_role("button", name=re.compile("Continue to column mapping"))
            ).to_be_visible()
        finally:
            await context.close()
            await browser.close()


asyncio.run(run_test())