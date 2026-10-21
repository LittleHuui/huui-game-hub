"""Redis-backed short-lived WebSocket ticket service."""

import json
import secrets
from typing import Optional, Tuple

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.auth.schemas import AuthenticatedUser
from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.core.time_utils import now_ms

_DEFAULT_TTL_SECONDS = 45
_MIN_TTL_SECONDS = 30
_MAX_TTL_SECONDS = 60
_TICKET_RANDOM_BYTES = 32
_MILLISECONDS_PER_SECOND = 1000
_GETDEL_LUA = """
local value = redis.call('GET', KEYS[1])
if value then
  redis.call('DEL', KEYS[1])
end
return value
"""


class RealtimeTicketService:
    """Issue and consume single-use realtime tickets through Redis."""

    def __init__(self, client: RedisClient = redis_client) -> None:
        self._redis = client

    async def issue_realtime_ticket(
        self,
        auth_user: AuthenticatedUser,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> Tuple[str, int]:
        """签发有效期不超过认证凭据剩余时长的单次实时票据。"""
        issued_at = int(auth_user.issuedAt or 0)
        token_expires_at = int(auth_user.expiresAt or 0)
        current_time = now_ms()
        remaining_ms = token_expires_at - current_time
        if remaining_ms < _MILLISECONDS_PER_SECOND:
            raise BizException(ErrorCode.AUTH_UNAUTHORIZED)
        configured_ttl = max(_MIN_TTL_SECONDS, min(int(ttl_seconds), _MAX_TTL_SECONDS))
        ttl = min(configured_ttl, remaining_ms // _MILLISECONDS_PER_SECOND)
        if ttl < 1:
            raise BizException(ErrorCode.AUTH_UNAUTHORIZED)
        ticket = "rt_{0}".format(secrets.token_urlsafe(_TICKET_RANDOM_BYTES))
        expires_at = current_time + ttl * _MILLISECONDS_PER_SECOND
        key = RedisKeys.auth_realtime_ticket(ticket)
        ok = await self._redis.set_json(
            key,
            {
                "userId": auth_user.userId,
                "deviceId": auth_user.deviceId,
                "tokenId": auth_user.tokenId,
                "issuedAt": issued_at,
                "expiresAt": expires_at,
            },
            ttl,
        )
        if not ok:
            raise BizException(ErrorCode.AUTH_UNAUTHORIZED)
        return ticket, expires_at

    async def consume_realtime_ticket(self, ticket: str) -> Optional[AuthenticatedUser]:
        normalized = str(ticket or "").strip()
        if not normalized:
            return None
        key = RedisKeys.auth_realtime_ticket(normalized)
        raw = await self._redis.eval_raw(_GETDEL_LUA, 1, [key], [])
        try:
            record = json.loads(raw) if raw is not None else None
        except (TypeError, ValueError):
            record = None
        if not isinstance(record, dict):
            return None
        expires_at = int(record.get("expiresAt") or 0)
        if expires_at <= now_ms():
            return None
        user_id = str(record.get("userId") or "").strip()
        device_id = str(record.get("deviceId") or "").strip()
        token_id = str(record.get("tokenId") or "").strip()
        issued_at = int(record.get("issuedAt") or 0)
        if not user_id or not device_id or not token_id:
            return None
        return AuthenticatedUser(
            userId=user_id,
            serviceId=user_id,
            deviceId=device_id,
            tokenId=token_id,
            issuedAt=issued_at,
            expiresAt=expires_at,
        )
