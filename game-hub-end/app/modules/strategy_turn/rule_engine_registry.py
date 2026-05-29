"""策略回合制规则引擎注册表。"""

from typing import Dict, Optional

from app.common.exceptions import ValidationException
from app.modules.strategy_turn.rule_engine import StrategyTurnRuleEngine

_ENGINE_REGISTRY = {}  # type: Dict[str, StrategyTurnRuleEngine]


def register_rule_engine(game_code: str, engine: StrategyTurnRuleEngine) -> None:
    """
    注册游戏的规则引擎实例。

    :param game_code: 游戏编码。
    :param engine: 规则引擎实例。
    :raises ValidationException: ``game_code`` 为空时抛出。
    """
    normalized = str(game_code).strip()
    if not normalized:
        raise ValidationException("game_code 不能为空")
    _ENGINE_REGISTRY[normalized] = engine


def get_rule_engine(game_code: str) -> Optional[StrategyTurnRuleEngine]:
    """
    按 ``gameCode`` 获取已注册的规则引擎。

    :param game_code: 游戏编码。
    :return: 引擎实例；未注册时为 ``None``。
    """
    from app.modules.strategy_turn.rule_definition_registry import ensure_builtin_registered

    ensure_builtin_registered()
    normalized = str(game_code).strip()
    if not normalized:
        return None
    return _ENGINE_REGISTRY.get(normalized)
