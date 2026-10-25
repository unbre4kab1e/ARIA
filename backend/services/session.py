import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from config import config

logger = logging.getLogger("aria.session")


class SessionState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    ACTING = "acting"
    INTERRUPTED = "interrupted"


@dataclass
class ARIASession:
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    state: SessionState = SessionState.IDLE
    current_task: str | None = None
    task_history: list[dict[str, Any]] = field(default_factory=list)
    browser_context_id: str | None = None
    interrupted: bool = False
    # Agent runner (ADK memory + browser context). Owned by the session, not by
    # the WebSocket, so a network blip and reconnect doesn't lose either.
    runner: Any = None
    connections: int = 0
    disconnected_at: float | None = None

    async def close(self):
        if self.runner is not None:
            try:
                await self.runner.stop()
            except Exception as e:
                logger.warning(f"Runner stop failed for {self.session_id}: {e}")
            self.runner = None

    def touch(self):
        self.last_active = time.time()

    def is_expired(self) -> bool:
        now = time.time()
        if (now - self.last_active) > config.SESSION_TTL_SECONDS:
            return True
        # Client left and did not come back within the grace period
        return (
            self.connections == 0
            and self.disconnected_at is not None
            and (now - self.disconnected_at) > config.RECONNECT_GRACE_SECONDS
        )

    def mark_connected(self):
        self.connections += 1
        self.disconnected_at = None
        self.touch()

    def mark_disconnected(self):
        self.connections = max(0, self.connections - 1)
        if self.connections == 0:
            self.disconnected_at = time.time()

    def interrupt(self):
        self.interrupted = True
        self.state = SessionState.INTERRUPTED

    def resume(self):
        self.interrupted = False
        self.state = SessionState.LISTENING

    def add_to_history(self, role: str, content: str, metadata: dict | None = None):
        self.task_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, ARIASession] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> ARIASession:
        await self.cleanup_expired()
        async with self._lock:
            if len(self._sessions) >= config.MAX_SESSIONS:
                raise RuntimeError(
                    f"Max concurrent sessions ({config.MAX_SESSIONS}) reached."
                )

            session = ARIASession(session_id=str(uuid.uuid4()))
            self._sessions[session.session_id] = session
            return session

    async def get(self, session_id: str) -> ARIASession | None:
        session = self._sessions.get(session_id)
        if session and not session.is_expired():
            session.touch()
            return session
        return None

    async def delete(self, session_id: str):
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            await session.close()

    async def cleanup_expired(self) -> int:
        """Drop expired sessions and free their browser contexts."""
        async with self._lock:
            expired = [s for s in self._sessions.values() if s.is_expired()]
            for s in expired:
                del self._sessions[s.session_id]
        for s in expired:
            await s.close()
        return len(expired)

    async def close_all(self):
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for s in sessions:
            await s.close()

    def active_count(self) -> int:
        return len([s for s in self._sessions.values() if not s.is_expired()])


session_manager = SessionManager()
