"""UNO 枚举型动作交互。"""

from typing import List, Optional, Tuple

from app.common.exceptions import ValidationException
from app.modules.game_impls.uno.uno_action_catalog import UnoActionCatalog, UnoEnumeratedOption
from app.modules.strategy_turn.interaction.automated_candidate_provider import AutomatedCandidateProvider
from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.interaction.enumerated_action_catalog import EnumeratedActionCatalog
from app.modules.strategy_turn.interaction.enumerated_interaction_support import option_to_resolved
from app.modules.strategy_turn.interaction.hint_suggestion_provider import HintSuggestionProvider
from app.modules.strategy_turn.interaction.offer_provider import ActionOfferProvider
from app.modules.strategy_turn.interaction.submission_resolver import ActionSubmissionResolver
from app.modules.strategy_turn.schemas import (
    ActionCandidate,
    ActionSubmission,
    EnumeratedActionInput,
    EnumeratedActionOffer,
    EnumeratedActionOption,
    ResolvedGameAction,
    HintSuggestion,
    HintSuggestionPage,
)


class _ReadonlyInteractionDependencies(object):
    """阻止交互对象在组装完成后替换 Catalog 等依赖。"""

    def __setattr__(self, name, value):
        """组装完成后禁止替换交互依赖。"""
        if getattr(self, "_dependencies_frozen", False) and name in (
            "_catalog",
            "_action_type",
        ):
            raise AttributeError("{0} is read-only".format(name))
        object.__setattr__(self, name, value)

    def _freeze_dependencies(self):
        """锁定本实例的交互依赖。"""
        object.__setattr__(self, "_dependencies_frozen", True)


class UnoEnumeratedActionCatalog(_ReadonlyInteractionDependencies, EnumeratedActionCatalog):
    """UNO 枚举动作目录，输出已解析动作。"""

    def __init__(self, catalog: UnoActionCatalog = None) -> None:
        """
        初始化枚举动作目录。

        :param catalog: 底层动作目录，可空则使用默认实例。
        :return: 无。
        """
        self._catalog = catalog or UnoActionCatalog()
        self._freeze_dependencies()

    def list_options(
        self,
        context: ActionInteractionContext,
        action_type: str,
    ) -> Tuple[UnoEnumeratedOption, ...]:
        """单次枚举当前状态的只读可选项，供 Offer、解析和候选共同使用。"""
        return tuple(self._catalog.list_enumerated_options(
            context.state, context.playerId, action_type,
        ))

    def list_actions(
        self,
        context: ActionInteractionContext,
        action_type: str,
    ) -> List[ResolvedGameAction]:
        """
        列出当前状态下指定类型的全部合法动作。

        :param context: 动作交互上下文。
        :param action_type: 动作类型。
        :return: 已解析动作列表。
        """
        return [option_to_resolved(option) for option in self.list_options(context, action_type)]


class UnoAutomatedCandidateProvider(_ReadonlyInteractionDependencies, AutomatedCandidateProvider):
    """UNO 托管与 AI 自动决策候选 Provider。"""

    def __init__(self, catalog: UnoEnumeratedActionCatalog, action_type: str) -> None:
        """
        初始化自动决策候选 Provider。

        :param catalog: 枚举动作目录。
        :param action_type: 动作类型。
        :return: 无。
        """
        self._catalog = catalog
        self._action_type = str(action_type or "").strip()
        self._freeze_dependencies()

    def list_candidates(
        self,
        context: ActionInteractionContext,
    ) -> List[ActionCandidate]:
        """
        列出自动决策候选（不截断数量）。

        :param context: 动作交互上下文。
        :return: 候选动作列表。
        """
        candidates = []
        for action in self._catalog.list_actions(context, self._action_type):
            submission = ActionSubmission(
                actionType=action.actionType,
                input=EnumeratedActionInput(kind="ENUMERATED", actionId=action.actionId),
            )
            candidates.append(
                ActionCandidate(
                    candidateId=action.actionId,
                    actionType=action.actionType,
                    submission=submission,
                    normalizedAction=action,
                    features={"payload": dict(action.payload or {})},
                )
            )
        return candidates


class UnoHintSuggestionProvider(_ReadonlyInteractionDependencies, HintSuggestionProvider):
    """UNO 用户提示候选 Provider。"""

    def __init__(self, catalog: UnoEnumeratedActionCatalog, action_type: str) -> None:
        """
        初始化提示候选 Provider。

        :param catalog: 枚举动作目录。
        :param action_type: 动作类型。
        :return: 无。
        """
        self._catalog = catalog
        self._action_type = str(action_type or "").strip()
        self._freeze_dependencies()

    def list_page(
        self,
        context: ActionInteractionContext,
        cursor: Optional[str],
        page_size: int,
    ) -> HintSuggestionPage:
        """
        分页列出提示候选。

        :param context: 动作交互上下文。
        :param cursor: 分页游标。
        :param page_size: 页大小。
        :return: 候选分页。
        """
        actions = self._catalog.list_actions(context, self._action_type)
        offset = 0
        if cursor is not None:
            try:
                offset = max(0, int(str(cursor).strip()))
            except (TypeError, ValueError):
                offset = 0
        limit = max(1, int(page_size or 20))
        page_actions = actions[offset: offset + limit]
        next_offset = offset + len(page_actions)
        next_cursor = None
        if next_offset < len(actions):
            next_cursor = str(next_offset)
        suggestions = []
        for action in page_actions:
            suggestions.append(
                HintSuggestion(
                    selection={"actionId": action.actionId},
                    summary=dict(action.payload or {}),
                )
            )
        return HintSuggestionPage(items=suggestions, nextCursor=next_cursor)


class UnoEnumeratedInteraction(
    _ReadonlyInteractionDependencies,
    ActionOfferProvider,
    ActionSubmissionResolver,
):
    """UNO 单动作类型的枚举 Offer 与提交解析。"""

    def __init__(self, catalog: UnoEnumeratedActionCatalog, action_type: str) -> None:
        """
        初始化枚举交互。

        :param catalog: 枚举动作目录。
        :param action_type: 动作类型。
        :return: 无。
        """
        self._catalog = catalog
        self._action_type = str(action_type or "").strip()
        self._freeze_dependencies()

    def build_offer(self, context: ActionInteractionContext) -> Optional[EnumeratedActionOffer]:
        """
        构建 UNO 枚举动作 Offer。

        :param context: 动作交互上下文。
        :return: 枚举 Offer；无选项时返回 None。
        """
        options = []
        for option in self._catalog.list_options(context, self._action_type):
            options.append(
                EnumeratedActionOption(
                    actionId=option.actionId,
                    payload=dict(option.payload),
                    selection=option.selection,
                )
            )
        if not options:
            return None
        return EnumeratedActionOffer(
            actionType=self._action_type,
            interactionMode="ENUMERATED",
            options=options,
        )

    def resolve(
        self,
        context: ActionInteractionContext,
        submission: ActionSubmission,
    ) -> ResolvedGameAction:
        """
        根据 actionId 解析 UNO 枚举动作。

        :param context: 动作交互上下文。
        :param submission: 外部动作意图。
        :return: 已解析动作。
        """
        if not isinstance(submission.input, EnumeratedActionInput):
            raise ValidationException("动作提交类型不匹配")
        target_action_id = str(submission.input.actionId or "").strip()
        for option in self._catalog.list_options(context, self._action_type):
            if str(option.actionId or "").strip() == target_action_id:
                return option_to_resolved(option)
        raise ValidationException("动作已过期或不合法")
