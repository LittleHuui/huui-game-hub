"""策略回合制运行时抽象模块。"""

from app.modules.strategy_turn.rule_definition_registry import (
    get_rule_definition,
    get_rule_engine,
    list_registered_game_codes,
    register_rule_engine,
)
from app.modules.strategy_turn.rule_engine import StrategyTurnRuleEngine
from app.modules.strategy_turn.rule_engine_registry import (
    get_rule_engine as get_registered_rule_engine,
    register_rule_engine as register_game_rule_engine,
)
from app.modules.strategy_turn.runtime_service import StrategyTurnRuntimeService
from app.modules.strategy_turn.schemas import (
    ApplyActionCommand,
    ApplyActionResult,
    GameAction,
    GameEvent,
    GameView,
    LegalAction,
    RuntimeSnapshot,
    StartGameCommand,
    StartGameResult,
    StrategyTurnRoomRule,
    StrategyTurnRuleDefinition,
    StrategyTurnRuntimeRule,
)

__all__ = [
    "ApplyActionCommand",
    "ApplyActionResult",
    "GameAction",
    "GameEvent",
    "GameView",
    "LegalAction",
    "RuntimeSnapshot",
    "StartGameCommand",
    "StartGameResult",
    "StrategyTurnRoomRule",
    "StrategyTurnRuleDefinition",
    "StrategyTurnRuleEngine",
    "StrategyTurnRuntimeRule",
    "StrategyTurnRuntimeService",
    "get_registered_rule_engine",
    "get_rule_definition",
    "get_rule_engine",
    "list_registered_game_codes",
    "register_game_rule_engine",
    "register_rule_engine",
]
