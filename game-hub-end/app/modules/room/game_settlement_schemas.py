"""平台积分结算模型。"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SettlementStatus = Literal["PENDING", "COMPLETED", "FAILED"]


class SettlementExecutionStatus(str, Enum):
    """结算 Outbox 单次执行的完整状态。"""

    COMPLETED = "COMPLETED"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"
    RETRY_REQUIRED = "RETRY_REQUIRED"
    TERMINAL_FAILURE_COMMITTED = "TERMINAL_FAILURE_COMMITTED"
    OBSOLETE = "OBSOLETE"
    CONTRACT_FAILURE = "CONTRACT_FAILURE"


class SettlementExecutionResult(BaseModel):
    """结算 Outbox 单次执行结果。"""

    model_config = ConfigDict(extra="forbid")

    status: SettlementExecutionStatus
    failureCode: Optional[str] = Field(default=None, max_length=64)
    failureReason: Optional[str] = Field(default=None, max_length=500)
    retryable: bool = False
    committedVersion: Optional[int] = Field(default=None, ge=0)


class SettlementPersistenceStatus(str, Enum):
    """数据库结算事务的幂等执行状态。"""

    CREATED = "CREATED"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"


class PlayerSettlementResult(BaseModel):
    """单名玩家平台结算结果。"""

    model_config = ConfigDict(extra="forbid")

    playerId: str = Field(min_length=1)
    expectedDelta: int = Field(description="理论积分变动")
    actualDelta: int = Field(description="实际积分变动")
    balanceBefore: int = Field(ge=0)
    balanceAfter: int = Field(ge=0)
    insufficientAmount: int = Field(default=0, ge=0)
    isAi: bool = Field(default=False, description="是否 AI 玩家（不走真人钱包）")


class GameSettlementResult(BaseModel):
    """一局游戏的平台积分结算结果。"""

    model_config = ConfigDict(extra="forbid")

    settlementId: str = Field(min_length=1)
    roomId: str = Field(min_length=1)
    gameCode: str = Field(min_length=1)
    matchId: str = Field(min_length=1)
    status: SettlementStatus = "COMPLETED"
    playerSettlements: List[PlayerSettlementResult] = Field(default_factory=list)
    systemDelta: int = Field(default=0, description="系统补差总额")


class SettlementPersistenceResult(BaseModel):
    """数据库结算事务结果。"""

    model_config = ConfigDict(extra="forbid")

    status: SettlementPersistenceStatus
    settlementResult: GameSettlementResult


def build_player_ai_map(members: List[Dict[str, Any]]) -> Dict[str, bool]:
    """
    根据房间成员构建玩家 AI 标记映射。

    :param members: 房间成员列表。
    :return: playerId -> 是否 AI。
    """
    result = {}
    for member in members or []:
        if not isinstance(member, dict):
            continue
        player_id = str(member.get("playerId", "")).strip()
        if player_id:
            result[player_id] = bool(member.get("isAi"))
    return result
