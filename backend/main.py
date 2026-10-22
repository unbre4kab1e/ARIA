import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn

# Windows requires ProactorEventLoop to support subprocesses (Playwright)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from agents.tools.browser_tools import browser_controller
from api.routes import public_router, router
from api.websocket import handle_websocket
from config import config
from services.session import session_manager
from services.startup_check import check_gemini

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Keep ARIA's own loggers at DEBUG for diagnostics
logging.getLogger("aria").setLevel(logging.DEBUG)
logger = logging.getLogger("aria")


async def _cleanup_loop():
    """Free browser contexts of sessions nobody came back to."""
    while True:
        await asyncio.sleep(60)
        try:
            evicted = await session_manager.cleanup_expired()
            if evicted:
                logger.info(f"Evicted {evicted} expired session(s).")
        except Exception as e:
            logger.warning(f"Session cleanup failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ARIA backend...")
    if not config.ACCESS_TOKEN:
        logger.warning("ACCESS_TOKEN is not set — anyone reaching this server can use it.")
    check_task = asyncio.create_task(check_gemini())
    cleanup_task = asyncio.create_task(_cleanup_loop())
    await browser_controller.start()
    yield
    logger.info("Shutting down ARIA backend...")
    check_task.cancel()
    cleanup_task.cancel()
    await session_manager.close_all()
    await browser_controller.stop()
    logger.info("Playwright browser stopped.")


app = FastAPI(
    title="ARIA — Adaptive Reality Intelligence Assistant",
    description="Backend for the ARIA multimodal AI agent (Gemini Live + Vision + Browser Control)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)
app.include_router(router)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await handle_websocket(websocket, session_id)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="debug" if config.DEBUG else "info",
    )
