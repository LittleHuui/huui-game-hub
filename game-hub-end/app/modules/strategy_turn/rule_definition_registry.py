"""策略回合制规则定义注册表。"""

from typing import Dict, List, Optional

from app.modules.strategy_turn.rule_engine import StrategyTurnRuleEngine
from app.modules.strategy_turn.rule_engine_registry import (
    get_rule_engine,
    register_rule_engine as register_game_rule_engine,
)
from app.modules.strategy_turn.schemas import StrategyTurnRuleDefinition

_DEFINITION_REGISTRY: Dict[str, StrategyTurnRuleDefinition] = {}
_BUILTIN_REGISTERED = False


def register_rule_engine(
    definition: StrategyTurnRuleDefinition,
    engine: StrategyTurnRuleEngine,
) -> None:
    """
    注册游戏的规则定义与引擎实例。

    :param definition: 规则定义元数据。
    :param engine: 规则引擎实例。
    """
    _DEFINITION_REGISTRY[definition.gameCode] = definition
    register_game_rule_engine(definition.gameCode, engine)


def ensure_builtin_registered() -> None:
    """确保内置规则定义与引擎已完成注册（延迟加载，避免循环导入）。"""
    global _BUILTIN_REGISTERED
    if _BUILTIN_REGISTERED:
        return
    _BUILTIN_REGISTERED = True
    _register_builtin_definitions()


def get_rule_definition(game_code: str) -> Optional[StrategyTurnRuleDefinition]:
    """
    按 ``gameCode`` 获取已注册的规则定义。

    :param game_code: 游戏编码。
    :return: 规则定义；未注册时为 ``None``。
    """
    ensure_builtin_registered()
    return _DEFINITION_REGISTRY.get(game_code)


def list_registered_game_codes() -> List[str]:
    """
    列出已注册 ``gameCode`` 列表。

    :return: 游戏编码列表。
    """
    ensure_builtin_registered()
    return list(_DEFINITION_REGISTRY.keys())


def _register_builtin_definitions() -> None:
    """注册内置 demo 规则定义（不含具体玩法实现）。"""
    from app.modules.games.uno.uno_rule_engine import UnoRuleEngine

    register_rule_engine(
        StrategyTurnRuleDefinition(
            gameCode="uno",
            ruleVersion="demo-1",
            roomRule={
                "minPlayers": 2,
                "maxPlayers": 10,
                "allowBot": True,
                "defaultExpireSeconds": 86400,
            },
            runtimeRule={
                "actionSubmitMode": "actionIdOnly",
                "privateView": True,
            },
            actionTypes=[],
            assets={},
        ),
        UnoRuleEngine(),
    )
