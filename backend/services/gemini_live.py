import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from google import genai
from google.genai import types

from config import config
from services.session import ARIASession, SessionState

logger = logging.getLogger("aria.live")

ARIA_SYSTEM_PROMPT = """You are ARIA (Adaptive Reality Intelligence Assistant), an advanced AI co-pilot.

Personality:
- Calm, precise, and proactive
- Keep spoken responses short (1-3 sentences)
- Respond in the same language as the user
"""

LIVE_TOOL_PROMPT = """
You control a real web browser through the tool `execute_browser_task`.
- Whenever the user wants something done or looked up on the web (search, open a site,
  click, fill, read a page, compare prices...), call `execute_browser_task` with a complete,
  self-contained instruction that includes every detail the user gave.
- Before calling it, say one very short sentence (e.g. "I'm on it.").
- When the result comes back, tell the user what was done or found in 1-2 sentences.
  Do not invent results: only report what the tool returned.
- If the result asks for confirmation (purchase, payment, sending, deleting...), ask the
  user. Only if they clearly agree, call the tool again with an instruction that starts
  with "The user confirmed:".
- For small talk or general questions, just answer, without the tool.
"""

BROWSER_TASK_TOOL = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="execute_browser_task",
        description=(
            "Perform a task in ARIA's web browser (search, navigate, click, type, read pages). "
            "Returns a short report of what was done and found."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "instruction": types.Schema(
                    type=types.Type.STRING,
                    description="Complete instruction, in the user's language, with all details.",
                ),
            },
            required=["instruction"],
        ),
    )
])

ToolHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class GeminiLiveService:
    def __init__(self):
        self._client = genai.Client(
            api_key=config.GOOGLE_API_KEY,
            http_options={"api_version": "v1alpha"},
        )

    def _build_live_config(self, with_tools: bool, resume_handle: str | None) -> types.LiveConnectConfig:
        prompt = ARIA_SYSTEM_PROMPT + (LIVE_TOOL_PROMPT if with_tools else "")
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part(text=prompt)]),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            tools=[BROWSER_TASK_TOOL] if with_tools else None,
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            # Lifts the ~15 min audio session limit by trimming old context
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow()
            ),
            # Lets us reconnect after the server recycles the connection (~10 min)
            session_resumption=types.SessionResumptionConfig(handle=resume_handle),
        )

    async def run_session(
        self,
        aria_session: ARIASession,
        audio_input_stream: AsyncIterator[bytes],
        on_text: Any = None,
        on_audio: Any = None,
        on_state_change: Any = None,
        on_user_speech: Any = None,
        on_tool_call: ToolHandler | None = None,
        on_tool_cancel: Callable[[list[str]], Awaitable[None]] | None = None,
        resume_state: dict[str, Any] | None = None,
    ):
        """Run one Live connection until it closes.

        `resume_state` is a dict shared across reconnects: it receives the latest
        session-resumption handle under "handle".
        """
        resume_state = resume_state if resume_state is not None else {}
        live_config = self._build_live_config(
            with_tools=on_tool_call is not None,
            resume_handle=resume_state.get("handle"),
        )
        logger.info(f"Connecting to Gemini Live: model={config.GEMINI_LIVE_MODEL}")

        async with self._client.aio.live.connect(
            model=config.GEMINI_LIVE_MODEL,
            config=live_config,
        ) as session:
            logger.info("Gemini Live session established.")
            aria_session.state = SessionState.LISTENING
            if on_state_change:
                await on_state_change(SessionState.LISTENING)

            tool_tasks: dict[str, asyncio.Task] = {}

            async def _send_audio():
                """Forward raw audio to Gemini Live — it handles VAD, transcription, and response."""
                async for chunk in audio_input_stream:
                    try:
                        await session.send_realtime_input(
                            audio=types.Blob(
                                mime_type="audio/pcm;rate=16000",
                                data=chunk,
                            )
                        )
                    except Exception as e:
                        logger.error(f"Audio send error: {e}")
                        return

            async def _run_tool(fc: types.FunctionCall):
                try:
                    result = await on_tool_call(fc.name, dict(fc.args or {}))
                except asyncio.CancelledError:
                    return  # Live cancelled the call itself: no response expected
                except Exception as e:
                    logger.error(f"Tool {fc.name} failed: {e}", exc_info=True)
                    result = {"status": "error", "error": str(e)}
                finally:
                    tool_tasks.pop(fc.id, None)
                try:
                    await session.send_tool_response(function_responses=[
                        types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                    ])
                except Exception as e:
                    logger.warning(f"Could not send tool response: {e}")

            async def _receive():
                # Buffer to accumulate input transcription fragments
                input_buf: list[str] = []
                # Buffer for ARIA's own spoken transcript (sent cumulatively)
                output_buf: list[str] = []

                async def _flush_user_speech():
                    full_text = "".join(input_buf).strip()
                    input_buf.clear()
                    if full_text:
                        logger.info(f"User said (complete): {full_text!r}")
                        if on_user_speech:
                            await on_user_speech(full_text)

                async def _flush_aria_speech():
                    if output_buf and on_text:
                        await on_text("".join(output_buf).strip(), final=True)
                    output_buf.clear()

                # receive() ends after each turn_complete: loop to keep the
                # conversation going for the whole session.
                while True:
                    got_any = False
                    async for response in session.receive():
                        got_any = True

                        if response.session_resumption_update:
                            update = response.session_resumption_update
                            if update.resumable and update.new_handle:
                                resume_state["handle"] = update.new_handle

                        if response.go_away:
                            logger.info(f"Gemini Live will close soon (time left: {response.go_away.time_left}).")

                        if response.tool_call:
                            # The user's request is complete once the model acts on it
                            await _flush_user_speech()
                            await _flush_aria_speech()
                            for fc in response.tool_call.function_calls or []:
                                if on_tool_call:
                                    tool_tasks[fc.id] = asyncio.create_task(_run_tool(fc))

                        if response.tool_call_cancellation:
                            ids = list(response.tool_call_cancellation.ids or [])
                            for call_id in ids:
                                task = tool_tasks.pop(call_id, None)
                                if task:
                                    task.cancel()
                            if on_tool_cancel and ids:
                                await on_tool_cancel(ids)

                        sc = response.server_content
                        if not sc:
                            continue

                        if sc.interrupted:
                            # User barged in while ARIA was speaking: tell the client to
                            # drop queued audio. Keep the user's transcription buffer —
                            # it holds what they are saying right now.
                            await _flush_aria_speech()
                            if on_state_change:
                                await on_state_change(SessionState.INTERRUPTED)
                            continue

                        # ARIA starts answering => the user has finished speaking
                        if input_buf and (sc.model_turn or sc.output_transcription):
                            await _flush_user_speech()

                        # Audio response from ARIA
                        if sc.model_turn:
                            for part in (sc.model_turn.parts or []):
                                if part.inline_data and on_audio:
                                    await on_audio(part.inline_data.data)

                        # What ARIA said (text transcript of audio response)
                        if sc.output_transcription and sc.output_transcription.text:
                            output_buf.append(sc.output_transcription.text)
                            if on_text:
                                await on_text("".join(output_buf), final=False)

                        # What user said — accumulate fragments
                        if sc.input_transcription and sc.input_transcription.text:
                            input_buf.append(sc.input_transcription.text)

                        if sc.turn_complete:
                            await _flush_aria_speech()
                            await _flush_user_speech()

                    if not got_any:
                        logger.info("Gemini Live stream closed.")
                        return

            # Whichever side ends first (stream closed, mic stream ended) ends the
            # connection; gather() would wait forever on the idle audio sender.
            tasks = [asyncio.create_task(_send_audio()), asyncio.create_task(_receive())]
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    t.result()  # surface errors
            finally:
                for t in tasks + list(tool_tasks.values()):
                    t.cancel()

    async def send_text_turn(
        self,
        message: str,
        screenshot_bytes: bytes | None = None,
    ) -> str:
        parts: list[types.Part] = []
        if screenshot_bytes:
            parts.append(
                types.Part(
                    inline_data=types.Blob(mime_type="image/jpeg", data=screenshot_bytes)
                )
            )
        parts.append(types.Part(text=message))

        response = await self._client.aio.models.generate_content(
            model=config.GEMINI_VISION_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=ARIA_SYSTEM_PROMPT,
                temperature=0.2,
            ),
        )
        return response.text


gemini_live_service = GeminiLiveService()
