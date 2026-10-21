"""平台通用终局元数据严格模型（与具体游戏无关）。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

TerminalStatus = Literal[
    "PENDING_SETTLEMENT",
    "DISPLAYING",
    "DISPLAYING_SETTLEMENT_FAILED",
]
SettlementStatus = Literal["PENDING", "COMPLETED", "FAILED"]


class TerminalOwnerTransferPlan(BaseModel):
    """终局后房主转移计划。"""

    model_config = ConfigDict(extra="forbid")

    ownerPlayerId: str = Field(min_length=1)
    ownerNickname: str = Field(min_length=1)


class PlatformPlayerSettlementView(BaseModel):
    """平台结算结果中的单玩家视图。"""

    model_config = ConfigDict(extra="forbid")

    playerId: str = Field(min_length=1)
    expectedDelta: int = Field(description="理论积分变动")
    actualDelta: int = Field(description="实际积分变动")
    balanceBefore: int = Field(ge=0)
    balanceAfter: int = Field(ge=0)
    insufficientAmount: int = Field(default=0, ge=0)
    isAi: bool = Field(default=False, description="是否 AI 玩家（不走真人钱包）")


class PlatformSettlementResultView(BaseModel):
    """平台结算结果视图。"""

    model_config = ConfigDict(extra="forbid")

    settlementId: str = Field(min_length=1)
    matchId: str = Field(min_length=1)
    status: SettlementStatus = "COMPLETED"
    playerSettlements: List[PlatformPlayerSettlementView] = Field(default_factory=list)
    systemDelta: int = Field(default=0, description="系统补差总额")


class TerminalMetadata(BaseModel):
    """终局阶段平台元数据（RuntimeSnapshot / GameView / Redis 共用）。"""

    model_config = ConfigDict(extra="forbid")

    terminalStatus: TerminalStatus
    settlementId: Optional[str] = Field(default=None)
    settlementStatus: Optional[SettlementStatus] = Field(default=None)
    settlementResultId: Optional[str] = Field(default=None)
    settlementResult: Optional[PlatformSettlementResultView] = Field(default=None)
    terminalDisplayUntil: int = Field(ge=0, description="终局展示截止时间（毫秒）")
    dissolveAfterTerminal: bool = Field(default=False)
    membersToRemoveAfterTerminal: List[str] = Field(default_factory=list)
    ownerTransferPlan: Optional[TerminalOwnerTransferPlan] = Field(default=None)
    settlementFailureCode: Optional[str] = Field(default=None)
    settlementFailureReason: Optional[str] = Field(default=None)
