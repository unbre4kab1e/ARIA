import io
import json
import logging
from typing import Any

from google import genai
from google.genai import types
from PIL import Image

from config import config

logger = logging.getLogger("aria.vision")


class VisionService:
    """
    Sends screenshots to Gemini Vision for UI understanding.
    Returns structured analysis: elements, intent, suggested actions.
    """

    def __init__(self):
        self._client = genai.Client(api_key=config.GOOGLE_API_KEY)

    def _resize_image(self, image_bytes: bytes) -> bytes:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Ensure image is RGB before saving as JPEG (prevents crash if Alpha channel exists)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        max_px = config.MAX_IMAGE_SIZE_PX
        if max(img.size) > max_px:
            ratio = max_px / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80) # Save as JPEG
        return buf.getvalue()

    async def analyze_screen(
        self,
        screenshot_bytes: bytes,
        user_intent: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze a screenshot and return structured UI understanding.
        """
        resized = self._resize_image(screenshot_bytes)

        intent_context = (
            f"The user wants to: {user_intent}" if user_intent else "General screen analysis."
        )

        prompt = f"""You are ARIA, an AI agent analyzing a computer screen to help a user.

{intent_context}

Analyze the screenshot and respond with a JSON object containing:
{{
  "page_description": "Brief description of what's on screen",
  "interactive_elements": [
    {{"type": "button|input|link|dropdown|...", "label": "...", "position": "top-left|center|...", "action": "click|type|scroll|..."}}
  ],
  "current_state": "What the user is currently doing / what page/app is visible",
  "suggested_next_actions": ["action1", "action2"],
  "can_fulfill_intent": true|false,
  "fulfillment_plan": ["step1", "step2", "step3"]
}}

Respond ONLY with valid JSON."""

        try:
            response = await self._client.aio.models.generate_content(
                model=config.GEMINI_VISION_MODEL,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                inline_data=types.Blob(mime_type="image/jpeg", data=resized)
                            ),
                            types.Part(text=prompt),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {"raw": response.text, "error": "Failed to parse structured response"}
        except Exception as e:
            logger.error(f"Vision analyze_screen failed: {e}")
            return {"error": str(e)}

    async def describe_element(
        self,
        screenshot_bytes: bytes,
        x: int,
        y: int,
    ) -> str:
        """
        Describe a specific UI element at (x, y) coordinates.
        """
        resized = self._resize_image(screenshot_bytes)

        prompt = (
            f"The user is pointing at the UI element near coordinates ({x}, {y}) on screen. "
            "Describe what that element is, what it does, and how to interact with it. "
            "Be concise and conversational — you are speaking to the user."
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=config.GEMINI_VISION_MODEL,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                inline_data=types.Blob(mime_type="image/jpeg", data=resized)
                            ),
                            types.Part(text=prompt),
                        ],
                    )
                ],
            )
            return response.text
        except Exception as e:
            logger.error(f"Vision describe_element failed: {e}")
            return f"Error analyzing element: {e}"


vision_service = VisionService()
