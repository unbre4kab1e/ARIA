"""Background check that the Gemini key and model names actually work."""

import asyncio
import logging

from google import genai

from config import config

logger = logging.getLogger("aria.check")

# "pending" until the check finishes, then "ok" or a human-readable problem
gemini_status: dict[str, str] = {"status": "pending"}


async def check_gemini():
    if not config.GOOGLE_API_KEY:
        gemini_status["status"] = "GOOGLE_API_KEY is not set"
        logger.warning("GOOGLE_API_KEY is not set — Gemini calls will fail. See backend/.env.example.")
        return

    client = genai.Client(api_key=config.GOOGLE_API_KEY)
    # model -> env var naming it (agent and vision often share a model: check once)
    models: dict[str, str] = {}
    for env_name, model in (
        ("GEMINI_AGENT_MODEL", config.GEMINI_AGENT_MODEL),
        ("GEMINI_VISION_MODEL", config.GEMINI_VISION_MODEL),
        ("GEMINI_LIVE_MODEL", config.GEMINI_LIVE_MODEL),
    ):
        models.setdefault(model, env_name)
    problems: list[str] = []
    for model, env_name in models.items():
        try:
            await asyncio.wait_for(client.aio.models.get(model=model), timeout=15)
        except Exception as e:
            text = str(e)
            if "API_KEY_INVALID" in text or "API key not valid" in text or "PERMISSION_DENIED" in text:
                problems = ["GOOGLE_API_KEY is invalid or not allowed to use the Gemini API"]
                break
            if "404" in text or "NOT_FOUND" in text:
                problems.append(f"{env_name}={model} does not exist")
            else:
                problems.append(f"could not reach Gemini ({type(e).__name__}: {text[:120]})")
                break

    gemini_status["status"] = "ok" if not problems else "; ".join(problems)
    if problems:
        logger.error(f"Gemini check failed: {gemini_status['status']}")
    else:
        logger.info("Gemini check passed: key and models are valid.")
