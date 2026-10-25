"""Optional shared-secret access control (enabled when ACCESS_TOKEN is set)."""

import secrets

from fastapi import Header, HTTPException, WebSocket

from config import config


def token_is_valid(token: str | None) -> bool:
    if not config.ACCESS_TOKEN:
        return True
    return bool(token) and secrets.compare_digest(token, config.ACCESS_TOKEN)


async def require_token(
    authorization: str | None = Header(default=None),
    x_aria_token: str | None = Header(default=None),
):
    token = x_aria_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token_is_valid(token):
        raise HTTPException(status_code=401, detail="Invalid or missing access token.")


def websocket_token_is_valid(websocket: WebSocket) -> bool:
    # Browsers can't set headers on WebSocket connections: the token comes as ?token=
    return token_is_valid(websocket.query_params.get("token"))
