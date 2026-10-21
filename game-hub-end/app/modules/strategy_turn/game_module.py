"""策略回合游戏模块注册表。"""

from types import MappingProxyType
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.exceptions import ValidationException
from app.modules.strategy_turn.decision.candidate_scorer import CandidateScorer
from app.modules.strategy_turn.decision.candidate_selector import CandidateSelector
from app.modules.strategy_turn.decision.fallback_policy import FallbackPolicy
from app.modules.strategy_turn.interaction.binding import ActionInteractionBinding
from app.modules.strategy_turn.lifecycle import GameLifecycleEngine, GameStateProjector


class StrategyTurnGameModule(BaseModel):
    """一个策略回合游戏的运行时组件集合。"""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    gameCode: str = Field(min_length=1, description="游戏编码")
    lifecycleEngine: GameLifecycleEngine = Field(description="生命周期引擎")
    stateProjector: GameStateProjector = Field(description="状态投影器")
    interactionBindings: Tuple[ActionInteractionBinding, ...] = Field(
        default_factory=tuple,
        description="动作交互绑定",
    )
    candidateScorer: Optional[CandidateScorer] = Field(default=None, description="候选评分器")
    candidateSelector: Optional[CandidateSelector] = Field(default=None, description="候选选择器")
    fallbackPolicy: Optional[FallbackPolicy] = Field(default=None, description="游戏兜底策略")

    @model_validator(mode="after")
    def validate_automated_components(self):
        """
        校验自动决策组件必须按能力成组出现。

        :return: 当前模块。
        """
        has_provider = any(
            binding.automatedCandidateProvider is not None
            for binding in self.interactionBindings
        )
        decision_components = (
            self.candidateScorer,
            self.candidateSelector,
            self.fallbackPolicy,
        )
        if has_provider and self.fallbackPolicy is None:
            raise ValueError("存在自动候选 Provider 时必须显式注册 fallbackPolicy")
        if not has_provider and any(component is not None for component in decision_components):
            raise ValueError("不存在自动候选 Provider 时不得注册自动决策组件")
        return self


class StrategyTurnGameModuleRegistry(object):
    """按 gameCode 管理策略回合游戏模块。"""

    def __init__(self) -> None:
        self._modules = {}  # type: Dict[str, StrategyTurnGameModule]
        self._frozen = False

    def register(self, module: StrategyTurnGameModule) -> None:
        """
        注册游戏模块。

        :param module: 游戏模块。
        :return: 无。
        :raises ValidationException: 注册表已冻结、游戏编码重复或为空时抛出。
        """
        if self._frozen:
            raise ValidationException("游戏模块注册表已冻结，无法继续注册")
        game_code = str(module.gameCode or "").strip()
        if not game_code:
            raise ValidationException("gameCode 不能为空")
        if game_code in self._modules:
            raise ValidationException("gameCode 不得重复注册")
        self._modules[game_code] = module

    def freeze(self) -> None:
        """
        冻结注册表，禁止继续注册。

        :return: 无。
        """
        if self._frozen:
            return
        self._modules = MappingProxyType(dict(self._modules))
        self._frozen = True

    @property
    def is_frozen(self) -> bool:
        """Return whether the registry has been frozen."""
        return bool(self._frozen)

    def get(self, game_code: str) -> Optional[StrategyTurnGameModule]:
        """
        获取游戏模块。

        :param game_code: 游戏编码。
        :return: 游戏模块，未注册时返回 None。
        """
        normalized = str(game_code or "").strip()
        if not normalized:
            return None
        return self._modules.get(normalized)

    def require(self, game_code: str) -> StrategyTurnGameModule:
        """
        获取已注册游戏模块。

        :param game_code: 游戏编码。
        :return: 游戏模块。
        :raises ValidationException: 未注册时抛出。
        """
        module = self.get(game_code)
        if module is None:
            raise ValidationException("游戏模块未注册")
        return module

    def list_game_codes(self) -> List[str]:
        """
        列出已注册游戏编码。

        :return: 游戏编码列表。
        """
        return list(self._modules.keys())
