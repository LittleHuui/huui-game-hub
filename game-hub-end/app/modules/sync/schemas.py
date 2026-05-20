"""同步域 Pydantic 模型（pending 事件协议）。"""

from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field

SyncEventType = Literal[
    "user_update",
    "user_system_setting_update",
    "user_game_setting_update",
    "wallet_ledger",
    "prop_purchase",
    "prop_usage",
    "match_record",
    "match_action",
    "score_record",
]


class PendingEvent(BaseModel):
    """待同步的客户端事件（camelCase）。"""

    model_config = ConfigDict(extra="forbid")

    clientId: str = Field(min_length=1)
    eventType: SyncEventType
    createdAt: int
    updatedAt: int
    payload: Dict[str, Any] = Field(default_factory=dict)
