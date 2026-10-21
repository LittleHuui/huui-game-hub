"""UNO 动作执行器。"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from app.common.exceptions import ValidationException
from app.core.time_utils import now_ms
from app.modules.game_impls.uno.schemas import UnoCard, UnoPlayerState, UnoRuleContext, UnoRuntimeState
from app.modules.game_impls.uno.uno_card_rule_registry import (
    _can_play_wild_draw4_under_pending,
    _can_stack_draw_two,
    get_card_rule_by_card_type,
)
from app.modules.game_impls.uno.uno_constants import ACTION_DRAW_CARD, ACTION_PASS_TURN, ACTION_PLAY_CARD
from app.modules.game_impls.uno.uno_deck_factory import draw_cards_from_pile
from app.modules.game_impls.uno.uno_event_factory import append_domain_event, build_rule_context
from app.modules.game_impls.uno.uno_finish_rule import mark_player_finished, sync_game_over_phase
from app.modules.game_impls.uno.uno_state_codec import dump_state, parse_state, resolve_room_config_from_state
from app.modules.game_impls.uno.uno_turn_rule import is_player_turn
from app.modules.game_seed.uno_seed import UNO_ONLINE_GAME_RULE_SEED
from app.modules.strategy_turn.schemas import DomainEventDraft, ResolvedGameAction


class UnoPlayCardPayload(BaseModel):
    """UNO 出牌归一载荷。"""

    model_config = ConfigDict(extra="forbid")
    cardInstanceId: str = Field(min_length=1)
    chooseColor: Optional[str] = None


class UnoDrawPayload(BaseModel):
    """UNO 摸牌归一载荷。"""

    model_config = ConfigDict(extra="forbid")
    mode: str = "normal"
    drawSource: Optional[str] = None


class UnoPassPayload(BaseModel):
    """UNO PASS 归一载荷。"""

    model_config = ConfigDict(extra="forbid")


class UnoActionExecutor(object):
    """UNO 已解析动作执行器。"""

    def apply_resolved_action(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
    ) -> Tuple[Dict[str, Any], List[DomainEventDraft]]:
        """
        校验并应用已解析动作。

        :param state: 当前对局状态。
        :param action: 已解析动作。
        :return: (新状态, 事件草稿列表)。
        """
        runtime_state = parse_state(state)
        if runtime_state.phase == "finished":
            raise ValidationException("对局已结束，无法继续操作")
        room_config = resolve_room_config_from_state(state)
        player_id = str(action.playerId or "").strip()
        if not is_player_turn(runtime_state, player_id):
            raise ValidationException("未轮到当前玩家")
        context = build_rule_context(runtime_state, room_config, player_id)
        action_type = str(action.actionType or "").strip()
        if action_type == ACTION_PLAY_CARD:
            self._apply_play_card(runtime_state, context, action, room_config)
            runtime_state.drewThisTurn = False
            runtime_state.lastDrawnCardInstanceId = None
        elif action_type == ACTION_DRAW_CARD:
            self._apply_draw_card(runtime_state, context, action, room_config)
        elif action_type == ACTION_PASS_TURN:
            self._apply_pass_turn(runtime_state, context)
            runtime_state.drewThisTurn = False
            runtime_state.lastDrawnCardInstanceId = None
        else:
            raise ValidationException("不支持的操作类型: {0}".format(action_type))
        sync_game_over_phase(runtime_state, room_config)
        dumped = dump_state(runtime_state)
        dumped["roomConfig"] = room_config
        return dumped, list(context.newEvents)

    def _apply_play_card(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
        action: ResolvedGameAction,
        room_config: Dict[str, Any],
    ) -> None:
        """
        执行出牌并应用牌型效果。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :param action: 已解析出牌动作。
        :param room_config: 房间配置。
        :return: 无。
        """
        payload = UnoPlayCardPayload.model_validate(action.payload or {}).model_dump(
            exclude_none=True,
        )
        card_instance_id = str(payload.get("cardInstanceId", "")).strip()
        if not card_instance_id:
            raise ValidationException("cardInstanceId 不能为空")
        player_id = str(action.playerId or "").strip()
        player_state = runtime_state.players.get(player_id)
        if player_state is None:
            raise ValidationException("玩家不在对局中")
        card = find_card_in_hand(player_state, card_instance_id)
        if card is None:
            raise ValidationException("手牌中不存在指定牌")
        assert_play_allowed_under_pending_draw(runtime_state, context, card)
        card = remove_card_from_hand(player_state, card_instance_id)
        rule = get_card_rule_by_card_type(card.cardType)
        if rule is None:
            raise ValidationException("未注册的牌型: {0}".format(card.cardType))
        runtime_state.effectAdvanceHandled = False
        previous_player_id = runtime_state.currentPlayerId
        rule.apply_effect(context, card, payload)
        if runtime_state.currentPlayerId != previous_player_id:
            runtime_state.effectAdvanceHandled = True
        if not player_state.handCards:
            mark_player_finished(runtime_state, player_id, now_ms())
            sync_game_over_phase(runtime_state, room_config)

    def _apply_draw_card(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
        action: ResolvedGameAction,
        room_config: Dict[str, Any],
    ) -> None:
        """
        执行抽牌：承担 ``pendingDraw``、主动抽牌或无牌可出时抽牌。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :param action: 已解析抽牌动作。
        :param room_config: 房间配置。
        :return: 无。
        """
        seed = UNO_ONLINE_GAME_RULE_SEED
        player_id = str(action.playerId or "").strip()
        player_state = runtime_state.players.get(player_id)
        if player_state is None:
            raise ValidationException("玩家不在对局中")
        payload = UnoDrawPayload.model_validate(action.payload or {}).model_dump(
            exclude_none=True,
        )
        pending = runtime_state.pendingDraw
        runtime_state.drawDecision = None
        runtime_state.drawSource = None
        if pending is not None:
            draw_count = pending.amount
            runtime_state.pendingDraw = None
        else:
            draw_count = 1
        draw_source = str(payload.get("drawSource", "")).strip() or None
        if draw_source is not None:
            runtime_state.drawSource = draw_source
        drawn_cards = draw_cards_from_pile(runtime_state, seed, draw_count, room_config)
        if drawn_cards:
            player_state.handCards.extend(drawn_cards)
        append_domain_event(
            context,
            "uno.cards.drawn",
            {
                "count": len(drawn_cards),
                "cardInstanceIds": [card.cardInstanceId for card in drawn_cards],
                "mode": payload.get("mode", "normal"),
            },
        )
        if pending is not None:
            runtime_state.drewThisTurn = False
            runtime_state.lastDrawnCardInstanceId = None
            runtime_state.effectAdvanceHandled = False
            runtime_state.drawDecision = "PENDING_DRAW_RESOLVED"
            return
        if not drawn_cards:
            runtime_state.drewThisTurn = False
            runtime_state.lastDrawnCardInstanceId = None
            runtime_state.effectAdvanceHandled = False
            runtime_state.drawDecision = "DRAW_EMPTY"
            return
        last_card = drawn_cards[-1]
        runtime_state.lastDrawnCardInstanceId = last_card.cardInstanceId
        post_context = build_rule_context(
            runtime_state,
            room_config,
            player_id,
        )
        allow_draw_and_play = bool(room_config.get("allowDrawAndPlay"))
        rule = get_card_rule_by_card_type(last_card.cardType)
        can_play_last = bool(rule is not None and rule.can_play(post_context, last_card))
        if draw_source != "voluntary" and allow_draw_and_play and can_play_last:
            runtime_state.drewThisTurn = True
            runtime_state.effectAdvanceHandled = True
            runtime_state.drawDecision = "FORCED_DRAW_AND_MAY_PLAY"
            return
        runtime_state.drewThisTurn = False
        runtime_state.effectAdvanceHandled = False
        runtime_state.drawDecision = "DRAW_END_TURN"

    def _apply_pass_turn(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
    ) -> None:
        """
        抽牌后放弃出牌并结束本回合。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :return: 无。
        """
        if not runtime_state.drewThisTurn:
            raise ValidationException("当前不可 PASS_TURN")
        UnoPassPayload.model_validate({})
        append_domain_event(context, "uno.turn.passed", {})
        runtime_state.effectAdvanceHandled = False


def find_card_in_hand(
    player_state: UnoPlayerState,
    card_instance_id: str,
) -> Optional[UnoCard]:
    """
    在手牌中查找指定实例，不移除。

    :param player_state: 玩家状态。
    :param card_instance_id: 牌实例 ID。
    :return: 找到的牌；不存在时为 ``None``。
    """
    for card in player_state.handCards:
        if card.cardInstanceId == card_instance_id:
            return card
    return None


def remove_card_from_hand(
    player_state: UnoPlayerState,
    card_instance_id: str,
) -> Optional[UnoCard]:
    """
    从手牌移除指定实例并返回该牌。

    :param player_state: 玩家状态。
    :param card_instance_id: 牌实例 ID。
    :return: 被移除的牌；不存在时为 ``None``。
    """
    for index, card in enumerate(player_state.handCards):
        if card.cardInstanceId == card_instance_id:
            return player_state.handCards.pop(index)
    return None


def assert_play_allowed_under_pending_draw(
    runtime_state: UnoRuntimeState,
    context: UnoRuleContext,
    card: UnoCard,
) -> None:
    """
    存在 ``pendingDraw`` 时二次校验出牌牌型，防止绕过枚举列表。

    :param runtime_state: 运行时状态。
    :param context: 规则上下文。
    :param card: 待打出的牌。
    :return: 无。
    :raises ValidationException: 牌型不允许时抛出。
    """
    if runtime_state.pendingDraw is None:
        return
    card_type = str(card.cardType).strip().upper()
    if card_type == "WILD":
        raise ValidationException("待抽牌惩罚未结算，不能打出该牌")
    if card_type == "DRAW_TWO":
        if not _can_stack_draw_two(context):
            raise ValidationException("待抽牌惩罚未结算，不能打出该牌")
        return
    if card_type == "WILD_DRAW4":
        if not _can_play_wild_draw4_under_pending(context):
            raise ValidationException("待抽牌惩罚未结算，不能打出该牌")
        return
    raise ValidationException("待抽牌惩罚未结算，不能打出该牌")
