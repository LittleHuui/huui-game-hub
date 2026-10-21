import json
from typing import List, Set
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError
from app.common.error_code import ErrorCode
from app.common.exceptions import BizException, NotFoundException, ValidationException
from app.core.logging import get_logger
from app.core.database import isolated_write
from app.core.time_utils import now_ms
from app.modules.sync.cloud_save_schemas import CloudSaveSyncRequest
from app.modules.sync.cloud_save_schemas import CloudSaveSyncResponse
from app.modules.sync.cloud_save_schemas import PendingSyncEventRequest
from app.modules.sync.entity_service import SyncLogEntityService
from app.modules.sync.module_service import SyncModuleService, order_cloud_save_events
from app.modules.sync.schemas import PendingEvent
from app.modules.user.models import UserAccount
from app.modules.user.module_service import UserModuleService
from sqlalchemy.orm import Session
from app.modules.sync.cloud_snapshot_service import CloudSnapshotService


logger = get_logger(__name__)

def _to_pending_event(event: PendingSyncEventRequest) -> PendingEvent:
    """
    将启动模块同步事件转为 sync 域 ``PendingEvent``。

    :param event: 启动模块待同步事件。
    :return: sync 域事件模型。
    """
    return PendingEvent(
        clientId=event.clientId,
        eventType=event.eventType,
        createdAt=event.createdAt,
        updatedAt=event.updatedAt,
        payload=event.payload,
    )

class CloudSaveService:
    """逐事件事务执行、批次审计与响应编排。"""

    def __init__(self, session: Session, user_module_service: UserModuleService,
                 sync_module_service: SyncModuleService, sync_log_entity_service: SyncLogEntityService,
                 snapshot_service: CloudSnapshotService) -> None:
        """注入同一请求事务和同步所需服务。"""
        self._session = session
        self._user_module_service = user_module_service
        self._sync_module_service = sync_module_service
        self._sync_log_entity_service = sync_log_entity_service
        self._snapshot_service = snapshot_service

    def _validate_cloud_save_request(self, request: CloudSaveSyncRequest) -> UserAccount:
        """
        校验云存档同步请求（用户存在、批次内 clientId 不重复）。

        :param request: 云存档同步请求。
        :return: 用户账号实体。
        :raises NotFoundException: 用户不存在。
        :raises ValidationException: 事件列表非法。
        """
        user_module = self._user_module_service
        user = user_module.get_user_by_id(request.userId)
        if user is None:
            raise NotFoundException("用户不存在")
        seen_client_ids: Set[str] = set()
        for idx, event in enumerate(request.pendingEvents):
            if event.clientId in seen_client_ids:
                raise ValidationException(f"同一批次内 clientId 重复: index={idx}")
            seen_client_ids.add(event.clientId)
        return user

    def _format_sync_event_error(self, client_id: str, exc: Exception) -> str:
        """
        将单条事件异常格式化为可读错误信息。

        :param client_id: 事件 clientId。
        :param exc: 捕获的异常。
        :return: 错误描述文本。
        """
        if isinstance(exc, BizException):
            return f"{client_id}: {exc.message}"
        if isinstance(exc, json.JSONDecodeError):
            return f"{client_id}: JSON 解析失败"
        if isinstance(exc, PydanticValidationError):
            return f"{client_id}: 数据校验失败"
        if isinstance(exc, SQLAlchemyError):
            return f"{client_id}: 数据库异常"
        return f"{client_id}: {exc}"

    def _append_sync_log(
        self,
        *,
        request: CloudSaveSyncRequest,
        sync_result: str,
        received_count: int,
        success_count: int,
        duplicate_count: int,
        fail_count: int,
        start_time: int,
        finish_time: int,
        error_messages: List[str],
    ) -> None:
        """
        写入云存档同步审计日志（含开始/结束时间与统计）。

        :param request: 云存档请求。
        :param sync_result: 批次结果标签。
        :param received_count: 收到事件数。
        :param success_count: 新写入成功数。
        :param duplicate_count: 幂等重复数。
        :param fail_count: 失败数。
        :param start_time: 同步开始时间（毫秒）。
        :param finish_time: 同步结束时间（毫秒）。
        :param error_messages: 聚合错误列表。
        :return: None
        """
        self._sync_log_entity_service.append_cloud_save(
            user_id=request.userId,
            device_id=request.deviceId,
            sync_result=sync_result,
            pending_count=received_count,
            success_count=success_count,
            fail_count=fail_count,
            duplicate_count=duplicate_count,
            start_time=start_time,
            finish_time=finish_time,
            error_message="; ".join(error_messages) if error_messages else None,
            client_snapshot_version=request.clientSnapshotVersion,
            processed_client_ids=[event.clientId for event in request.pendingEvents],
        )

    async def sync_cloud_save(
        self,
        request: CloudSaveSyncRequest,
    ) -> CloudSaveSyncResponse:
        """云存档同步：事件分发、派生数据重算、审计日志与完整快照返回。"""
        start_time = now_ms()
        user = self._validate_cloud_save_request(request)

        received_count = len(request.pendingEvents)
        success_count = 0
        duplicate_count = 0
        fail_count = 0
        error_messages: List[str] = []
        sync_result_label = "success"

        try:
            sync_module = self._sync_module_service
            pending_events = [_to_pending_event(event) for event in request.pendingEvents]
            ordered_events = order_cloud_save_events(pending_events)
            for event in ordered_events:
                try:
                    with isolated_write(self._session):
                        result = sync_module.dispatch_cloud_save_event(
                            request.userId,
                            request.deviceId,
                            event,
                        )
                    if result == "duplicate":
                        duplicate_count += 1
                    else:
                        success_count += 1
                except BizException as exc:
                    fail_count += 1
                    message = self._format_sync_event_error(event.clientId, exc)
                    error_messages.append(message)
                    logger.warning("sync event failed clientId=%s message=%s", event.clientId, exc.message)
                except (json.JSONDecodeError, PydanticValidationError) as exc:
                    fail_count += 1
                    error_messages.append(self._format_sync_event_error(event.clientId, exc))
                    logger.warning("sync event parse failed clientId=%s", event.clientId)
                except SQLAlchemyError as exc:
                    fail_count += 1
                    error_messages.append(self._format_sync_event_error(event.clientId, exc))
                    logger.exception("sync event database error clientId=%s", event.clientId)
                except Exception as exc:
                    fail_count += 1
                    error_messages.append(self._format_sync_event_error(event.clientId, exc))
                    logger.exception("sync event unexpected error clientId=%s", event.clientId)

            if fail_count == 0:
                sync_result_label = "success"
            elif success_count > 0 or duplicate_count > 0:
                sync_result_label = "partial"
            else:
                sync_result_label = "failed"

            server_time = now_ms()
            return self._snapshot_service.build_cloud_save_response(
                request=request,
                user=user,
                server_time=server_time,
                received_count=received_count,
                success_count=success_count,
                duplicate_count=duplicate_count,
                fail_count=fail_count,
            )
        except BizException:
            sync_result_label = "failed"
            raise
        except SQLAlchemyError as exc:
            sync_result_label = "failed"
            logger.exception("云存档同步数据库异常 userId=%s", request.userId)
            raise BizException(ErrorCode.SYSTEM_ERROR, message="数据库异常") from exc
        except Exception as exc:
            sync_result_label = "failed"
            logger.exception("云存档同步未预期异常 userId=%s", request.userId)
            raise BizException(ErrorCode.SYSTEM_ERROR, message="服务器内部错误") from exc
        finally:
            finish_time = now_ms()
            self._append_sync_log(
                request=request,
                sync_result=sync_result_label,
                received_count=received_count,
                success_count=success_count,
                duplicate_count=duplicate_count,
                fail_count=fail_count,
                start_time=start_time,
                finish_time=finish_time,
                error_messages=error_messages,
            )
