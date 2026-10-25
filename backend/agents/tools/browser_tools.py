import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Route

from config import config
from services.url_guard import check_url

logger = logging.getLogger("aria.browser")

VIEWPORT = {"width": 1280, "height": 800}

# Clicking something labelled like this needs the user's explicit go-ahead
SENSITIVE_ACTION = re.compile(
    r"\b(buy|pay|purchase|checkout|check out|place order|order now|confirm (order|purchase|payment)|"
    r"subscribe|send|delete|remove account|transfer|donate|book now|"
    r"acheter|achat|payer|paiement|commander|valider (la|ma) commande|s'abonner|abonnez|"
    r"envoyer|supprimer|virement|faire un don|r[ée]server)\b",
    re.IGNORECASE,
)

_ELEMENT_LABEL_JS = """el => {
  const t = el.closest('button, a, input, [role=button], [role=link]') || el;
  return (t.innerText || t.value || t.getAttribute('aria-label') || t.title || '').slice(0, 200);
}"""


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
            ctx = await self._browser.new_context(
                viewport=VIEWPORT,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            # Every request (navigation, redirect, subresource) goes through the guard
            await ctx.route("**/*", self._guard_request)
            self._contexts[session_id] = ctx
        return self._contexts[session_id]

    @staticmethod
    async def _guard_request(route: Route):
        url = route.request.url
        if urlsplit(url).scheme in ("http", "https"):
            reason = await check_url(url)
            if reason:
                logger.warning(f"Blocked request to {url}: {reason}")
                await route.abort("blockedbyclient")
                return
        await route.continue_()

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
        if "://" not in url:
            url = f"https://{url}"
        reason = await check_url(url)
        if reason:
            return {"status": "error", "error": f"Navigation blocked: {reason}"}
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
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """Click an element by CSS selector or by (x, y) coordinates.
        Clicks on purchase/payment/send/delete-like elements need confirmed=True."""
        try:
            page = await self._get_page(session_id)
            if not confirmed:
                label = await self._element_label(page, selector, x, y)
                if SENSITIVE_ACTION.search(f"{selector or ''} {label}"):
                    return {
                        "status": "needs_confirmation",
                        "element": label.strip() or selector,
                        "message": "This looks like a sensitive action. Ask the user to confirm, "
                                   "then call again with confirmed=true.",
                    }
            if selector:
                await page.click(selector, timeout=config.BROWSER_TIMEOUT_MS)
                return {"status": "ok", "action": "click", "target": selector}
            elif x is not None and y is not None:
                await page.mouse.click(x, y)
                return {"status": "ok", "action": "click", "target": f"({x},{y})"}
            return {"status": "error", "error": "Provide either selector or (x, y) coordinates."}
        except Exception as e:
            return {"status": "error", "error": f"Click failed: {e}"}

    @staticmethod
    async def _element_label(page: Page, selector: str | None, x: int | None, y: int | None) -> str:
        """Visible label of the element about to be clicked ('' if unknown)."""
        try:
            if selector:
                return await page.locator(selector).first.evaluate(_ELEMENT_LABEL_JS, timeout=2000)
            if x is not None and y is not None:
                return await page.evaluate(
                    f"([x, y]) => {{ const el = document.elementFromPoint(x, y); "
                    f"return el ? ({_ELEMENT_LABEL_JS})(el) : ''; }}",
                    [x, y],
                )
        except Exception:
            pass
        return ""

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

    async def frame_jpeg(self, session_id: str) -> tuple[bytes, str, str] | None:
        """(JPEG, url, title) of the current page for the live preview; None if nothing to show."""
        ctx = self._contexts.get(session_id)
        if not ctx or not ctx.pages:
            return None
        page = ctx.pages[-1]
        try:
            frame = await page.screenshot(type="jpeg", quality=60, full_page=False)
            return frame, page.url, await page.title()
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
