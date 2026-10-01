"""TestSprite FE test (Playwright, async): download center offers xlsx and csv for every artifact."""
import asyncio
import os
import re

from playwright.async_api import async_playwright, expect

CSV = (
    "Order ID,Order Date,Customer Name,Region,Qty.,Revenue\n"
    'ORD-1,09/01/2026,Acme Inc,north,2,"$1,240.00"\n'
    "ORD-2,31/09/2026,Beta Co,south,3,not available\n"
).encode("utf-8")


async def run_test() -> None:
    target = os.environ.get("TARGET_URL", "http://127.0.0.1:8501")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            # Build the pipeline: upload -> map -> process.
            await page.goto(f"{target}/upload", wait_until="networkidle")
            await page.set_input_files(
                'input[type="file"]',
                {"name": "sales.csv", "mimeType": "text/csv", "buffer": CSV},
            )
            await expect(page.get_by_text("Files ready to process")).to_be_visible(timeout=30000)
            await page.get_by_role("button", name=re.compile("Continue to column mapping")).click()
            await expect(page.get_by_text("Match your columns")).to_be_visible(timeout=15000)
            confirm = page.get_by_role("button", name=re.compile("Confirm mapping"))
            await expect(confirm).to_be_enabled(timeout=15000)
            await confirm.click()
            run = page.get_by_role("button", name=re.compile("Run cleaning & validation"))
            await expect(run).to_be_visible(timeout=15000)
            await run.click()
            await expect(page.get_by_text("Rows flagged")).to_be_visible(timeout=30000)

            # Navigate to the download center via the review page (real user flow).
            await page.get_by_role("button", name=re.compile("Review flagged rows")).click()
            await expect(page.get_by_text("Rows that need your attention")).to_be_visible(timeout=15000)
            await page.get_by_role("button", name=re.compile("Continue to download center")).click()

            await expect(page.get_by_text("Your report package is ready")).to_be_visible(timeout=15000)
            for section in ("Clean dataset", "Summary report", "Flagged rows"):
                await expect(page.get_by_text(section)).to_be_visible(timeout=15000)

            # 1 clean row -> clean & flagged xlsx+csv; summary is xlsx only.
            await expect(page.get_by_text(re.compile(r"1 validated rows"))).to_be_visible()
            await expect(page.get_by_text(re.compile(r"1 group\(s\)"))).to_be_visible()
            await expect(page.get_by_role("link", name="Download .xlsx")).to_have_count(3)
            await expect(page.get_by_role("link", name="Download .csv")).to_have_count(2)

            await expect(page.get_by_text(re.compile(r"1 rows with every reason"))).to_be_visible()
        finally:
            await context.close()
            await browser.close()


asyncio.run(run_test())