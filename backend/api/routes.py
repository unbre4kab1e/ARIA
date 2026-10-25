from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.tools.browser_tools import browser_controller
from api.auth import require_token
from config import config
from services.gemini_live import gemini_live_service
from services.session import session_manager
from services.startup_check import gemini_status
from services.vision import vision_service

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])
public_router = APIRouter(prefix="/api")


# ─── Session ──────────────────────────────────────────────────────────────────

@router.post("/sessions")
async def create_session():
    """Create a new ARIA session. Returns session_id to use with WebSocket."""
    try:
        session = await session_manager.create()
        return {"session_id": session.session_id, "state": session.state.value}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = await session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "session_id": session.session_id,
        "state": session.state.value,
        "current_task": session.current_task,
        "history_count": len(session.task_history),
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    await session_manager.delete(session_id)
    return {"deleted": session_id}


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str):
    session = await session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"history": session.task_history}


# ─── One-shot Vision ──────────────────────────────────────────────────────────

class AnalyzeScreenRequest(BaseModel):
    screenshot_b64: str
    user_intent: str = ""


@router.post("/vision/analyze")
async def analyze_screen(req: AnalyzeScreenRequest):
    """Analyze a screenshot with Gemini Vision. No live session required."""
    import base64
    try:
        png_bytes = base64.b64decode(req.screenshot_b64)
        result = await vision_service.analyze_screen(png_bytes, req.user_intent or None)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DescribeElementRequest(BaseModel):
    screenshot_b64: str
    x: int
    y: int


@router.post("/vision/describe-element")
async def describe_element(req: DescribeElementRequest):
    """Describe the UI element at (x, y) in the screenshot."""
    import base64
    try:
        png_bytes = base64.b64decode(req.screenshot_b64)
        description = await vision_service.describe_element(png_bytes, req.x, req.y)
        return {"description": description}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── One-shot Text Query ──────────────────────────────────────────────────────

class TextQueryRequest(BaseModel):
    message: str
    screenshot_b64: str | None = None


@router.post("/query")
async def text_query(req: TextQueryRequest):
    """Send a text (+ optional screenshot) message to ARIA without a live session."""
    import base64
    screenshot_bytes = None
    if req.screenshot_b64:
        screenshot_bytes = base64.b64decode(req.screenshot_b64)
    try:
        response = await gemini_live_service.send_text_turn(req.message, screenshot_bytes)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Health ───────────────────────────────────────────────────────────────────

@public_router.get("/health")
async def health():
    return {
        "status": "ok",
        "active_sessions": session_manager.active_count(),
        "auth_required": bool(config.ACCESS_TOKEN),
        "gemini_configured": bool(config.GOOGLE_API_KEY),
        "gemini_status": gemini_status["status"],
        "browser_ready": browser_controller.ready,
        "browser_error": browser_controller.last_error,
    }
