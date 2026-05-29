"""UNO 牌型规则注册表。"""

from typing import Any, Dict, List, Optional

from app.common.exceptions import ValidationException
from app.core.time_utils import now_ms
from app.modules.games.uno.schemas import (
    UnoCard,
    UnoDiscardRecentCard,
    UnoPendingDraw,
    UnoRuleContext,
)
from app.modules.games.uno.uno_card_rule import UnoCardRule
from app.modules.games.uno.uno_turn_rule import (
    advance_turn,
    count_active_players,
    peek_next_active_player,
)
from app.modules.strategy_turn.schemas import GameEvent

_VALID_COLORS = frozenset(("RED", "YELLOW", "BLUE", "GREEN"))
_RULE_KEY_DRAW_TWO = "DRAW_TWO"
_RULE_KEY_WILD_DRAW4 = "WILD_DRAW4"


def _has_pending_draw(context: UnoRuleContext) -> bool:
    """
    当前是否存在待结算抽牌。

    :param context: 规则上下文。
    :return: 存在为 ``True``。
    """
    return context.runtimeState.pendingDraw is not None


def _allow_draw_stacking(context: UnoRuleContext) -> bool:
    """
    房间是否允许 +2/+4 叠加。

    :param context: 规则上下文。
    :return: 允许为 ``True``。
    """
    return bool(context.roomConfig.get("allowDrawStacking"))


def _effective_color(context: UnoRuleContext) -> Optional[str]:
    """
    获取当前生效花色（优先 ``currentColor``，否则取顶牌花色）。

    :param context: 规则上下文。
    :return: 花色字符串；无则为 ``None``。
    """
    state = context.runtimeState
    if state.currentColor is not None:
        return state.currentColor
    top = state.topDiscard
    if top is not None and top.color is not None:
        return top.color
    return None


def _matches_color(card: UnoCard, context: UnoRuleContext) -> bool:
    """
    判断牌是否与当前生效花色相同。

    :param card: 待出牌。
    :param context: 规则上下文。
    :return: 相同为 ``True``。
    """
    color = _effective_color(context)
    return card.color is not None and color is not None and card.color == color


def _matches_top_number(card: UnoCard, context: UnoRuleContext) -> bool:
    """
    判断数字牌是否与顶牌点数相同。

    :param card: 待出牌。
    :param context: 规则上下文。
    :return: 相同为 ``True``。
    """
    top = context.runtimeState.topDiscard
    if top is None:
        return False
    return (
        card.numberValue is not None
        and top.numberValue is not None
        and card.numberValue == top.numberValue
    )


def _matches_top_card_type(card: UnoCard, context: UnoRuleContext) -> bool:
    """
    判断牌是否与顶牌 ``cardType`` 相同。

    :param card: 待出牌。
    :param context: 规则上下文。
    :return: 相同为 ``True``。
    """
    top = context.runtimeState.topDiscard
    if top is None:
        return False
    return card.cardType == top.cardType


def _matches_color_or_number(card: UnoCard, context: UnoRuleContext) -> bool:
    """
    判断是否与当前花色或顶牌点数匹配。

    :param card: 待出牌。
    :param context: 规则上下文。
    :return: 可匹配为 ``True``。
    """
    return _matches_color(card, context) or _matches_top_number(card, context)


def _matches_color_or_card_type(card: UnoCard, context: UnoRuleContext) -> bool:
    """
    判断是否与当前花色或顶牌 ``cardType`` 匹配。

    :param card: 待出牌。
    :param context: 规则上下文。
    :return: 可匹配为 ``True``。
    """
    return _matches_color(card, context) or _matches_top_card_type(card, context)


def _normalize_choose_color(action: Dict[str, Any]) -> Optional[str]:
    """
    从操作载荷解析并校验 ``chooseColor``。

    :param action: 玩家操作载荷。
    :return: 大写花色；无效或缺失时为 ``None``。
    """
    raw_color = action.get("chooseColor")
    if not isinstance(raw_color, str):
        return None
    normalized = raw_color.strip().upper()
    if normalized not in _VALID_COLORS:
        return None
    return normalized


def _require_choose_color(action: Dict[str, Any]) -> str:
    """
    解析万能牌必选花色，非法时抛出异常。

    :param action: 玩家操作载荷。
    :return: 大写花色。
    :raises ValueError: 缺少或非法 ``chooseColor`` 时抛出。
    """
    chosen = _normalize_choose_color(action)
    if chosen is None:
        raise ValueError("chooseColor must be one of RED, YELLOW, BLUE, GREEN")
    return chosen


def _apply_discard(context: UnoRuleContext, card: UnoCard) -> None:
    """
    将牌置入弃牌堆并更新顶牌。

    :param context: 规则上下文。
    :param card: 已出的牌。
    """
    state = context.runtimeState
    state.topDiscard = card
    state.discardPile.append(card)


def _append_event(
    context: UnoRuleContext,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """
    向上下文追加一条对局事件。

    :param context: 规则上下文。
    :param event_type: 事件类型。
    :param payload: 事件载荷。
    """
    event = GameEvent(
        eventType=event_type,
        sequence=context.nextEventSequence,
        playerId=context.actingPlayerId,
        payload=payload,
        createdAt=now_ms(),
    )
    context.newEvents.append(event)
    context.nextEventSequence = context.nextEventSequence + 1


def _record_discard_recent(
    context: UnoRuleContext,
    card: UnoCard,
    sequence: int,
) -> None:
    """
    记录最近有效出牌，仅保留最近两张。

    :param context: 规则上下文。
    :param card: 已出的牌。
    :param sequence: 对应出牌事件序号。
    :return: 无。
    """
    state = context.runtimeState
    recent = list(state.discardPileRecentCards)
    recent.append(
        UnoDiscardRecentCard(
            cardInstanceId=card.cardInstanceId,
            cardCode=card.cardCode,
            playerId=context.actingPlayerId,
            sequence=sequence,
        )
    )
    state.discardPileRecentCards = recent[-2:]


def _emit_card_played(context: UnoRuleContext, card: UnoCard, rule_key: str) -> None:
    """
    记录出牌事件。

    :param context: 规则上下文。
    :param card: 已出的牌。
    :param rule_key: 牌型规则键。
    """
    sequence = context.nextEventSequence
    _append_event(
        context,
        "uno.card.played",
        {
            "ruleKey": rule_key,
            "cardInstanceId": card.cardInstanceId,
            "cardCode": card.cardCode,
            "cardType": card.cardType,
            "color": card.color,
            "numberValue": card.numberValue,
        },
    )
    _record_discard_recent(context, card, sequence)


def _stack_or_set_pending_draw(
    context: UnoRuleContext,
    source_card_type: str,
    amount_delta: int,
) -> None:
    """
    叠加或新建待抽牌惩罚。

    :param context: 规则上下文。
    :param source_card_type: 来源牌型规则键。
    :param amount_delta: 本次增加张数。
    """
    state = context.runtimeState
    stackable = _allow_draw_stacking(context)
    pending = state.pendingDraw
    if pending is not None:
        if (
            source_card_type == _RULE_KEY_DRAW_TWO
            and pending.sourceCardType == _RULE_KEY_DRAW_TWO
            and stackable
        ):
            pending.amount = pending.amount + amount_delta
        elif (
            source_card_type == _RULE_KEY_WILD_DRAW4
            and stackable
            and (
                pending.sourceCardType == _RULE_KEY_DRAW_TWO
                or pending.sourceCardType == _RULE_KEY_WILD_DRAW4
            )
        ):
            pending.amount = pending.amount + amount_delta
            pending.sourceCardType = _RULE_KEY_WILD_DRAW4
        else:
            state.pendingDraw = UnoPendingDraw(
                amount=amount_delta,
                stackable=stackable,
                sourceCardType=source_card_type,
            )
    else:
        state.pendingDraw = UnoPendingDraw(
            amount=amount_delta,
            stackable=stackable,
            sourceCardType=source_card_type,
        )
    _append_event(
        context,
        "uno.pendingDraw.updated",
        {
            "amount": state.pendingDraw.amount,
            "sourceCardType": state.pendingDraw.sourceCardType,
            "stackable": state.pendingDraw.stackable,
        },
    )


def _can_stack_draw_two(context: UnoRuleContext) -> bool:
    """
    当前是否允许以 +2 叠加待抽。

    :param context: 规则上下文。
    :return: 允许为 ``True``。
    """
    pending = context.runtimeState.pendingDraw
    if pending is None:
        return False
    return (
        _allow_draw_stacking(context)
        and pending.sourceCardType == _RULE_KEY_DRAW_TWO
    )


def _can_play_wild_draw4_under_pending(context: UnoRuleContext) -> bool:
    """
    待抽场景下是否允许出 +4 万能牌。

    :param context: 规则上下文。
    :return: 允许为 ``True``。
    """
    pending = context.runtimeState.pendingDraw
    if pending is None:
        return False
    if not _allow_draw_stacking(context):
        return False
    source = pending.sourceCardType
    if source == _RULE_KEY_DRAW_TWO:
        return True
    if source == _RULE_KEY_WILD_DRAW4:
        return True
    return False


class _NumberCardRule(UnoCardRule):
    """数字牌规则。"""

    rule_key = "NUMBER"

    def can_play(self, context, card):
        """
        无待抽时，可按花色或点数与顶牌匹配出牌。

        :param context: 规则上下文。
        :param card: 待出牌。
        :return: 可出为 ``True``。
        """
        if _has_pending_draw(context):
            return False
        return _matches_color_or_number(card, context)

    def apply_effect(self, context, card, action):
        """
        更新顶牌与当前花色。

        :param context: 规则上下文。
        :param card: 已出的牌。
        :param action: 操作载荷。
        """
        _apply_discard(context, card)
        context.runtimeState.currentColor = card.color
        _emit_card_played(context, card, self.rule_key)


class _DisableCardRule(UnoCardRule):
    """禁用（跳过）牌规则。"""

    rule_key = "DISABLE"

    def can_play(self, context, card):
        """
        无待抽时，可按花色或 ``cardType`` 匹配出牌。

        :param context: 规则上下文。
        :param card: 待出牌。
        :return: 可出为 ``True``。
        """
        if _has_pending_draw(context):
            return False
        return _matches_color_or_card_type(card, context)

    def apply_effect(self, context, card, action):
        """
        禁用下一位仍在对局中的玩家回合。

        :param context: 规则上下文。
        :param card: 已出的牌。
        :param action: 操作载荷。
        """
        state = context.runtimeState
        _apply_discard(context, card)
        state.currentColor = card.color
        disabled_player_id = peek_next_active_player(state, 1)
        advance_turn(state, 2)
        state.effectAdvanceHandled = True
        _emit_card_played(context, card, self.rule_key)
        _append_event(
            context,
            "uno.player.disabled",
            {"disabledPlayerId": disabled_player_id},
        )


class _ReverseCardRule(UnoCardRule):
    """转向牌规则。"""

    rule_key = "REVERSE"

    def can_play(self, context, card):
        """
        无待抽时，可按花色或 ``cardType`` 匹配出牌。

        :param context: 规则上下文。
        :param card: 待出牌。
        :return: 可出为 ``True``。
        """
        if _has_pending_draw(context):
            return False
        return _matches_color_or_card_type(card, context)

    def apply_effect(self, context, card, action):
        """
        反转出牌方向后按新方向推进到下一位玩家。

        :param context: 规则上下文。
        :param card: 已出的牌。
        :param action: 操作载荷。
        """
        state = context.runtimeState
        _apply_discard(context, card)
        state.currentColor = card.color
        _emit_card_played(context, card, self.rule_key)
        state.playDirection = state.playDirection * -1
        next_player_id = advance_turn(state, 1)
        state.effectAdvanceHandled = True
        _append_event(
            context,
            "uno.direction.reversed",
            {
                "playDirection": state.playDirection,
                "nextPlayerId": next_player_id,
            },
        )


class _DrawTwoCardRule(UnoCardRule):
    """+2 牌规则。"""

    rule_key = "DRAW_TWO"

    def can_play(self, context, card):
        """
        普通场景按花色或 ``cardType`` 匹配；待抽叠加场景仅允许继续出 +2。

        :param context: 规则上下文。
        :param card: 待出牌。
        :return: 可出为 ``True``。
        """
        if _has_pending_draw(context):
            return _can_stack_draw_two(context)
        return _matches_color_or_card_type(card, context)

    def apply_effect(self, context, card, action):
        """
        待抽张数 +2。

        :param context: 规则上下文。
        :param card: 已出的牌。
        :param action: 操作载荷。
        """
        state = context.runtimeState
        _apply_discard(context, card)
        state.currentColor = card.color
        _stack_or_set_pending_draw(context, _RULE_KEY_DRAW_TWO, 2)
        _emit_card_played(context, card, self.rule_key)


class _WildCardRule(UnoCardRule):
    """万用牌规则。"""

    rule_key = "WILD"

    def can_play(self, context, card):
        """
        无待抽时可出。

        :param context: 规则上下文。
        :param card: 待出牌。
        :return: 可出为 ``True``。
        """
        return not _has_pending_draw(context)

    def apply_effect(self, context, card, action):
        """
        必须指定 ``chooseColor`` 并更新当前花色。

        :param context: 规则上下文。
        :param card: 已出的牌。
        :param action: 操作载荷。
        """
        chosen_color = _require_choose_color(action)
        state = context.runtimeState
        _apply_discard(context, card)
        state.currentColor = chosen_color
        _emit_card_played(context, card, self.rule_key)
        _append_event(
            context,
            "uno.color.chosen",
            {"chooseColor": chosen_color},
        )


class _WildDrawFourCardRule(UnoCardRule):
    """+4 万能牌规则。"""

    rule_key = "WILD_DRAW4"

    def can_play(self, context, card):
        """
        普通场景可出；待抽场景按来源牌型限制。

        :param context: 规则上下文。
        :param card: 待出牌。
        :return: 可出为 ``True``。
        """
        if _has_pending_draw(context):
            return _can_play_wild_draw4_under_pending(context)
        return True

    def apply_effect(self, context, card, action):
        """
        指定花色并使待抽张数 +4。

        :param context: 规则上下文。
        :param card: 已出的牌。
        :param action: 操作载荷。
        """
        chosen_color = _require_choose_color(action)
        state = context.runtimeState
        _apply_discard(context, card)
        state.currentColor = chosen_color
        _stack_or_set_pending_draw(context, _RULE_KEY_WILD_DRAW4, 4)
        _emit_card_played(context, card, self.rule_key)
        _append_event(
            context,
            "uno.color.chosen",
            {"chooseColor": chosen_color},
        )


_CARD_RULE_REGISTRY = {
    "NUMBER": _NumberCardRule(),
    "DISABLE": _DisableCardRule(),
    "REVERSE": _ReverseCardRule(),
    "DRAW_TWO": _DrawTwoCardRule(),
    "WILD": _WildCardRule(),
    "WILD_DRAW4": _WildDrawFourCardRule(),
}  # type: Dict[str, UnoCardRule]

def get_card_rule(rule_key: str) -> Optional[UnoCardRule]:
    """
    按规则键获取牌型规则。

    :param rule_key: 规则键，如 ``NUMBER``。
    :return: 规则实例；未注册时为 ``None``。
    """
    normalized = str(rule_key).strip()
    if not normalized:
        return None
    return _CARD_RULE_REGISTRY.get(normalized)


def get_card_rule_by_card_type(card_type: str) -> Optional[UnoCardRule]:
    """
    按种子 ``cardType`` 获取牌型规则。

    :param card_type: 牌型标识（NUMBER / DISABLE / REVERSE / DRAW_TWO / WILD / WILD_DRAW4）。
    :return: 规则实例；未注册时为 ``None``。
    """
    normalized = str(card_type).strip().upper()
    if not normalized:
        return None
    return get_card_rule(normalized)


def require_card_rule(rule_key: str) -> UnoCardRule:
    """
    获取牌型规则，未注册时抛出校验异常。

    :param rule_key: 规则键。
    :return: 规则实例。
    :raises ValidationException: 未注册时抛出。
    """
    rule = get_card_rule(rule_key)
    if rule is None:
        raise ValidationException("未注册的 UNO 牌型规则: {0}".format(rule_key))
    return rule
