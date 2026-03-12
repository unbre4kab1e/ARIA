import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from config import config


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

    def touch(self):
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > config.SESSION_TTL_SECONDS

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
        async with self._lock:
            # Evict expired sessions
            expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
            for sid in expired:
                del self._sessions[sid]

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
            self._sessions.pop(session_id, None)

    def active_count(self) -> int:
        return len([s for s in self._sessions.values() if not s.is_expired()])


session_manager = SessionManager()
