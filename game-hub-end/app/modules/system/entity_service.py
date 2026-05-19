"""系统域单实体服务。"""

from typing import List, Optional

from app.core.database import new_entity_ids
from app.core.exceptions import NotFoundException, ValidationException
from app.modules.system.models import LoginLog, RequestLog, SystemConfig
from app.modules.system.repository import (
    LoginLogRepository,
    RequestLogRepository,
    SystemConfigRepository,
)


class SystemConfigEntityService:
    """系统配置实体：查询、创建、更新。"""

    def __init__(self, repository: SystemConfigRepository) -> None:
        self._repository = repository

    def list_configs(self, *, active_only: bool = True) -> List[SystemConfig]:
        """
        列出全部系统配置。

        :param active_only: 是否只含未软删行。
        :return: 配置列表。
        """
        return self._repository.list_all(active_only=active_only)

    def get_by_config_key(self, config_key: str, *, active_only: bool = True) -> Optional[SystemConfig]:
        """
        按配置键读取。

        :param config_key: 唯一配置键。
        :param active_only: 是否只查未软删行。
        :return: 配置实体或 ``None``。
        """
        return self._repository.get_by_config_key(config_key, active_only=active_only)

    def require_by_config_key(self, config_key: str) -> SystemConfig:
        """
        按配置键读取，不存在则抛出 NotFoundException。

        :param config_key: 唯一配置键。
        :return: 配置实体。
        """
        entity = self._repository.get_by_config_key(config_key)
        if entity is None:
            raise NotFoundException("系统配置不存在")
        return entity

    def upsert_by_config_key(
        self,
        config_key: str,
        *,
        config_value: Optional[str],
        description: Optional[str],
        enabled: int,
    ) -> SystemConfig:
        """
        按 config_key 创建或更新配置；若唯一键被软删行占用则复活该行。

        :param config_key: 唯一配置键。
        :param config_value: 配置值，可空。
        :param description: 说明，可空。
        :param enabled: 0 禁用，1 启用。
        :return: 持久化后的配置。
        """
        active = self._repository.get_by_config_key(config_key, active_only=True)
        if active is not None:
            active.config_value = config_value
            active.description = description
            active.enabled = enabled
            return self._repository.save(active)
        tomb = self._repository.get_any_by_config_key(config_key)
        if tomb is not None and tomb.deleted_at is not None:
            tomb.deleted_at = None
            tomb.config_value = config_value
            tomb.description = description
            tomb.enabled = enabled
            return self._repository.save(tomb)
        server_id, created_at, updated_at = new_entity_ids("system_config")
        entity = SystemConfig(
            server_id=server_id,
            config_key=config_key,
            config_value=config_value,
            description=description,
            enabled=enabled,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)


class RequestLogEntityService:
    """请求日志实体：追加写入。"""

    def __init__(self, repository: RequestLogRepository) -> None:
        self._repository = repository

    def append(
        self,
        *,
        request_id: Optional[str],
        user_id: Optional[str],
        device_id: Optional[str],
        method: Optional[str],
        path: Optional[str],
        query_string: Optional[str],
        status_code: Optional[int],
        duration_ms: Optional[int],
        ip: Optional[str],
        user_agent: Optional[str],
        payload_json: Optional[str],
    ) -> RequestLog:
        """
        追加一条请求日志。

        :return: 新日志实体。
        """
        server_id, created_at, updated_at = new_entity_ids("request_log")
        entity = RequestLog(
            server_id=server_id,
            request_id=request_id,
            user_id=user_id,
            device_id=device_id,
            method=method,
            path=path,
            query_string=query_string,
            status_code=status_code,
            duration_ms=duration_ms,
            ip=ip,
            user_agent=user_agent,
            payload_json=payload_json,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)


class LoginLogEntityService:
    """登录日志实体：追加写入。"""

    def __init__(self, repository: LoginLogRepository) -> None:
        self._repository = repository

    def append(
        self,
        *,
        user_id: Optional[str],
        device_id: Optional[str],
        login_type: Optional[str],
        login_result: Optional[str],
        ip: Optional[str],
        user_agent: Optional[str],
        payload_json: Optional[str],
    ) -> LoginLog:
        """
        追加一条登录日志。

        :return: 新日志实体。
        """
        server_id, created_at, updated_at = new_entity_ids("login_log")
        entity = LoginLog(
            server_id=server_id,
            user_id=user_id,
            device_id=device_id,
            login_type=login_type,
            login_result=login_result,
            ip=ip,
            user_agent=user_agent,
            payload_json=payload_json,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)

