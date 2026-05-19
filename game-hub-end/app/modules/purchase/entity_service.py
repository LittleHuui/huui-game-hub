"""购买域单实体服务。"""

from typing import List, Optional, Tuple

from app.core.database import new_entity_ids
from app.core.time_utils import now_ms
from app.modules.purchase.models import PropPurchaseRecord
from app.modules.purchase.repository import PropPurchaseRecordRepository


class PropPurchaseRecordEntityService:
    """道具购买记录实体服务。"""

    def __init__(self, repository: PropPurchaseRecordRepository) -> None:
        self._repository = repository

    def get_by_user_and_client_id(self, user_id: str, client_id: str) -> Optional[PropPurchaseRecord]:
        """
        按幂等键读取购买记录。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 购买记录或 ``None``。
        """
        return self._repository.get_by_user_and_client_id(user_id, client_id)

    def list_by_user(self, user_id: str) -> List[PropPurchaseRecord]:
        """
        列出用户购买记录。

        :param user_id: 用户主键。
        :return: 购买记录列表。
        """
        return self._repository.list_by_user(user_id)

    def page_by_user(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        prop_code: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[PropPurchaseRecord], int]:
        """
        分页查询用户购买记录。

        :param user_id: 用户主键。
        :param game_code: 可选游戏编码过滤。
        :param prop_code: 可选道具编码过滤。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :return: 当前页记录列表与总条数。
        """
        return self._repository.page_by_user(
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
        prop_code: str,
        quantity: int,
        unit_price: int,
        total_price: int,
    ) -> PropPurchaseRecord:
        """
        创建购买记录（调用方需保证幂等键未占用）。

        :param client_id: 客户端幂等 ID。
        :param user_id: 用户主键。
        :param device_id: 设备 ID，可空。
        :param game_code: 游戏编码。
        :param prop_code: 道具编码。
        :param quantity: 购买数量。
        :param unit_price: 单价。
        :param total_price: 总价。
        :return: 新购买记录。
        """
        synced_at = now_ms()
        server_id, created_at, updated_at = new_entity_ids("prop_purchase")
        entity = PropPurchaseRecord(
            server_id=server_id,
            client_id=client_id,
            user_id=user_id,
            device_id=device_id,
            game_code=game_code,
            prop_code=prop_code,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
            synced_at=synced_at,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)
