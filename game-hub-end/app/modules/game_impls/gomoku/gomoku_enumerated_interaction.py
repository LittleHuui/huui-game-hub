"""五子棋枚举型动作交互。"""

from typing import List, Optional

from app.common.exceptions import ValidationException
from app.modules.game_impls.gomoku.gomoku_action_catalog import (
    GomokuActionCatalog,
    GomokuEnumeratedOption,
)
from app.modules.strategy_turn.interaction.automated_candidate_provider import AutomatedCandidateProvider
from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.interaction.enumerated_interaction_support import (
    option_to_candidate,
    option_to_resolved,
)
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


class GomokuEnumeratedInteraction(
    ActionOfferProvider,
    ActionSubmissionResolver,
    AutomatedCandidateProvider,
    HintSuggestionProvider,
):
    """五子棋单动作类型的枚举交互实现。"""

    def __setattr__(self, name, value):
        if getattr(self, "_dependencies_frozen", False) and name in (
            "_catalog",
            "_action_type",
        ):
            raise AttributeError("{0} is read-only".format(name))
        object.__setattr__(self, name, value)

    def __init__(self, catalog: GomokuActionCatalog, action_type: str) -> None:
        """
        初始化枚举交互。

        :param catalog: 五子棋动作目录。
        :param action_type: 动作类型。
        :return: 无。
        """
        self._catalog = catalog
        self._action_type = str(action_type or "").strip()
        object.__setattr__(self, "_dependencies_frozen", True)

    def build_offer(self, context: ActionInteractionContext) -> Optional[EnumeratedActionOffer]:
        """
        构建五子棋枚举动作 Offer。

        :param context: 动作交互上下文。
        :return: 枚举 Offer；无选项时返回 None。
        """
        options = []
        for option in self._list_options(context):
            options.append(
                EnumeratedActionOption(
                    actionId=option.actionId,
                    payload=dict(option.payload or {}),
                    selection=dict(option.selection or {}),
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
        根据 actionId 解析五子棋枚举动作。

        :param context: 动作交互上下文。
        :param submission: 外部动作意图。
        :return: 已解析动作。
        """
        if not isinstance(submission.input, EnumeratedActionInput):
            raise ValidationException("动作提交类型不匹配")
        target_action_id = str(submission.input.actionId or "").strip()
        for option in self._list_options(context):
            if str(option.actionId or "").strip() == target_action_id:
                return option_to_resolved(option)
        raise ValidationException("动作已过期或不合法")

    def list_candidates(
        self,
        context: ActionInteractionContext,
    ) -> List[ActionCandidate]:
        """
        返回当前动作类型的全部自动决策候选。

        :param context: 动作交互上下文。
        :return: 候选列表。
        """
        return [option_to_candidate(option) for option in self._list_options(context)]

    def list_page(
        self,
        context: ActionInteractionContext,
        cursor: Optional[str],
        page_size: int,
    ) -> HintSuggestionPage:
        """
        分页返回用户提示候选。

        :param context: 动作交互上下文。
        :param cursor: 分页游标。
        :param page_size: 页大小。
        :return: 候选分页。
        """
        options = self._list_options(context)
        offset = max(0, int(cursor or 0)) if str(cursor or "").isdigit() else 0
        limit = max(1, int(page_size or 20))
        selected = options[offset:offset + limit]
        next_offset = offset + len(selected)
        next_cursor = str(next_offset) if next_offset < len(options) else None
        return HintSuggestionPage(
            items=[
                HintSuggestion(
                    selection=dict(option.selection or {"actionId": option.actionId}),
                    summary=dict(option.payload or {}),
                )
                for option in selected
            ],
            nextCursor=next_cursor,
        )

    def _list_options(self, context: ActionInteractionContext) -> List[GomokuEnumeratedOption]:
        """
        列出当前动作类型的枚举可选项。

        :param context: 动作交互上下文。
        :return: 枚举可选项列表。
        """
        return self._catalog.list_enumerated_options(
            context.state,
            context.playerId,
            self._action_type,
            context.currentTimeMs,
        )
