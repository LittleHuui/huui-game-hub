"""成绩域单实体服务。"""

from typing import List, Optional, Tuple

from app.core.database import new_entity_ids
from app.core.time_utils import now_ms
from app.modules.match.schemas import ScoreRecordCreate, object_to_json_text
from app.modules.score.models import ScoreRecord
from app.modules.score.repository import ScoreRecordRepository


class ScoreRecordEntityService:
    """成绩记录实体的基础校验与 CRUD。"""

    def __init__(self, repository: ScoreRecordRepository) -> None:
        self._repository = repository

    def list_by_user(self, user_id: str, limit: int = 200) -> List[ScoreRecord]:
        """
        列出用户成绩记录。

        :param user_id: 用户主键。
        :param limit: 返回条数上限。
        :return: 成绩列表。
        """
        return self._repository.list_by_user(user_id, limit)

    def exists_by_user_and_client_id(self, user_id: str, client_id: str) -> bool:
        """
        判断成绩记录是否已存在。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 已存在为 True。
        """
        existing = self._repository.get_by_user_and_client_id(user_id, client_id, active_only=True)
        return existing is not None

    def create_score_record_if_not_exists(self, payload: ScoreRecordCreate) -> Tuple[ScoreRecord, bool]:
        """
        按 ``user_id + client_id`` 幂等写入成绩记录。

        :param payload: 创建请求体。
        :return: ``(成绩记录, 是否新创建)``。
        """
        active = self._repository.get_by_user_and_client_id(payload.userId, payload.clientId, active_only=True)
        if active is not None:
            return active, False
        tomb = self._repository.get_any_by_user_and_client_id(payload.userId, payload.clientId)
        if tomb is not None and tomb.deleted_at is not None:
            tomb.deleted_at = None
            tomb.client_id = payload.clientId
            tomb.user_id = payload.userId
            tomb.device_id = payload.deviceId
            tomb.game_code = payload.gameCode
            tomb.mode = payload.mode
            tomb.difficulty_code = payload.difficultyCode
            tomb.result = payload.result
            tomb.score = payload.score
            tomb.duration_ms = payload.durationMs
            tomb.payload_json = object_to_json_text(payload.payload)
            tomb.synced_at = now_ms()
            return self._repository.save(tomb), True
        synced_at = now_ms()
        server_id, created_at, updated_at = new_entity_ids("score_record")
        entity = ScoreRecord(
            server_id=server_id,
            client_id=payload.clientId,
            user_id=payload.userId,
            device_id=payload.deviceId,
            game_code=payload.gameCode,
            mode=payload.mode,
            difficulty_code=payload.difficultyCode,
            result=payload.result,
            score=payload.score,
            duration_ms=payload.durationMs,
            payload_json=object_to_json_text(payload.payload),
            synced_at=synced_at,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity), True
