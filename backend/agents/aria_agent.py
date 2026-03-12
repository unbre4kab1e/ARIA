from urllib.parse import quote_plus

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from agents.tools.browser_tools import browser_controller
from agents.tools.system_tools import get_time_tool, notify_user_tool, summarize_history_tool
from agents.tools.vision_tools import analyze_screen_tool, describe_element_tool
from config import config

# --- Browser action tools (wrapped as ADK FunctionTools) ---


async def navigate_to(url: str, session_id: str = "") -> dict:
    """Navigate the controlled browser to the given URL.
    The session_id is extracted from the conversation context [session_id=...] line."""
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    return await browser_controller.navigate(session_id, url)


async def click_element(
    selector: str | None = None,
    x: int | None = None,
    y: int | None = None,
    session_id: str = "",
) -> dict:
    """Click a UI element. Provide either a CSS `selector` OR screen coordinates `x` and `y`."""
    return await browser_controller.click(session_id, selector=selector, x=x, y=y)


async def type_into_field(
    selector: str,
    text: str,
    clear_first: bool = True,
    session_id: str = "",
) -> dict:
    """Type text into an input field identified by CSS selector."""
    return await browser_controller.type_text(session_id, selector, text, clear_first)


async def scroll_page(
    direction: str = "down",
    amount: int = 500,
    session_id: str = "",
) -> dict:
    """Scroll the browser page up or down by `amount` pixels."""
    return await browser_controller.scroll(session_id, direction, amount)


async def press_keyboard_key(key: str, session_id: str = "") -> dict:
    """Press a keyboard key, e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown'."""
    return await browser_controller.press_key(session_id, key)


async def read_page_content(session_id: str = "") -> dict:
    """Extract the visible text content from the current browser page."""
    return await browser_controller.get_page_text(session_id)


async def wait_for_element(selector: str, timeout_ms: int = 5000, session_id: str = "") -> dict:
    """Wait until a CSS selector becomes visible on the page."""
    return await browser_controller.wait_for_selector(session_id, selector, timeout_ms)


async def search_web(query: str, engine: str = "google", session_id: str = "") -> dict:
    """Search the web for a query. This is the FASTEST way to search.
    engine: 'google' (default) | 'bing' | 'duckduckgo'"""
    encoded = quote_plus(query)
    urls = {
        "google": f"https://www.google.com/search?q={encoded}",
        "bing": f"https://www.bing.com/search?q={encoded}",
        "duckduckgo": f"https://duckduckgo.com/?q={encoded}",
    }
    url = urls.get(engine, urls["google"])
    return await browser_controller.navigate(session_id, url)


async def get_current_url(session_id: str = "") -> dict:
    """Get the current URL and page title of the browser."""
    return await browser_controller.get_current_url(session_id)


# --- ADK Agent definition ---

ARIA_AGENT_INSTRUCTION = """You are ARIA -- an autonomous AI agent that controls a dedicated Chromium browser window.

IMPORTANT: You control YOUR OWN browser (Chromium), NOT the user's browser.
When the user says "search for X" or "go to Y", you must navigate YOUR browser there.

IMPORTANT: The session_id is provided in the user message as [session_id=...].
You MUST pass this session_id to ALL browser tool calls.

## Task shortcuts -- DO THESE DIRECTLY:
- "search for X" -> use search_web(query="X", session_id="<from context>")
- "go to / open / navigate to [site]" -> navigate_to(url="https://site.com", session_id="<from context>")
- "click [text]" -> click_element(selector="text=Click text here", session_id="<from context>")
- "type X" -> type_into_field(selector=<known selector>, text="X", session_id="<from context>")
- "scroll down" -> scroll_page(direction="down", session_id="<from context>")
- "press Enter" -> press_keyboard_key(key="Enter", session_id="<from context>")

## Common selectors:
- Google search bar: textarea[name="q"]
- Google search button: input[name="btnK"]
- YouTube search: input#search
- Generic search inputs: input[type="search"], input[type="text"], textarea

## Rules:
1. For search tasks: ALWAYS use search_web() first -- it's one step.
2. Only call analyze_current_screen when you genuinely don't know what's on the page.
3. If a selector fails, try: text=ButtonLabel, role=button name=..., or coordinates.
4. After every action, give a short spoken status update.
5. Never navigate to harmful or illegal websites.
6. ALWAYS extract the session_id from the [session_id=...] line in the user message.
"""

aria_agent = Agent(
    name="ARIA",
    model=config.GEMINI_AGENT_MODEL,
    description="Adaptive Reality Intelligence Assistant -- voice + vision browser control agent",
    instruction=ARIA_AGENT_INSTRUCTION,
    tools=[
        FunctionTool(func=search_web),
        FunctionTool(func=get_current_url),
        FunctionTool(func=navigate_to),
        FunctionTool(func=click_element),
        FunctionTool(func=type_into_field),
        FunctionTool(func=scroll_page),
        FunctionTool(func=press_keyboard_key),
        FunctionTool(func=read_page_content),
        FunctionTool(func=wait_for_element),
        analyze_screen_tool,
        describe_element_tool,
        get_time_tool,
        notify_user_tool,
        summarize_history_tool,
    ],
)
