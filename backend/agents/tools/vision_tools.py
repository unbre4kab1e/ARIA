from google.adk.tools import FunctionTool

from agents.tools.browser_tools import browser_controller
from services.vision import vision_service


async def analyze_current_screen(session_id: str = "", user_intent: str = "") -> dict:
    """Take a screenshot of the current browser page and analyze it with Gemini Vision.
    Returns structured understanding of what's on screen and what actions to take."""
    screenshot = await browser_controller.screenshot(session_id)
    return await vision_service.analyze_screen(screenshot, user_intent or None)


async def describe_screen_element(session_id: str = "", x: int = 0, y: int = 0) -> str:
    """Describe a specific UI element the user is pointing at (by screen coordinates)."""
    screenshot = await browser_controller.screenshot(session_id)
    return await vision_service.describe_element(screenshot, x, y)


analyze_screen_tool = FunctionTool(func=analyze_current_screen)
describe_element_tool = FunctionTool(func=describe_screen_element)
