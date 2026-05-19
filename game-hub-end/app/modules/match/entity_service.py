"""对局域单实体服务。"""

from typing import List, Optional, Tuple

from app.core.database import new_entity_ids
from app.core.time_utils import now_ms
from app.modules.match.models import MatchActionRecord, MatchRecord
from app.modules.match.repository import MatchActionRecordRepository, MatchRecordRepository
from app.modules.match.schemas import MatchActionRecordCreate, MatchRecordCreate


class MatchRecordEntityService:
    """对局记录实体的基础校验与 CRUD。"""

    def __init__(self, repository: MatchRecordRepository) -> None:
        self._repository = repository

    def get_by_user_and_client_id(self, user_id: str, client_id: str) -> Optional[MatchRecord]:
        """
        按幂等键读取对局记录。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 对局实体或 ``None``。
        """
        return self._repository.get_by_user_and_client_id(user_id, client_id)

    def get_by_server_id(self, server_id: str) -> Optional[MatchRecord]:
        """
        按主键读取未软删对局记录。

        :param server_id: 对局主键。
        :return: 对局实体或 ``None``。
        """
        return self._repository.get_by_server_id(server_id)

    def list_by_user(self, user_id: str, limit: int = 50) -> List[MatchRecord]:
        """
        列出用户最近对局。

        :param user_id: 用户主键。
        :param limit: 返回条数上限。
        :return: 对局列表。
        """
        return self._repository.list_by_user(user_id, limit)

    def count_by_user_filtered(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        mode: Optional[str] = None,
        result: Optional[str] = None,
        difficulty_code: Optional[str] = None,
    ) -> int:
        """
        统计用户历史对局条数（含筛选条件）。

        :param user_id: 用户主键。
        :param game_code: 游戏编码，非空时过滤。
        :param mode: 玩法模式，非空时过滤。
        :param result: 对局结果，非空时过滤。
        :param difficulty_code: 难度编码，非空时过滤。
        :return: 符合条件的总记录数。
        """
        return self._repository.count_by_user_filtered(
            user_id,
            game_code=game_code,
            mode=mode,
            result=result,
            difficulty_code=difficulty_code,
        )

    def page_by_user_filtered(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        mode: Optional[str] = None,
        result: Optional[str] = None,
        difficulty_code: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> List[MatchRecord]:
        """
        分页查询用户历史对局。

        :param user_id: 用户主键。
        :param game_code: 游戏编码，非空时过滤。
        :param mode: 玩法模式，非空时过滤。
        :param result: 对局结果，非空时过滤。
        :param difficulty_code: 难度编码，非空时过滤。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :return: 当前页对局列表。
        """
        return self._repository.page_by_user_filtered(
            user_id,
            game_code=game_code,
            mode=mode,
            result=result,
            difficulty_code=difficulty_code,
            page_num=page_num,
            page_size=page_size,
        )

    def create_match_record_if_not_exists(self, payload: MatchRecordCreate) -> Tuple[MatchRecord, bool]:
        """
        按 ``user_id + client_id`` 幂等写入对局记录。

        :param payload: 创建请求体。
        :return: ``(对局记录, 是否新创建)``。
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
            tomb.result = payload.result
            tomb.difficulty_code = payload.difficultyCode
            tomb.duration_ms = payload.durationMs
            tomb.score = payload.score
            tomb.prop_uses_json = payload.propUsesJson
            tomb.payload_json = payload.payloadJson
            tomb.synced_at = now_ms()
            return self._repository.save(tomb), True
        synced_at = now_ms()
        server_id, created_at, updated_at = new_entity_ids("match_record")
        entity = MatchRecord(
            server_id=server_id,
            client_id=payload.clientId,
            user_id=payload.userId,
            device_id=payload.deviceId,
            game_code=payload.gameCode,
            mode=payload.mode,
            result=payload.result,
            difficulty_code=payload.difficultyCode,
            duration_ms=payload.durationMs,
            score=payload.score,
            prop_uses_json=payload.propUsesJson,
            payload_json=payload.payloadJson,
            synced_at=synced_at,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity), True


class MatchActionRecordEntityService:
    """对局操作记录实体的基础校验与 CRUD。"""

    def __init__(self, repository: MatchActionRecordRepository) -> None:
        self._repository = repository

    def list_by_match_id(self, match_id: str) -> List[MatchActionRecord]:
        """
        按对局 ID 列出操作记录。

        :param match_id: 对局主键。
        :return: 按 ``action_seq`` 升序的操作列表。
        """
        return self._repository.list_by_match_id(match_id)

    def create_match_action_if_not_exists(
        self,
        payload: MatchActionRecordCreate,
    ) -> Tuple[MatchActionRecord, bool]:
        """
        按 ``user_id + client_id`` 幂等写入单条操作记录。

        :param payload: 创建请求体。
        :return: ``(操作记录, 是否新创建)``。
        """
        active = self._repository.get_by_user_and_client_id(payload.userId, payload.clientId, active_only=True)
        if active is not None:
            return active, False
        tomb = self._repository.get_any_by_user_and_client_id(payload.userId, payload.clientId)
        if tomb is not None and tomb.deleted_at is not None:
            tomb.deleted_at = None
            tomb.client_id = payload.clientId
            tomb.match_id = payload.matchId
            tomb.user_id = payload.userId
            tomb.device_id = payload.deviceId
            tomb.game_code = payload.gameCode
            tomb.action_type = payload.actionType
            tomb.action_seq = payload.actionSeq
            tomb.action_time_ms = payload.actionTimeMs
            tomb.payload_json = payload.payloadJson
            tomb.synced_at = now_ms()
            return self._repository.save(tomb), True
        synced_at = now_ms()
        server_id, created_at, updated_at = new_entity_ids("match_action_record")
        entity = MatchActionRecord(
            server_id=server_id,
            client_id=payload.clientId,
            match_id=payload.matchId,
            user_id=payload.userId,
            device_id=payload.deviceId,
            game_code=payload.gameCode,
            action_type=payload.actionType,
            action_seq=payload.actionSeq,
            action_time_ms=payload.actionTimeMs,
            payload_json=payload.payloadJson,
            synced_at=synced_at,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity), True
