from urllib.parse import quote_plus

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest
from google.adk.tools import FunctionTool, ToolContext
from google.genai import types

from agents.tools.browser_tools import browser_controller
from agents.tools.system_tools import get_time_tool, notify_user_tool, summarize_history_tool
from agents.tools.vision_tools import analyze_screen_tool, describe_element_tool
from config import config

# Key under which the ARIA session id is stored in the ADK session state.
# Tools read it from `tool_context.state` — the model never has to pass it.
SESSION_STATE_KEY = "aria_session_id"


def session_id_from(tool_context: ToolContext) -> str:
    return tool_context.state.get(SESSION_STATE_KEY, "")


# --- Browser action tools (wrapped as ADK FunctionTools) ---


async def navigate_to(url: str, tool_context: ToolContext) -> dict:
    """Navigate the controlled browser to the given URL."""
    return await browser_controller.navigate(session_id_from(tool_context), url)


async def click_element(
    tool_context: ToolContext,
    selector: str = "",
    x: int = -1,
    y: int = -1,
    confirmed: bool = False,
) -> dict:
    """Click a UI element. Provide either a CSS/Playwright `selector` OR viewport coordinates `x` and `y` (viewport is 1280x800).
    Set confirmed=true ONLY after the user explicitly approved a sensitive action (purchase, payment, sending, deleting)."""
    return await browser_controller.click(
        session_id_from(tool_context),
        selector=selector or None,
        x=x if x >= 0 else None,
        y=y if y >= 0 else None,
        confirmed=confirmed,
    )


async def type_into_field(
    selector: str,
    text: str,
    tool_context: ToolContext,
    clear_first: bool = True,
) -> dict:
    """Type text into an input field identified by CSS/Playwright selector."""
    return await browser_controller.type_text(session_id_from(tool_context), selector, text, clear_first)


async def scroll_page(
    tool_context: ToolContext,
    direction: str = "down",
    amount: int = 500,
) -> dict:
    """Scroll the browser page up or down by `amount` pixels."""
    return await browser_controller.scroll(session_id_from(tool_context), direction, amount)


async def press_keyboard_key(key: str, tool_context: ToolContext) -> dict:
    """Press a keyboard key, e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown'."""
    return await browser_controller.press_key(session_id_from(tool_context), key)


async def read_page_content(tool_context: ToolContext) -> dict:
    """Extract the visible text content from the current browser page."""
    return await browser_controller.get_page_text(session_id_from(tool_context))


async def wait_for_element(selector: str, tool_context: ToolContext, timeout_ms: int = 5000) -> dict:
    """Wait until a CSS selector becomes visible on the page."""
    return await browser_controller.wait_for_selector(session_id_from(tool_context), selector, timeout_ms)


async def search_web(query: str, tool_context: ToolContext, engine: str = "google") -> dict:
    """Search the web for a query. This is the FASTEST way to search.
    engine: 'google' (default) | 'bing' | 'duckduckgo'"""
    encoded = quote_plus(query)
    urls = {
        "google": f"https://www.google.com/search?q={encoded}",
        "bing": f"https://www.bing.com/search?q={encoded}",
        "duckduckgo": f"https://duckduckgo.com/?q={encoded}",
    }
    url = urls.get(engine, urls["google"])
    return await browser_controller.navigate(session_id_from(tool_context), url)


async def get_current_url(tool_context: ToolContext) -> dict:
    """Get the current URL and page title of the browser."""
    return await browser_controller.get_current_url(session_id_from(tool_context))


# --- Context hygiene ---


def keep_only_latest_image(callback_context: CallbackContext, llm_request: LlmRequest):
    """Screenshots pile up in the session history: send only the most recent one
    to the model, replacing older ones with a short placeholder."""
    seen_latest = False
    for content in reversed(llm_request.contents or []):
        parts = content.parts or []
        if not any(p.inline_data for p in parts):
            continue
        if not seen_latest:
            seen_latest = True
            continue
        content.parts = [
            types.Part(text="[earlier screenshot omitted]") if p.inline_data else p
            for p in parts
        ]
    return None


# --- ADK Agent definition ---

ARIA_AGENT_INSTRUCTION = """You are ARIA -- an autonomous AI agent that controls a dedicated Chromium browser window.

IMPORTANT: You control YOUR OWN browser (Chromium), NOT the user's browser.
When the user says "search for X" or "go to Y", you must navigate YOUR browser there.
The user sees a live preview of your browser. A message may also include a screenshot
of the USER's own screen as context -- you cannot click on it, only look at it.

## Task shortcuts -- DO THESE DIRECTLY:
- "search for X" -> search_web(query="X")
- "go to / open / navigate to [site]" -> navigate_to(url="https://site.com")
- "click [text]" -> click_element(selector="text=Click text here")
- "type X" -> type_into_field(selector=<known selector>, text="X")
- "scroll down" -> scroll_page(direction="down")
- "press Enter" -> press_keyboard_key(key="Enter")

## Common selectors:
- Google search bar: textarea[name="q"]
- YouTube search: input[name="search_query"]
- Generic search inputs: input[type="search"], input[type="text"], textarea

## Rules:
1. For search tasks: ALWAYS use search_web() first -- it's one step.
2. Only call analyze_current_screen when you genuinely don't know what's on the page.
3. If a selector fails, try: text=ButtonLabel, role=button[name="..."], or coordinates from analyze_current_screen.
4. When done, reply with a short status (1-2 sentences) in the user's language.
5. Never navigate to harmful or illegal websites.
6. SENSITIVE ACTIONS (buying, paying, booking, sending a message/email, deleting,
   submitting personal data): STOP and ask the user to confirm, describing exactly
   what will happen. If a tool returns status "needs_confirmation", do the same.
   Only when the user's latest message explicitly approves, call again with confirmed=true.
7. Private/internal addresses are blocked on purpose -- do not try to work around it.
"""

aria_agent = Agent(
    name="ARIA",
    model=config.GEMINI_AGENT_MODEL,
    description="Adaptive Reality Intelligence Assistant -- voice + vision browser control agent",
    instruction=ARIA_AGENT_INSTRUCTION,
    before_model_callback=keep_only_latest_image,
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
