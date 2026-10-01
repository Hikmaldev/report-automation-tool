"""TestSprite FE test (Playwright, async): mapping blocks when required columns are missing."""
import asyncio
import os
import re

from playwright.async_api import async_playwright, expect

MINIMAL_CSV = b"Name,Value\nAcme,100\nBeta,200\n"


async def run_test() -> None:
    target = os.environ.get("TARGET_URL", "http://127.0.0.1:8501")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(f"{target}/upload", wait_until="networkidle")
            await page.set_input_files(
                'input[type="file"]',
                {"name": "minimal.csv", "mimeType": "text/csv", "buffer": MINIMAL_CSV},
            )
            await expect(page.get_by_text("Files ready to process")).to_be_visible(timeout=30000)

            await page.get_by_role("button", name=re.compile("Continue to column mapping")).click()

            # Required columns are all missing -> explicit warning + disabled confirm.
            await expect(page.get_by_text(re.compile("Missing required columns"))).to_be_visible(
                timeout=15000
            )
            for required in ("order_id", "date", "customer", "region", "revenue"):
                await expect(
                    page.get_by_text(re.compile(rf"\b{required}\b"))
                ).to_be_visible(timeout=15000)

            confirm = page.get_by_role("button", name=re.compile("Confirm mapping"))
            await expect(confirm).to_be_disabled(timeout=15000)
        finally:
            await context.close()
            await browser.close()


asyncio.run(run_test())