"""游戏运行时共享装配（composition root）。"""

from dataclasses import dataclass
from typing import Dict, Optional

from app.modules.strategy_turn.decision.managed_decision_service import ManagedDecisionService
from app.modules.strategy_turn.game_module import (
    StrategyTurnGameModule,
    StrategyTurnGameModuleRegistry,
)
from app.modules.strategy_turn.interaction.gateway import ActionInteractionGateway
from app.modules.strategy_turn.interaction.registry import build_interaction_registry_from_modules
from app.modules.strategy_turn.runtime_service import StrategyTurnRuntimeService
from app.modules.strategy_turn.view_service import GameViewService

_module_registry = None  # type: Optional[StrategyTurnGameModuleRegistry]
_runtime_instance = None  # type: Optional[GameRuntime]


def build_game_module_registry(
    module_overrides: Optional[Dict[str, StrategyTurnGameModule]] = None,
) -> StrategyTurnGameModuleRegistry:
    """
    组装并冻结内置策略回合游戏模块注册表。

    :return: 已冻结的游戏模块注册表。
    """
    from app.modules.game_impls.doudizhu.doudizhu_game_module import build_doudizhu_game_module
    from app.modules.game_impls.gomoku.gomoku_game_module import build_gomoku_game_module
    from app.modules.game_impls.uno.uno_game_module import build_uno_game_module

    overrides = dict(module_overrides or {})
    modules = (
        build_uno_game_module(),
        build_gomoku_game_module(),
        build_doudizhu_game_module(),
    )
    registry = StrategyTurnGameModuleRegistry()
    for module in modules:
        registry.register(overrides.pop(module.gameCode, module))
    if overrides:
        raise ValueError("unknown game module overrides: {0}".format(sorted(overrides.keys())))
    registry.freeze()
    return registry


def get_game_module_registry() -> StrategyTurnGameModuleRegistry:
    """
    获取全局游戏模块注册表单例。

    :return: 已冻结的游戏模块注册表。
    """
    global _module_registry
    if _module_registry is None:
        _module_registry = build_game_module_registry()
    return _module_registry


@dataclass(frozen=True)
class GameRuntime(object):
    """策略回合运行时共享依赖。"""

    module_registry: StrategyTurnGameModuleRegistry
    runtime_service: StrategyTurnRuntimeService
    interaction_gateway: ActionInteractionGateway
    game_view_service: GameViewService
    managed_decision_service: ManagedDecisionService

def _build_runtime_from_registry(
    module_registry: StrategyTurnGameModuleRegistry,
    interaction_gateway: Optional[ActionInteractionGateway] = None,
) -> GameRuntime:
    """基于给定模块注册表组装一套独立运行时对象图。"""
    runtime_service = StrategyTurnRuntimeService(module_registry)
    resolved_gateway = interaction_gateway
    if resolved_gateway is None:
        interaction_registry = build_interaction_registry_from_modules(module_registry)
        resolved_gateway = ActionInteractionGateway(interaction_registry)
    game_view_service = GameViewService(module_registry, resolved_gateway)
    managed_decision_service = ManagedDecisionService(module_registry, resolved_gateway)
    return GameRuntime(
        module_registry=module_registry,
        runtime_service=runtime_service,
        interaction_gateway=resolved_gateway,
        game_view_service=game_view_service,
        managed_decision_service=managed_decision_service,
    )


def build_game_runtime() -> GameRuntime:
    """
    组装策略回合共享运行时依赖。

    :return: 游戏运行时对象。
    """
    return _build_runtime_from_registry(get_game_module_registry())


def get_game_runtime() -> GameRuntime:
    """
    获取游戏运行时单例。

    :return: 游戏运行时对象。
    """
    global _runtime_instance
    if _runtime_instance is None:
        _runtime_instance = build_game_runtime()
    return _runtime_instance
