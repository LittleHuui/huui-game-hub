"""房间运行时快照的唯一持久化编解码边界。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.modules.strategy_turn.schemas import (
    GameEvent,
    RuntimeSnapshot,
    StrategyTurnRuntimeRule,
    TerminalDirective,
)
from app.modules.strategy_turn.terminal_schemas import TerminalMetadata


class StoredRuntimeSnapshot(BaseModel):
    """Redis 中保存的严格运行时快照。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str = Field(min_length=1)
    roomId: Optional[str] = None
    runtimeRule: StrategyTurnRuntimeRule
    state: Dict[str, Any]
    eventLog: List[GameEvent]
    eventSequence: int = Field(ge=0)
    startedAt: int = Field(ge=0)
    updatedAt: int = Field(ge=0)
    isGameOver: bool
    commitVersion: Optional[int] = Field(default=None, ge=0)
    terminalMetadata: Optional[TerminalMetadata] = None
    terminalDirective: Optional[TerminalDirective] = None


class RuntimeSnapshotCodec(object):
    """在领域快照与 Redis 持久化模型之间转换。"""

    def encode(self, snapshot: RuntimeSnapshot) -> Dict[str, Any]:
        """
        将领域快照编码为严格 Redis 字典。

        :param snapshot: 领域运行时快照。
        :return: 可 JSON 序列化的持久化字典。
        """
        stored = StoredRuntimeSnapshot(
            gameCode=snapshot.gameCode,
            roomId=snapshot.roomId,
            runtimeRule=snapshot.runtimeRule,
            state=snapshot.state,
            eventLog=snapshot.eventLog,
            eventSequence=snapshot.eventSequence,
            startedAt=snapshot.startedAt,
            updatedAt=snapshot.updatedAt,
            isGameOver=snapshot.isGameOver,
            commitVersion=snapshot.commitVersion,
            terminalMetadata=snapshot.terminalMetadata,
            terminalDirective=snapshot.terminalDirective,
        )
        return stored.model_dump()

    def decode(self, raw: Dict[str, Any]) -> RuntimeSnapshot:
        """
        将严格 Redis 字典解码为领域快照。

        :param raw: Redis 读取出的运行时字典。
        :return: 领域运行时快照。
        :raises BizException: 字段缺失、字段非法或出现合同外字段。
        """
        try:
            stored = StoredRuntimeSnapshot.model_validate(raw)
            return RuntimeSnapshot.model_validate(stored.model_dump())
        except (TypeError, ValidationError, ValueError) as exc:
            raise BizException(
                ErrorCode.SYSTEM_ERROR,
                message="房间运行时快照格式无效",
            ) from exc


runtime_snapshot_codec = RuntimeSnapshotCodec()
