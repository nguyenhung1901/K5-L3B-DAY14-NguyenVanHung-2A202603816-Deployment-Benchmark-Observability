"""Protect the Agent endpoint with a configured API key."""
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """Return the authenticated key or reject the request with HTTP 401."""
    expected = settings.agent_api_key
    if not api_key or not expected or not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key
