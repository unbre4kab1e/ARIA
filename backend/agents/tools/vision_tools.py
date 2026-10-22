from google.adk.tools import FunctionTool, ToolContext

from agents.tools.browser_tools import browser_controller
from services.vision import vision_service


async def analyze_current_screen(tool_context: ToolContext, user_intent: str = "") -> dict:
    """Take a screenshot of the current browser page and analyze it with Gemini Vision.
    Returns structured understanding of what's on screen and what actions to take."""
    try:
        screenshot = await browser_controller.screenshot(tool_context.state.get("aria_session_id", ""))
    except Exception as e:
        return {"error": f"Screenshot failed: {e}"}
    return await vision_service.analyze_screen(screenshot, user_intent or None)


async def describe_screen_element(tool_context: ToolContext, x: int = 0, y: int = 0) -> str:
    """Describe a specific UI element of the browser page at viewport coordinates (x, y)."""
    try:
        screenshot = await browser_controller.screenshot(tool_context.state.get("aria_session_id", ""))
    except Exception as e:
        return f"Screenshot failed: {e}"
    return await vision_service.describe_element(screenshot, x, y)


analyze_screen_tool = FunctionTool(func=analyze_current_screen)
describe_element_tool = FunctionTool(func=describe_screen_element)
