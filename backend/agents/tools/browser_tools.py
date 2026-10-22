import asyncio
import logging
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import config

logger = logging.getLogger("aria.browser")

VIEWPORT = {"width": 1280, "height": 800}


class BrowserController:
    """
    Playwright-based browser controller used by the ARIA agent as tool execution layer.
    Each ARIA session gets its own browser context for isolation.
    """

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._contexts: dict[str, BrowserContext] = {}
        self._start_lock = asyncio.Lock()
        self.last_error: str | None = None

    @property
    def ready(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def start(self):
        """Launch Chromium. Failures are logged, not raised, so the API stays up."""
        async with self._start_lock:
            if self.ready:
                return
            try:
                if not self._playwright:
                    self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=config.BROWSER_HEADLESS,
                    executable_path=config.BROWSER_EXECUTABLE_PATH or None,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                self.last_error = None
                logger.info("Playwright browser launched.")
            except Exception as e:
                self.last_error = str(e)
                logger.error(
                    "Could not launch Chromium (run `playwright install chromium`): %s", e
                )

    async def stop(self):
        for ctx in list(self._contexts.values()):
            try:
                await ctx.close()
            except Exception:
                pass
        self._contexts.clear()
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def get_or_create_context(self, session_id: str) -> BrowserContext:
        if not self.ready:
            await self.start()
        if not self.ready:
            raise RuntimeError(f"Browser unavailable: {self.last_error}")
        if session_id not in self._contexts:
            self._contexts[session_id] = await self._browser.new_context(
                viewport=VIEWPORT,
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
            try:
                await ctx.close()
            except Exception:
                pass

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
        try:
            page = await self._get_page(session_id)
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
        try:
            page = await self._get_page(session_id)
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
        try:
            page = await self._get_page(session_id)
            if clear_first:
                await page.fill(selector, "", timeout=config.BROWSER_TIMEOUT_MS)
            await page.locator(selector).first.press_sequentially(
                text, delay=30, timeout=config.BROWSER_TIMEOUT_MS
            )
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
        try:
            page = await self._get_page(session_id)
            delta = amount if direction == "down" else -amount
            await page.mouse.wheel(0, delta)
            return {"status": "ok", "action": "scroll", "direction": direction, "amount": amount}
        except Exception as e:
            return {"status": "error", "error": f"Scroll failed: {e}"}

    # ─── Tool: screenshot ─────────────────────────────────────────────────────

    async def screenshot(self, session_id: str) -> bytes:
        """Capture a PNG screenshot of the current page."""
        page = await self._get_page(session_id)
        return await page.screenshot(type="png", full_page=False)

    async def frame_jpeg(self, session_id: str) -> bytes | None:
        """Compact JPEG frame for the live preview; None if nothing to show."""
        ctx = self._contexts.get(session_id)
        if not ctx or not ctx.pages:
            return None
        try:
            return await ctx.pages[-1].screenshot(type="jpeg", quality=60, full_page=False)
        except Exception:
            return None

    # ─── Tool: get_page_text ──────────────────────────────────────────────────

    async def get_page_text(self, session_id: str) -> dict[str, Any]:
        """Extract visible text content from the current page."""
        try:
            page = await self._get_page(session_id)
            text = await page.evaluate("() => document.body ? document.body.innerText : ''")
            title = await page.title()
            truncated = len(text) > 8000
            return {"url": page.url, "title": title, "text": text[:8000], "truncated": truncated}
        except Exception as e:
            return {"status": "error", "error": f"Read failed: {e}"}

    # ─── Tool: press_key ──────────────────────────────────────────────────────

    async def press_key(self, session_id: str, key: str) -> dict[str, Any]:
        """Press a keyboard key (e.g. 'Enter', 'Tab', 'Escape')."""
        try:
            page = await self._get_page(session_id)
            await page.keyboard.press(key)
            return {"status": "ok", "action": "key_press", "key": key}
        except Exception as e:
            return {"status": "error", "error": f"Key press failed: {e}"}

    # ─── Tool: wait_for ───────────────────────────────────────────────────────

    async def wait_for_selector(
        self, session_id: str, selector: str, timeout_ms: int = 5000
    ) -> dict[str, Any]:
        """Wait until a CSS selector appears on the page."""
        try:
            page = await self._get_page(session_id)
            await page.wait_for_selector(selector, timeout=timeout_ms)
            return {"status": "found", "selector": selector}
        except Exception:
            return {"status": "timeout", "selector": selector}

    # ─── Tool: get_current_url ────────────────────────────────────────────────

    async def get_current_url(self, session_id: str) -> dict[str, Any]:
        """Get the current URL and page title."""
        try:
            page = await self._get_page(session_id)
            return {"url": page.url, "title": await page.title()}
        except Exception as e:
            return {"status": "error", "error": str(e)}


browser_controller = BrowserController()
