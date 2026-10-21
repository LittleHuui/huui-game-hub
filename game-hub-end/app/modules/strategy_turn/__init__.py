"""策略回合制运行时抽象模块。"""

from app.modules.strategy_turn.runtime_service import StrategyTurnRuntimeService
from app.modules.strategy_turn.schemas import (
    ActionOutcome,
    AdvanceOutcome,
    ApplyActionCommand,
    ApplyActionResult,
    DomainEventDraft,
    GameEvent,
    GameView,
    InitialStateOutcome,
    RuntimeSnapshot,
    StartGameCommand,
    StartGameResult,
    StrategyTurnRoomRule,
    StrategyTurnRuntimeRule,
)

__all__ = [
    "ActionOutcome",
    "AdvanceOutcome",
    "ApplyActionCommand",
    "ApplyActionResult",
    "DomainEventDraft",
    "GameEvent",
    "GameView",
    "InitialStateOutcome",
    "RuntimeSnapshot",
    "StartGameCommand",
    "StartGameResult",
    "StrategyTurnRoomRule",
    "StrategyTurnRuntimeRule",
    "StrategyTurnRuntimeService",
]
