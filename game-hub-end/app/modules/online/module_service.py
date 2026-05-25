"""在线/临时态模块业务编排。"""

from typing import Any, Dict, Optional

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.config import settings
from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.core.time_utils import now_ms
from app.modules.online.schemas import OnlineStatusRequest, OnlineUserResponse, OnlineUsersResponse
from app.modules.user.models import UserAccount


class OnlineModuleService(object):
    """在线/临时态业务服务。"""

    def __init__(self, redis: RedisClient = redis_client) -> None:
        """
        初始化在线业务服务。

        :param redis: Redis 工具。
        """
        self._redis = redis

    async def list_online_users(self) -> OnlineUsersResponse:
        """
        查询当前在线用户列表。

        :return: 在线用户列表。
        """
        keys = await self._redis.scan_keys(RedisKeys.user_online_pattern())
        values = await self._redis.mget_json(keys)
        users = []
        for value in values:
            user = self._to_online_user(value)
            if user is not None:
                users.append(user)
        users.sort(key=lambda item: item.lastActiveAt, reverse=True)
        return OnlineUsersResponse(users=users)

    async def update_status(
        self,
        account: UserAccount,
        request: OnlineStatusRequest,
    ) -> OnlineUserResponse:
        """
        更新当前用户在线状态。

        :param account: 当前用户账号。
        :param request: 在线状态请求。
        :return: 更新后的在线用户状态。
        """
        key = RedisKeys.user_online(account.server_id)
        if request.status == "offline":
            current_time = now_ms()
            await self._redis.delete(key)
            return self._build_user_response(account, request.status, current_time, current_time)
        current_time = now_ms()
        existing = await self._redis.get_json(key)
        online_at = self._resolve_online_at(existing, current_time)
        user = self._build_user_response(account, request.status, online_at, current_time)
        ok = await self._redis.set_json(
            key,
            user.model_dump(),
            settings.REDIS_ONLINE_USER_EXPIRE_SECONDS,
        )
        if not ok:
            raise BizException(ErrorCode.SYSTEM_ERROR, message="在线状态写入失败")
        return user

    def _to_online_user(self, value: Any) -> Optional[OnlineUserResponse]:
        """
        将 Redis JSON 对象转为在线用户响应。

        :param value: Redis 中的 JSON 对象。
        :return: 在线用户响应；非法对象返回 ``None``。
        """
        if not isinstance(value, dict):
            return None
        try:
            return OnlineUserResponse.model_validate(value)
        except ValueError:
            return None

    def _resolve_online_at(self, value: Any, current_time: int) -> int:
        """
        解析本次在线会话首次上线时间。

        :param value: Redis 中已有在线用户 JSON 对象。
        :param current_time: 当前服务端毫秒时间戳。
        :return: 首次上线时间；旧值缺失时返回当前时间。
        """
        if not isinstance(value, dict):
            return current_time
        online_at = value.get("onlineAt")
        if isinstance(online_at, int) and online_at > 0:
            return online_at
        return current_time

    def _build_user_response(
        self,
        account: UserAccount,
        status: str,
        online_at: int,
        last_active_at: int,
    ) -> OnlineUserResponse:
        """
        构造在线用户响应。

        :param account: 用户账号。
        :param status: 在线状态。
        :param online_at: 本次在线会话首次上线时间。
        :param last_active_at: 服务端毫秒时间戳。
        :return: 在线用户响应。
        """
        data: Dict[str, Any] = {
            "serviceId": account.server_id,
            "nickname": account.nickname,
            "avatar": account.avatar,
            "status": status,
            "onlineAt": online_at,
            "lastActiveAt": last_active_at,
        }
        return OnlineUserResponse.model_validate(data)
