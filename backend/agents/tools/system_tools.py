import time

from google.adk.tools import FunctionTool, ToolContext

from services.session import session_manager


async def get_current_time() -> dict:
    """Return the current UTC timestamp."""
    return {"utc_timestamp": time.time(), "human": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}


async def summarize_task_history(tool_context: ToolContext) -> str:
    """
    Summarize the last actions and messages of the current session.
    """
    session = await session_manager.get(tool_context.state.get("aria_session_id", ""))
    history = session.task_history if session else []
    if not history:
        return "No previous actions."
    lines = []
    for entry in history[-10:]:  # last 10 entries
        ts = time.strftime("%H:%M:%S", time.gmtime(entry.get("timestamp", 0)))
        lines.append(f"[{ts}] {entry.get('role', '?')}: {entry.get('content', '')[:120]}")
    return "\n".join(lines)


async def notify_user(message: str, level: str = "info") -> dict:
    """
    Show a toast notification to the user (level: info | warning | success | error).
    """
    return {"notification": message, "level": level, "timestamp": time.time()}


get_time_tool = FunctionTool(func=get_current_time)
summarize_history_tool = FunctionTool(func=summarize_task_history)
notify_user_tool = FunctionTool(func=notify_user)
