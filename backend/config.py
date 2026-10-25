import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_CLOUD_REGION: str = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

    # Gemini Models
    GEMINI_LIVE_MODEL: str = os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")
    GEMINI_AGENT_MODEL: str = os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash-lite")
    GEMINI_VISION_MODEL: str = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash-lite")

    # App
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    # Shared secret required on /api/* and /ws/* when set (empty = open access)
    ACCESS_TOKEN: str = os.getenv("ACCESS_TOKEN", "")
    # Comma-separated list of allowed origins, "*" for any
    CORS_ORIGINS: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

    # Session
    SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", 3600))
    MAX_SESSIONS: int = int(os.getenv("MAX_SESSIONS", 10))
    # How long a session's browser and agent memory wait for a WebSocket reconnect
    RECONNECT_GRACE_SECONDS: int = int(os.getenv("RECONNECT_GRACE_SECONDS", 120))

    # Screenshot
    SCREENSHOT_INTERVAL_MS: int = int(os.getenv("SCREENSHOT_INTERVAL_MS", 2000))
    MAX_IMAGE_SIZE_PX: int = int(os.getenv("MAX_IMAGE_SIZE_PX", 1280))

    # Playwright
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    BROWSER_TIMEOUT_MS: int = int(os.getenv("BROWSER_TIMEOUT_MS", 10000))
    # Allow the agent's browser to reach localhost / private networks (dev only)
    ALLOW_PRIVATE_NETWORK: bool = os.getenv("ALLOW_PRIVATE_NETWORK", "false").lower() == "true"
    # Optional: use an already-installed Chromium instead of Playwright's bundled one
    BROWSER_EXECUTABLE_PATH: str = os.getenv("BROWSER_EXECUTABLE_PATH", "")


config = Config()
