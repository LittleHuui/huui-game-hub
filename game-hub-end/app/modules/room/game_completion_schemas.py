"""终局规划与 Outbox 意图模型。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.strategy_turn.schemas import RuntimeSnapshot

TERMINAL_DISPLAY_MS = 3000


class OwnerTransferPlan(BaseModel):
    """终局后房主转移计划。"""

    model_config = ConfigDict(extra="forbid")

    ownerPlayerId: str = Field(min_length=1)
    ownerNickname: str = Field(min_length=1)


class GameCompletionPlan(BaseModel):
    """对局结束后的纯规划结果，不含任何副作用。"""

    model_config = ConfigDict(extra="forbid")

    terminalSnapshot: RuntimeSnapshot = Field(description="带终局元数据的运行时快照")
    nextRoomMeta: Dict[str, Any] = Field(description="提交用房间元信息，status 仍为 playing")
    dissolveAfterTerminal: bool = Field(description="终局展示后是否解散房间")
    membersToRemoveAfterTerminal: List[str] = Field(
        default_factory=list,
        description="终局 finalize 时需移除的成员 playerId 列表",
    )
    ownerTransferPlan: Optional[OwnerTransferPlan] = Field(
        default=None,
        description="终局 finalize 时的房主转移计划",
    )
    terminalDisplayUntil: int = Field(ge=0, description="终局展示截止时间（毫秒）")
    settlementRequired: bool = Field(default=False, description="是否需要平台积分结算")
