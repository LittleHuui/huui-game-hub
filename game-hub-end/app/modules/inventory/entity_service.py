"""背包域单实体服务。"""

from typing import List, Optional

from app.core.database import new_entity_ids
from app.common.exceptions import ValidationException
from app.core.time_utils import now_ms
from app.modules.inventory.models import PropUsageRecord, UserPropBag
from app.modules.inventory.repository import PropUsageRecordRepository, UserPropBagRepository


class UserPropBagEntityService:
    """用户道具背包实体服务。"""

    def __init__(self, repository: UserPropBagRepository) -> None:
        self._repository = repository

    def list_by_user(self, user_id: str, *, game_code: Optional[str] = None) -> List[UserPropBag]:
        """
        列出用户背包。

        :param user_id: 用户主键。
        :param game_code: 可选游戏过滤。
        :return: 背包行列表。
        """
        return self._repository.list_by_user(user_id, game_code=game_code)

    def ensure_line(self, user_id: str, game_code: str, prop_code: str) -> UserPropBag:
        """
        确保背包行存在（不存在则创建数量为 0 的行）。

        :param user_id: 用户主键。
        :param game_code: 游戏编码。
        :param prop_code: 道具编码。
        :return: 背包行。
        """
        existing = self._repository.get_by_user_game_prop(user_id, game_code, prop_code)
        if existing is not None:
            return existing
        server_id, created_at, updated_at = new_entity_ids("user_prop_bag")
        entity = UserPropBag(
            server_id=server_id,
            user_id=user_id,
            game_code=game_code,
            prop_code=prop_code,
            quantity=0,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)

    def apply_aggregate_quantity(self, entity: UserPropBag, quantity: int) -> UserPropBag:
        """
        按购买/使用流水聚合结果回写背包快照（禁止业务层直接调用）。

        :param entity: 背包行。
        :param quantity: 聚合后的数量（非负）。
        :return: 更新后的背包行。
        :raises ValidationException: 数量为负。
        """
        if quantity < 0:
            raise ValidationException("道具数量不能为负")
        entity.quantity = quantity
        return self._repository.save(entity)


class PropUsageRecordEntityService:
    """道具使用记录实体服务。"""

    def __init__(self, repository: PropUsageRecordRepository) -> None:
        self._repository = repository

    def get_by_user_and_client_id(self, user_id: str, client_id: str) -> Optional[PropUsageRecord]:
        """
        按幂等键读取使用记录。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 使用记录或 ``None``。
        """
        return self._repository.get_by_user_and_client_id(user_id, client_id)

    def list_by_user(self, user_id: str) -> List[PropUsageRecord]:
        """
        列出用户使用记录。

        :param user_id: 用户主键。
        :return: 使用记录列表。
        """
        return self._repository.list_by_user(user_id)

    def count_by_user(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        prop_code: Optional[str] = None,
    ) -> int:
        """
        统计用户使用记录条数。

        :param user_id: 用户主键。
        :param game_code: 可选游戏过滤。
        :param prop_code: 可选道具过滤。
        :return: 总条数。
        """
        return self._repository.count_by_user(user_id, game_code=game_code, prop_code=prop_code)

    def list_by_user_paged(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        prop_code: Optional[str] = None,
        page_num: int,
        page_size: int,
    ) -> List[PropUsageRecord]:
        """
        分页列出用户使用记录。

        :param user_id: 用户主键。
        :param game_code: 可选游戏过滤。
        :param prop_code: 可选道具过滤。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :return: 当前页使用记录列表。
        """
        return self._repository.list_by_user_paged(
            user_id,
            game_code=game_code,
            prop_code=prop_code,
            page_num=page_num,
            page_size=page_size,
        )

    def create_record(
        self,
        *,
        client_id: str,
        user_id: str,
        device_id: Optional[str],
        game_code: str,
        match_id: Optional[str],
        prop_code: str,
        quantity: int,
        use_reason: Optional[str],
        payload_json: Optional[str],
    ) -> PropUsageRecord:
        """
        创建使用记录（调用方需保证幂等键未占用）。

        :param client_id: 客户端幂等 ID。
        :param user_id: 用户主键。
        :param device_id: 设备 ID，可空。
        :param game_code: 游戏编码。
        :param match_id: 对局 ID，可空。
        :param prop_code: 道具编码。
        :param quantity: 使用数量。
        :param use_reason: 使用原因，可空。
        :param payload_json: 附加 JSON，可空。
        :return: 新使用记录。
        """
        synced_at = now_ms()
        server_id, created_at, updated_at = new_entity_ids("prop_usage")
        entity = PropUsageRecord(
            server_id=server_id,
            client_id=client_id,
            user_id=user_id,
            device_id=device_id,
            game_code=game_code,
            match_id=match_id,
            prop_code=prop_code,
            quantity=quantity,
            use_reason=use_reason,
            payload_json=payload_json,
            synced_at=synced_at,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)
