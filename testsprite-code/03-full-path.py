"""TestSprite FE test (Playwright, async): full happy path — upload, map, process, summary."""
import asyncio
import os
import re

from playwright.async_api import async_playwright, expect

CSV = (
    "Order ID,Order Date,Customer Name,Region,Qty.,Revenue\n"
    'ORD-1,09/01/2026,Acme Inc,north,2,"$1,240.00"\n'  # duplicate of the row below
    'ORD-1,09/01/2026,Acme Inc,north,2,"$1,240.00"\n'
    'ORD-2,2026-09-02,Beta Co,south,3,"\u20ac 3.040,00"\n'
    "ORD-3,31/09/2026,Gamma Ltd,north,4,not available\n"
).encode("utf-8")


async def run_test() -> None:
    target = os.environ.get("TARGET_URL", "http://127.0.0.1:8501")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            # ---- Step 1: upload --------------------------------------------------
            await page.goto(f"{target}/upload", wait_until="networkidle")
            await page.set_input_files(
                'input[type="file"]',
                {"name": "sales.csv", "mimeType": "text/csv", "buffer": CSV},
            )
            await expect(page.get_by_text("Files ready to process")).to_be_visible(timeout=30000)
            await expect(page.get_by_text(re.compile(r"4 rows"))).to_be_visible()

            # ---- Step 2: column mapping ------------------------------------------
            await page.get_by_role("button", name=re.compile("Continue to column mapping")).click()
            await expect(page.get_by_text("Match your columns")).to_be_visible(timeout=15000)
            await expect(page.locator('[data-testid="stDataEditor"]').first).to_be_visible(
                timeout=15000
            )
            confirm = page.get_by_role("button", name=re.compile("Confirm mapping"))
            await expect(confirm).to_be_enabled(timeout=15000)
            await confirm.click()

            # ---- Step 3: processing ------------------------------------------------
            run = page.get_by_role("button", name=re.compile("Run cleaning & validation"))
            await expect(run).to_be_visible(timeout=15000)
            await run.click()

            for label in ("Rows combined", "Duplicates removed", "Rows flagged", "Clean rows for reporting"):
                await expect(page.get_by_text(label)).to_be_visible(timeout=30000)
            await expect(page.get_by_text(re.compile(r"1 rows were flagged"))).to_be_visible()
            await expect(page.get_by_text("Cleaning log")).to_be_visible()

            # ---- Step 4: summary report ---------------------------------------------
            await page.get_by_role("button", name=re.compile("View summary report")).click()
            await expect(page.get_by_text("Summary table")).to_be_visible(timeout=15000)
            await expect(page.locator(".js-plotly-plot").first).to_be_visible(timeout=15000)
            await expect(
                page.get_by_text(re.compile(r"across 2 group\(s\) from 2 clean rows"))
            ).to_be_visible(timeout=15000)
        finally:
            await context.close()
            await browser.close()


asyncio.run(run_test())