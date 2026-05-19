"""购买域 ORM 与 API 响应转换。"""

from app.modules.boot.schemas import PropPurchaseRecordResponse, UserPropBagResponse, UserWalletResponse
from app.modules.inventory.models import UserPropBag
from app.modules.purchase.models import PropPurchaseRecord
from app.modules.wallet.models import UserWallet


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


def to_user_wallet_response(wallet: UserWallet) -> UserWalletResponse:
    """
    将钱包 ORM 转为 API 响应。

    :param wallet: 钱包实体。
    :return: ``UserWalletResponse``。
    """
    return UserWalletResponse(
        serverId=wallet.server_id,
        clientId=None,
        userId=wallet.user_id,
        balance=wallet.balance,
        totalEarned=wallet.total_earned,
        createdAt=wallet.created_at,
        updatedAt=wallet.updated_at,
        deletedAt=wallet.deleted_at,
    )


def to_user_prop_bag_response(bag: UserPropBag) -> UserPropBagResponse:
    """
    将背包行 ORM 转为 API 响应。

    :param bag: 背包实体。
    :return: ``UserPropBagResponse``。
    """
    return UserPropBagResponse(
        serverId=bag.server_id,
        clientId=None,
        userId=bag.user_id,
        gameCode=bag.game_code,
        propCode=bag.prop_code,
        quantity=bag.quantity,
        createdAt=bag.created_at,
        updatedAt=bag.updated_at,
        deletedAt=bag.deleted_at,
    )
