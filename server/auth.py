"""
server/auth.py — Google OAuth token verification and JWT cookie management.

Auth flow:
  Google Sign-In (frontend) → POST /api/auth/google { id_token }
  → verify with google-auth → create/find user in SQLite
  → set httpOnly JWT cookie → frontend redirects to dashboard
"""

import logging
import os

import jwt
from fastapi import HTTPException, Request
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token

from .db import get_user_by_id

logger = logging.getLogger("leerio.auth")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
COOKIE_NAME = "leerio_token"
COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days
IS_DEV = os.environ.get("LEERIO_DEV", "") == "1"


def verify_google_token(token: str) -> dict:
    """Verify Google ID token and return user info."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "GOOGLE_CLIENT_ID not configured")
    try:
        idinfo = google_id_token.verify_oauth2_token(token, GoogleRequest(), GOOGLE_CLIENT_ID)
        return {
            "email": idinfo["email"],
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture", ""),
        }
    except ValueError as e:
        logger.warning("Google token verification failed: %s", e)
        raise HTTPException(401, "Invalid Google token")


def create_jwt(user_id: str) -> str:
    """Create a JWT token for the user."""
    return jwt.encode({"sub": user_id}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> str | None:
    """Decode JWT and return user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract user from JWT cookie. Raises 401 if not authenticated."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not authenticated")
    user_id = decode_jwt(token)
    if not user_id:
        raise HTTPException(401, "Invalid token")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return user


def require_admin(user: dict) -> dict:
    """Check that user has admin role. Raises 403 if not."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return user


def set_auth_cookie(response, user_id: str):
    """Set the JWT cookie on a response."""
    token = create_jwt(user_id)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=not IS_DEV,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response):
    """Clear the JWT cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
