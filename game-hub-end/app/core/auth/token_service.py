"""JWT HS256 access-token encoding and decoding."""

import logging
import uuid
from typing import Optional

import jwt

from app.core.auth.schemas import AccessTokenPayload, AuthenticatedUser
from app.core.config import settings
from app.core.time_utils import now_ms

logger = logging.getLogger(__name__)

_TOKEN_ALGORITHM = "HS256"


def _require_secret() -> str:
    secret = settings.AUTH_JWT_SECRET
    if secret is None or not str(secret).strip():
        raise RuntimeError("AUTH_JWT_SECRET is not configured")
    return str(secret).strip()


def issue_access_token(user_id: str, device_id: str) -> AccessTokenPayload:
    """Issue a short-lived token for a username + deviceId login."""
    secret = _require_secret()
    issued_at = now_ms()
    expires_at = issued_at + settings.AUTH_ACCESS_TOKEN_EXPIRE_SECONDS * 1000
    token_id = "tok_{0}".format(uuid.uuid4().hex)
    payload = {
        "sub": user_id,
        "deviceId": device_id,
        "jti": token_id,
        "iat": issued_at // 1000,
        "exp": expires_at // 1000,
    }
    token = jwt.encode(payload, secret, algorithm=_TOKEN_ALGORITHM)
    return AccessTokenPayload(accessToken=token, expiresAt=expires_at, tokenId=token_id)


def verify_access_token(token: str) -> Optional[AuthenticatedUser]:
    """Validate token signature and expiry, returning the authenticated user."""
    normalized = str(token or "").strip()
    if not normalized:
        return None
    secret = _require_secret()
    try:
        payload = jwt.decode(
            normalized,
            secret,
            algorithms=[_TOKEN_ALGORITHM],
            options={"require": ["sub", "jti", "exp", "iat", "deviceId"]},
        )
    except jwt.PyJWTError as exc:
        logger.info("access token rejected, reason=%s token_prefix=%s", exc.__class__.__name__, _token_log_prefix(normalized))
        return None
    user_id = str(payload.get("sub") or "").strip()
    device_id = str(payload.get("deviceId") or "").strip()
    token_id = str(payload.get("jti") or "").strip()
    if not user_id or not device_id or not token_id:
        logger.info("access token rejected, reason=missing_claims token_prefix=%s", _token_log_prefix(normalized))
        return None
    return AuthenticatedUser(
        userId=user_id,
        serviceId=user_id,
        deviceId=device_id,
        tokenId=token_id,
        issuedAt=int(payload.get("iat", 0)) * 1000,
        expiresAt=int(payload.get("exp", 0)) * 1000,
    )


def _token_log_prefix(token: str) -> str:
    if len(token) <= 8:
        return "***"
    return "{0}...".format(token[:8])
