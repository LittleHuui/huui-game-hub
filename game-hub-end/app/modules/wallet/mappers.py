"""钱包域 ORM 到 API 响应的转换。"""

import json
from typing import Any, Dict, Optional

from app.core.exceptions import ValidationException
from app.modules.boot.schemas import UserWalletResponse, WalletLedgerResponse
from app.modules.wallet.models import UserWallet, WalletLedger


def _parse_optional_json_dict(raw: Optional[str], *, strict: bool = False) -> Optional[Dict[str, Any]]:
    """
    将存库 JSON 文本解析为字典。

    :param raw: JSON 文本，可空。
    :param strict: 为 ``True`` 时解析失败抛错。
    :return: 字典或 ``None``。
    :raises ValidationException: 严格模式下解析失败或类型非对象。
    """
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        if not strict:
            return None
        raise ValidationException(f"JSON 解析失败: {exc}") from exc
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        if not strict:
            return None
        raise ValidationException("JSON 必须为对象")
    return parsed


def to_user_wallet_response(wallet: UserWallet) -> UserWalletResponse:
    """
    将用户钱包 ORM 转为 API 响应。

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


def to_wallet_ledger_response(ledger: WalletLedger) -> WalletLedgerResponse:
    """
    将钱包流水 ORM 转为 API 响应。

    :param ledger: 流水实体。
    :return: ``WalletLedgerResponse``。
    """
    return WalletLedgerResponse(
        serverId=ledger.server_id,
        clientId=ledger.client_id,
        userId=ledger.user_id,
        deviceId=ledger.device_id,
        gameCode=ledger.game_code,
        changeType=ledger.change_type,
        reason=ledger.reason,
        amount=ledger.amount,
        balanceAfter=ledger.balance_after,
        payload=_parse_optional_json_dict(ledger.payload_json, strict=False),
        syncedAt=ledger.synced_at,
        createdAt=ledger.created_at,
        updatedAt=ledger.updated_at,
        deletedAt=ledger.deleted_at,
    )
