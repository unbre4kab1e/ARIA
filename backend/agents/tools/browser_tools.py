import logging
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import config

logger = logging.getLogger("aria.browser")


class BrowserController:
    """
    Playwright-based browser controller used by the ARIA agent as tool execution layer.
    Each ARIA session gets its own browser context for isolation.
    """

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._contexts: dict[str, BrowserContext] = {}

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=config.BROWSER_HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        logger.info("Playwright browser launched.")

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_or_create_context(self, session_id: str) -> BrowserContext:
        if not self._browser:
            raise RuntimeError("Browser not started. Call start() first.")
        if session_id not in self._contexts:
            self._contexts[session_id] = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
        return self._contexts[session_id]

    async def close_context(self, session_id: str):
        ctx = self._contexts.pop(session_id, None)
        if ctx:
            await ctx.close()

    async def _get_page(self, session_id: str) -> Page:
        ctx = await self.get_or_create_context(session_id)
        pages = ctx.pages
        if not pages:
            page = await ctx.new_page()
        else:
            page = pages[-1]
        return page

    # ─── Tool: navigate ───────────────────────────────────────────────────────

    async def navigate(self, session_id: str, url: str) -> dict[str, Any]:
        """Navigate the browser to a URL."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        page = await self._get_page(session_id)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=config.BROWSER_TIMEOUT_MS)
            title = await page.title()
            logger.info(f"Navigated to {page.url} ({title})")
            return {"status": "ok", "url": page.url, "title": title}
        except Exception as e:
            return {"status": "error", "error": f"Navigation failed: {e}"}

    # ─── Tool: click ──────────────────────────────────────────────────────────

    async def click(
        self,
        session_id: str,
        selector: str | None = None,
        x: int | None = None,
        y: int | None = None,
    ) -> dict[str, Any]:
        """Click an element by CSS selector or by (x, y) coordinates."""
        page = await self._get_page(session_id)
        try:
            if selector:
                await page.click(selector, timeout=config.BROWSER_TIMEOUT_MS)
                return {"status": "ok", "action": "click", "target": selector}
            elif x is not None and y is not None:
                await page.mouse.click(x, y)
                return {"status": "ok", "action": "click", "target": f"({x},{y})"}
            return {"status": "error", "error": "Provide either selector or (x, y) coordinates."}
        except Exception as e:
            return {"status": "error", "error": f"Click failed: {e}"}

    # ─── Tool: type_text ──────────────────────────────────────────────────────

    async def type_text(
        self,
        session_id: str,
        selector: str,
        text: str,
        clear_first: bool = True,
    ) -> dict[str, Any]:
        """Type text into an input element."""
        page = await self._get_page(session_id)
        try:
            if clear_first:
                await page.fill(selector, "", timeout=config.BROWSER_TIMEOUT_MS)
            await page.type(selector, text, delay=30, timeout=config.BROWSER_TIMEOUT_MS)
            return {"status": "ok", "action": "type", "selector": selector, "text": text}
        except Exception as e:
            return {"status": "error", "error": f"Type failed: {e}"}

    # ─── Tool: scroll ─────────────────────────────────────────────────────────

    async def scroll(
        self,
        session_id: str,
        direction: str = "down",
        amount: int = 500,
    ) -> dict[str, Any]:
        """Scroll the page up or down."""
        page = await self._get_page(session_id)
        delta = amount if direction == "down" else -amount
        await page.mouse.wheel(0, delta)
        return {"status": "ok", "action": "scroll", "direction": direction, "amount": amount}

    # ─── Tool: screenshot ─────────────────────────────────────────────────────

    async def screenshot(self, session_id: str) -> bytes:
        """Capture a PNG screenshot of the current page."""
        page = await self._get_page(session_id)
        return await page.screenshot(type="png", full_page=False)

    # ─── Tool: get_page_text ──────────────────────────────────────────────────

    async def get_page_text(self, session_id: str) -> dict[str, Any]:
        """Extract visible text content from the current page."""
        page = await self._get_page(session_id)
        text = await page.evaluate("() => document.body.innerText")
        url = page.url
        title = await page.title()
        truncated = len(text) > 8000
        return {"url": url, "title": title, "text": text[:8000], "truncated": truncated}

    # ─── Tool: press_key ──────────────────────────────────────────────────────

    async def press_key(self, session_id: str, key: str) -> dict[str, Any]:
        """Press a keyboard key (e.g. 'Enter', 'Tab', 'Escape')."""
        page = await self._get_page(session_id)
        await page.keyboard.press(key)
        return {"status": "ok", "action": "key_press", "key": key}

    # ─── Tool: wait_for ───────────────────────────────────────────────────────

    async def wait_for_selector(
        self, session_id: str, selector: str, timeout_ms: int = 5000
    ) -> dict[str, Any]:
        """Wait until a CSS selector appears on the page."""
        page = await self._get_page(session_id)
        try:
            await page.wait_for_selector(selector, timeout=timeout_ms)
            return {"status": "found", "selector": selector}
        except Exception:
            return {"status": "timeout", "selector": selector}

    # ─── Tool: get_current_url ────────────────────────────────────────────────

    async def get_current_url(self, session_id: str) -> dict[str, Any]:
        """Get the current URL and page title."""
        page = await self._get_page(session_id)
        return {"url": page.url, "title": await page.title()}


browser_controller = BrowserController()
