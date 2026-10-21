"""斗地主枚举型动作交互。"""

from typing import List, Optional

from app.common.exceptions import ValidationException
from app.modules.game_impls.doudizhu.doudizhu_bidding_rule import (
    can_decide_bid,
    list_legal_bid_scores,
)
from app.modules.game_impls.doudizhu.doudizhu_constants import (
    ACTION_CALL_LANDLORD,
    ACTION_DOUBLE,
    ACTION_PASS,
    ACTION_PASS_CALL,
    ACTION_PASS_DOUBLE,
    ACTION_PASS_ROB,
    ACTION_ROB_LANDLORD,
    ACTION_SHOW_CARDS,
    ACTION_SKIP_SHOW_CARDS,
    PHASE_CALLING,
    PHASE_DOUBLING,
    PHASE_PLAYING,
    PHASE_ROBBING,
    PHASE_SHOWING,
)
from app.modules.game_impls.doudizhu.doudizhu_rule_policy import uses_classic_bid_rules
from app.modules.game_impls.doudizhu.doudizhu_state_helpers import (
    build_simple_action,
    parse_combo_info,
)
from app.modules.strategy_turn.interaction.automated_candidate_provider import AutomatedCandidateProvider
from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.interaction.hint_suggestion_provider import HintSuggestionProvider
from app.modules.strategy_turn.interaction.offer_provider import ActionOfferProvider
from app.modules.strategy_turn.interaction.submission_resolver import ActionSubmissionResolver
from app.modules.strategy_turn.schemas import (
    ActionCandidate,
    ActionSubmission,
    EnumeratedActionInput,
    EnumeratedActionOffer,
    EnumeratedActionOption,
    HintSuggestion,
    HintSuggestionPage,
    ResolvedGameAction,
)


_PHASE_BY_ACTION_TYPE = {
    ACTION_SHOW_CARDS: PHASE_SHOWING,
    ACTION_SKIP_SHOW_CARDS: PHASE_SHOWING,
    ACTION_CALL_LANDLORD: PHASE_CALLING,
    ACTION_PASS_CALL: PHASE_CALLING,
    ACTION_ROB_LANDLORD: PHASE_ROBBING,
    ACTION_PASS_ROB: PHASE_ROBBING,
    ACTION_DOUBLE: PHASE_DOUBLING,
    ACTION_PASS_DOUBLE: PHASE_DOUBLING,
}

_ACTION_SUFFIX = {
    ACTION_SHOW_CARDS: "show",
    ACTION_SKIP_SHOW_CARDS: "skip-show",
    ACTION_CALL_LANDLORD: "call",
    ACTION_PASS_CALL: "pass-call",
    ACTION_ROB_LANDLORD: "rob",
    ACTION_PASS_ROB: "pass-rob",
    ACTION_DOUBLE: "double",
    ACTION_PASS_DOUBLE: "pass-double",
    ACTION_PASS: "pass",
}


class DoudizhuEnumeratedInteraction(
    ActionOfferProvider,
    ActionSubmissionResolver,
    AutomatedCandidateProvider,
    HintSuggestionProvider,
):
    """同一合法动作集合服务于 Offer、提交解析、自动决策与提示。"""

    def __init__(self, action_type: str) -> None:
        self._action_type = str(action_type or "").strip()

    def build_offer(self, context: ActionInteractionContext) -> Optional[EnumeratedActionOffer]:
        """
        构建枚举动作 Offer。

        :param context: 动作交互上下文。
        :return: 枚举动作 Offer；不可用时返回 ``None``。
        """
        actions = self._list_actions(context)
        if not actions:
            return None
        options = [
            EnumeratedActionOption(
                actionId=action.actionId,
                payload=dict(action.payload or {}),
                selection={},
            )
            for action in actions
        ]
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
        根据 actionId 解析枚举动作。

        :param context: 动作交互上下文。
        :param submission: 外部动作意图。
        :return: 已解析动作。
        """
        if not isinstance(submission.input, EnumeratedActionInput):
            raise ValidationException("动作提交类型不匹配")
        if submission.actionType != self._action_type:
            raise ValidationException("动作类型不匹配")
        target_action_id = str(submission.input.actionId or "").strip()
        for action in self._list_actions(context):
            if str(action.actionId or "").strip() == target_action_id:
                return ResolvedGameAction(
                    actionId=action.actionId,
                    actionType=action.actionType,
                    playerId=action.playerId,
                    payload=dict(action.payload or {}),
                )
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
        return [self._action_to_candidate(action) for action in self._list_actions(context)]

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
        actions = self._list_actions(context)
        offset = 0
        if cursor is not None:
            try:
                offset = max(0, int(str(cursor).strip()))
            except (TypeError, ValueError):
                offset = 0
        limit = max(1, int(page_size or 20))
        page_actions = actions[offset: offset + limit]
        next_offset = offset + len(page_actions)
        next_cursor = str(next_offset) if next_offset < len(actions) else None
        return HintSuggestionPage(
            items=[
                HintSuggestion(
                    selection={"actionId": action.actionId},
                    summary=dict(action.payload or {}),
                )
                for action in page_actions
            ],
            nextCursor=next_cursor,
        )

    def _action_to_candidate(self, action) -> ActionCandidate:
        """
        将枚举动作转为候选。

        :param action: 已解析动作。
        :return: 动作候选。
        """
        submission = ActionSubmission(
            actionType=action.actionType,
            input=EnumeratedActionInput(kind="ENUMERATED", actionId=action.actionId),
        )
        normalized = ResolvedGameAction(
            actionId=action.actionId,
            actionType=action.actionType,
            playerId=action.playerId,
            payload=dict(action.payload or {}),
        )
        return ActionCandidate(
            candidateId=action.actionId,
            actionType=action.actionType,
            submission=submission,
            normalizedAction=normalized,
            features={
                "payload": dict(action.payload or {}),
                "selection": {},
            },
        )

    def _list_actions(self, context: ActionInteractionContext) -> List[ResolvedGameAction]:
        """
        列出当前动作类型在当回合可用的枚举动作。

        :param context: 动作交互上下文。
        :return: 合法动作列表。
        """
        if not self._is_turn_available(context):
            return []
        suffix = _ACTION_SUFFIX.get(self._action_type)
        if suffix is None:
            return []
        if self._action_type == ACTION_CALL_LANDLORD and uses_classic_bid_rules(context.state):
            actions = []
            for score in list_legal_bid_scores(context.state, context.playerId):
                action = build_simple_action(
                    self._action_type, context.playerId, "{0}-{1}".format(suffix, score),
                )
                action.payload = {"bidScore": score}
                actions.append(action)
            return actions
        action = build_simple_action(self._action_type, context.playerId, suffix)
        return [action]

    def _is_turn_available(self, context: ActionInteractionContext) -> bool:
        """
        判断当前玩家是否可执行该枚举动作。

        :param context: 动作交互上下文。
        :return: 可用为 ``True``。
        """
        if str(context.state.get("currentPlayerId") or "").strip() != context.playerId:
            return False
        if self._action_type == ACTION_PASS:
            if str(context.state.get("phase") or "") != PHASE_PLAYING:
                return False
            return parse_combo_info(context.state.get("lastPlay")) is not None
        expected_phase = _PHASE_BY_ACTION_TYPE.get(self._action_type)
        if expected_phase is None:
            return False
        if str(context.state.get("phase") or "") != expected_phase:
            return False
        if expected_phase == PHASE_CALLING:
            return can_decide_bid(context.state, context.playerId)
        if expected_phase == PHASE_ROBBING:
            return not uses_classic_bid_rules(context.state)
        player = (context.state.get("players") or {}).get(context.playerId) or {}
        decided_flag = {
            PHASE_SHOWING: "showCardsDecided",
            PHASE_DOUBLING: "doubleDecided",
        }.get(expected_phase)
        return decided_flag is not None and not bool(player.get(decided_flag))
