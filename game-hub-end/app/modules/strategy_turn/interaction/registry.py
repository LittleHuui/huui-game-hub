"""动作交互绑定注册表。"""



from types import MappingProxyType
from typing import Dict, List



from app.common.exceptions import ValidationException

from app.modules.strategy_turn.game_module import StrategyTurnGameModuleRegistry

from app.modules.strategy_turn.interaction.binding import ActionInteractionBinding





class ActionInteractionRegistry(object):

    """按 gameCode 和 actionType 管理动作交互绑定。"""



    def __init__(self) -> None:

        self._bindings = {}  # type: Dict[str, Dict[str, ActionInteractionBinding]]

        self._frozen = False



    def register_game(self, game_code: str, bindings: List[ActionInteractionBinding]) -> None:

        """

        注册一个游戏的全部动作绑定。



        :param game_code: 游戏编码。

        :param bindings: 动作绑定列表。

        :return: 无。

        :raises ValidationException: 注册表已冻结、游戏编码为空或动作重复时抛出。

        """

        if self._frozen:

            raise ValidationException("动作交互注册表已冻结，无法继续注册")

        normalized = str(game_code or "").strip()

        if not normalized:

            raise ValidationException("gameCode 不能为空")

        if normalized in self._bindings:

            raise ValidationException("gameCode 不得重复注册")

        action_map = {}  # type: Dict[str, ActionInteractionBinding]

        for binding in bindings or []:

            action_type = str(binding.actionType or "").strip()

            if not action_type:

                raise ValidationException("actionType 不能为空")

            if action_type in action_map:

                raise ValidationException("actionType 不得重复注册")

            if binding.interactionMode not in ("ENUMERATED", "COMPOSED"):

                raise ValidationException("interactionMode 必填")

            if binding.offerProvider is None or binding.submissionResolver is None:

                raise ValidationException("OfferProvider 与 SubmissionResolver 必填")

            action_map[action_type] = binding

        self._bindings[normalized] = action_map



    def freeze(self) -> None:

        """

        冻结注册表，禁止继续注册。



        :return: 无。

        """

        if self._frozen:
            return
        self._bindings = MappingProxyType(
            {
                game_code: MappingProxyType(dict(bindings))
                for game_code, bindings in self._bindings.items()
            },
        )
        self._frozen = True



    def require(self, game_code: str, action_type: str) -> ActionInteractionBinding:

        """

        获取指定动作绑定。



        :param game_code: 游戏编码。

        :param action_type: 动作类型。

        :return: 动作绑定。

        :raises ValidationException: 未注册时抛出。

        """

        normalized_game = str(game_code or "").strip()

        normalized_action = str(action_type or "").strip()

        game_bindings = self._bindings.get(normalized_game)

        if game_bindings is None:

            raise ValidationException("游戏动作绑定未注册")

        binding = game_bindings.get(normalized_action)

        if binding is None:

            raise ValidationException("动作类型未注册")

        return binding



    def list_bindings(self, game_code: str) -> List[ActionInteractionBinding]:

        """

        列出游戏的全部动作绑定。



        :param game_code: 游戏编码。

        :return: 动作绑定列表。

        """

        normalized = str(game_code or "").strip()

        return list((self._bindings.get(normalized) or {}).values())





def build_interaction_registry_from_modules(

    module_registry: StrategyTurnGameModuleRegistry,

) -> ActionInteractionRegistry:

    """

    从游戏模块注册表构建并校验动作交互注册表。



    :param module_registry: 策略回合游戏模块注册表。

    :return: 已冻结的动作交互注册表。

    """

    registry = ActionInteractionRegistry()

    for game_code in module_registry.list_game_codes():

        module = module_registry.require(game_code)

        if str(module.gameCode or "").strip() != str(game_code).strip():

            raise ValidationException("module.gameCode 与注册 gameCode 不一致")

        has_automated_provider = any(
            binding.automatedCandidateProvider is not None
            for binding in module.interactionBindings
        )
        components = (
            module.candidateScorer,
            module.candidateSelector,
            module.fallbackPolicy,
        )
        if has_automated_provider and any(component is None for component in components):
            raise ValidationException("自动决策组件必须完整注册")
        if not has_automated_provider and any(component is not None for component in components):
            raise ValidationException("无自动决策能力的游戏不得注册自动决策组件")

        registry.register_game(game_code, module.interactionBindings)

    registry.freeze()

    return registry
