"""
ADK Agent Runner — bridges the ARIA WebSocket session with the Google ADK agent.

Flow:
  1. Receives user messages from the WebSocket handler
  2. Runs them through the ADK InMemoryRunner (stateful, per-session)
  3. Streams text events back via callbacks
  4. ADK handles tool execution automatically
"""

import asyncio
import base64
import logging
from typing import Any

from google.adk.runners import InMemoryRunner
from google.adk.sessions import Session
from google.genai import types as genai_types

from agents.aria_agent import aria_agent
from agents.tools.browser_tools import browser_controller
from config import config
from services.session import ARIASession, SessionState

logger = logging.getLogger("aria.runner")

APP_NAME = "aria"


class ARIAAgentRunner:
    """
    One instance per ARIA session.
    Wraps ADK InMemoryRunner to handle multi-turn conversations.
    """

    def __init__(self, aria_session: ARIASession):
        self.aria_session = aria_session
        self._runner = InMemoryRunner(
            agent=aria_agent,
            app_name=APP_NAME,
        )
        self._adk_session: Session | None = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Initialize the ADK session."""
        self._adk_session = await self._runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=self.aria_session.session_id,
        )
        logger.info(f"ADK session started: {self._adk_session.id}")
        await browser_controller.get_or_create_context(self.aria_session.session_id)

    async def stop(self):
        """Clean up browser context."""
        await browser_controller.close_context(self.aria_session.session_id)
        logger.info(f"ADK runner stopped for session {self.aria_session.session_id}")

    async def run_turn(
        self,
        user_message: str,
        screenshot_b64: str | None = None,
        on_text: Any = None,
        on_action: Any = None,
        on_state_change: Any = None,
    ) -> str:
        if not self._adk_session:
            raise RuntimeError("Runner not started. Call start() first.")

        async with self._lock:
            self.aria_session.state = SessionState.THINKING
            if on_state_change:
                await on_state_change(SessionState.THINKING)

            # Build message with optional screenshot context
            parts: list[genai_types.Part] = []

            if screenshot_b64:
                parts.append(
                    genai_types.Part(
                        inline_data=genai_types.Blob(
                            mime_type="image/jpeg",
                            data=base64.b64decode(screenshot_b64),
                        )
                    )
                )

            # Prepend session_id context so tools know which browser to control
            augmented_message = (
                f"[session_id={self.aria_session.session_id}]\n{user_message}"
            )
            parts.append(genai_types.Part(text=augmented_message))

            content = genai_types.Content(role="user", parts=parts)
            full_response = ""

            try:
                async for event in self._runner.run_async(
                    user_id=self.aria_session.session_id,
                    session_id=self._adk_session.id,
                    new_message=content,
                ):
                    if self.aria_session.interrupted:
                        logger.info("Turn interrupted by user.")
                        self.aria_session.resume()
                        break

                    # Text response
                    if event.is_final_response():
                        text = ""
                        if event.content and event.content.parts:
                            text = event.content.parts[0].text or ""
                        if text:
                            full_response += text
                            if on_text:
                                await on_text(text)

                    # Tool call event — narrate the action
                    elif hasattr(event, "get_function_calls") and event.get_function_calls():
                        calls = event.get_function_calls()
                        for call in calls:
                            self.aria_session.state = SessionState.ACTING
                            if on_state_change:
                                await on_state_change(SessionState.ACTING)

                            detail = _summarize_tool_call(call.name, call.args)
                            logger.info(f"Tool call: {call.name}({detail})")

                            if on_action:
                                await on_action(call.name, detail)

                            self.aria_session.add_to_history(
                                "action", f"{call.name}: {detail}"
                            )

            except asyncio.CancelledError:
                logger.info("Turn cancelled.")
                raise
            except Exception as e:
                logger.error(f"Runner turn error: {e}", exc_info=True)
                raise

            self.aria_session.state = SessionState.LISTENING
            if on_state_change:
                await on_state_change(SessionState.LISTENING)

            self.aria_session.add_to_history("aria", full_response)
            return full_response


def _summarize_tool_call(name: str, args: dict | None) -> str:
    if not args:
        return ""
    a = args or {}
    summaries: dict[str, str] = {
        "navigate_to":             a.get("url", ""),
        "click_element":           a.get("selector") or f"({a.get('x')},{a.get('y')})",
        "type_into_field":         f'"{a.get("text", "")[:40]}" -> {a.get("selector", "")}',
        "scroll_page":             f'{a.get("direction", "down")} {a.get("amount", 500)}px',
        "press_keyboard_key":      a.get("key", ""),
        "read_page_content":       "extracting text",
        "wait_for_element":        a.get("selector", ""),
        "analyze_current_screen":  a.get("user_intent", "analyzing screen"),
        "describe_screen_element": f'({a.get("x")},{a.get("y")})',
        "search_web":              f'{a.get("query", "")} ({a.get("engine", "google")})',
        "get_current_url":         "checking current page",
        "get_time":                "checking time",
        "notify_user":             a.get("message", ""),
        "summarize_history":       "summarizing session",
    }
    return summaries.get(name, str(a)[:80])
