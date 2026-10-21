"""HTTP authentication FastAPI dependencies."""

from typing import Optional

from fastapi import Depends, Header

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.auth.schemas import AuthenticatedUser
from app.core.auth.token_service import verify_access_token
from app.core.time_utils import now_ms

_AUTH_HEADER_PREFIX = "Bearer "


def _parse_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization is None:
        return None
    normalized = str(authorization).strip()
    if not normalized.startswith(_AUTH_HEADER_PREFIX):
        return None
    token = normalized[len(_AUTH_HEADER_PREFIX) :].strip()
    return token or None


def get_authenticated_user(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> AuthenticatedUser:
    """Decode and validate the current Bearer token."""
    token = _parse_bearer_token(authorization)
    if token is None:
        raise BizException(ErrorCode.AUTH_UNAUTHORIZED)
    auth_user = verify_access_token(token)
    if auth_user is None or auth_user.expiresAt <= now_ms():
        raise BizException(ErrorCode.AUTH_UNAUTHORIZED)
    return auth_user


def get_optional_authenticated_user(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> Optional[AuthenticatedUser]:
    token = _parse_bearer_token(authorization)
    if token is None:
        return None
    auth_user = verify_access_token(token)
    if auth_user is None or auth_user.expiresAt <= now_ms():
        return None
    return auth_user


def require_path_user_matches_auth(userId: str, auth_user: AuthenticatedUser = Depends(get_authenticated_user)) -> AuthenticatedUser:
    if str(userId).strip() != auth_user.userId:
        raise BizException(ErrorCode.AUTH_UNAUTHORIZED)
    return auth_user
