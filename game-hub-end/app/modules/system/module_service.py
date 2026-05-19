"""系统域模块级编排服务。"""

from typing import List, Optional

from app.core.exceptions import ValidationException
from app.modules.system.entity_service import (
    LoginLogEntityService,
    RequestLogEntityService,
    SystemConfigEntityService,
)
from app.modules.system.models import LoginLog, RequestLog, SystemConfig
from app.modules.system.schemas import SystemConfigUpsert


class SystemModuleService:
    """系统模块对外业务能力：配置管理与审计日志写入。"""

    def __init__(
        self,
        config_entity: SystemConfigEntityService,
        request_log_entity: RequestLogEntityService,
        login_log_entity: LoginLogEntityService,
    ) -> None:
        self._configs = config_entity
        self._request_logs = request_log_entity
        self._login_logs = login_log_entity

    def list_configs(self) -> List[SystemConfig]:
        """
        列出全部未软删的系统配置。

        :return: 配置列表。
        """
        return self._configs.list_configs(active_only=True)

    def upsert_config(self, config_key: str, body: SystemConfigUpsert) -> SystemConfig:
        """
        按 config_key 创建或更新系统配置。

        :param config_key: 路径中的唯一配置键。
        :param body: 更新载荷。
        :return: 持久化后的配置。
        """
        if not config_key or not config_key.strip():
            raise ValidationException("config_key 不能为空")
        enabled = 1
        if body.enabled is not None:
            if body.enabled not in (0, 1):
                raise ValidationException("enabled 必须为 0 或 1")
            enabled = int(body.enabled)
        return self._configs.upsert_by_config_key(
            config_key.strip(),
            config_value=body.configValue,
            description=body.description,
            enabled=enabled,
        )

    def record_request_log(
        self,
        *,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        query_string: Optional[str] = None,
        status_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> RequestLog:
        """
        写入请求审计日志（供中间件或其它模块调用）。

        :return: 新日志实体。
        """
        return self._request_logs.append(
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
        )

    def record_login_log(
        self,
        *,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        login_type: Optional[str] = None,
        login_result: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> LoginLog:
        """
        写入登录审计日志。

        :return: 新日志实体。
        """
        return self._login_logs.append(
            user_id=user_id,
            device_id=device_id,
            login_type=login_type,
            login_result=login_result,
            ip=ip,
            user_agent=user_agent,
            payload_json=payload_json,
        )
