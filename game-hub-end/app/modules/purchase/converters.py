"""购买域 ORM 与 API 响应转换。"""

from app.modules.purchase.response_schemas import PropPurchaseRecordResponse
from app.modules.purchase.models import PropPurchaseRecord


def to_prop_purchase_record_response(record: PropPurchaseRecord) -> PropPurchaseRecordResponse:
    """
    将购买记录 ORM 转为 API 响应。

    :param record: 购买记录实体。
    :return: ``PropPurchaseRecordResponse``。
    """
    return PropPurchaseRecordResponse(
        serverId=record.server_id,
        clientId=record.client_id,
        userId=record.user_id,
        deviceId=record.device_id,
        gameCode=record.game_code,
        propCode=record.prop_code,
        quantity=record.quantity,
        unitPrice=record.unit_price,
        totalPrice=record.total_price,
        syncedAt=record.synced_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        deletedAt=record.deleted_at,
    )
