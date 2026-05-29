"""UNO 策略回合制规则引擎。"""

from typing import Any, Dict, List, Optional, Set

from app.common.exceptions import ValidationException
from app.core.time_utils import now_ms
from app.modules.game_seed.schemas import resolve_room_config_defaults
from app.modules.game_seed.uno_seed import UNO_ONLINE_GAME_RULE_SEED
from app.modules.games.uno.schemas import (
    UnoCard,
    UnoDiscardRecentCard,
    UnoPlayerState,
    UnoRuleContext,
    UnoRuntimeState,
)
from app.modules.games.uno.uno_card_rule_registry import (
    _can_play_wild_draw4_under_pending,
    _can_stack_draw_two,
    get_card_rule_by_card_type,
)
from app.modules.games.uno.uno_deck_factory import (
    build_initial_draw_pile,
    draw_cards_from_pile,
    pop_starting_discard_card,
    resolve_deck_set_count,
)
from app.modules.games.uno.uno_finish_rule import (
    mark_player_finished,
    sync_game_over_phase,
)
from app.modules.games.uno.uno_turn_rule import advance_turn, is_player_turn, stamp_turn_clock
from app.modules.strategy_turn.rule_engine import StrategyTurnRuleEngine
from app.modules.strategy_turn.schemas import (
    GameAction,
    GameEvent,
    GameView,
    LegalAction,
    StrategyTurnRuntimeRule,
)

_ACTION_PLAY_CARD = "PLAY_CARD"
_ACTION_DRAW_CARD = "DRAW_CARD"
_ACTION_PASS_TURN = "PASS_TURN"
_SEAT_PLAYING = "PLAYING"
_SEAT_SPECTATING = "SPECTATING"
_SEAT_LEFT = "LEFT"
_WILD_CARD_TYPES = frozenset(("WILD", "WILD_DRAW4"))
_VALID_CHOOSE_COLORS = ("RED", "YELLOW", "BLUE", "GREEN")
_STATE_EVENTS_KEY = "lastActionEvents"


class UnoRuleEngine(StrategyTurnRuleEngine):
    """UNO 规则引擎：开局、合法操作、出牌、回合推进与视图。"""

    def build_initial_state(
        self,
        runtime_rule: StrategyTurnRuntimeRule,
    ) -> Dict[str, Any]:
        """
        根据玩家列表生成初始状态并完成发牌。

        :param runtime_rule: 运行时规则。
        :return: 对局状态字典。
        """
        seed = UNO_ONLINE_GAME_RULE_SEED
        player_ids = list(runtime_rule.playerIds)
        room_config = self._resolve_room_config(runtime_rule)
        ai_player_ids = self._resolve_ai_player_ids(runtime_rule)
        deck_set_count = resolve_deck_set_count(seed, len(player_ids))
        draw_pile = build_initial_draw_pile(seed, len(player_ids), shuffle=True)
        initial_hand_count = int(room_config.get("initialHandCount", 7))
        dealing_state = UnoRuntimeState(
            phase="playing",
            playerIds=player_ids,
            players={},
            drawPile=draw_pile,
            discardPile=[],
            currentPlayerId=player_ids[0],
            deckSetCount=deck_set_count,
        )
        players = {}
        for player_id in player_ids:
            hand_cards = draw_cards_from_pile(
                dealing_state,
                seed,
                initial_hand_count,
                room_config,
            )
            players[player_id] = UnoPlayerState(
                playerId=player_id,
                handCards=hand_cards,
                seatStatus=_SEAT_PLAYING,
                isAi=player_id in ai_player_ids,
                isFinished=False,
            )
        runtime_state = UnoRuntimeState(
            phase="playing",
            playerIds=player_ids,
            players=players,
            drawPile=dealing_state.drawPile,
            discardPile=[],
            topDiscard=None,
            currentPlayerId=self._first_playing_player_id(player_ids, players),
            playDirection=1,
            pendingDraw=None,
            currentColor=None,
            rankings=[],
            deckSetCount=deck_set_count,
        )
        top_discard = pop_starting_discard_card(runtime_state.drawPile)
        if top_discard is not None:
            runtime_state.topDiscard = top_discard
            runtime_state.currentColor = top_discard.color
            runtime_state.discardPile.append(top_discard)
            runtime_state.discardPileRecentCards = [
                UnoDiscardRecentCard(
                    cardInstanceId=top_discard.cardInstanceId,
                    cardCode=top_discard.cardCode,
                    playerId=None,
                    sequence=0,
                )
            ]
        stamp_turn_clock(runtime_state)
        sync_game_over_phase(runtime_state, room_config)
        dumped = self._dump_state(runtime_state)
        dumped["roomConfig"] = room_config
        return dumped

    def list_legal_actions(
        self,
        state: Dict[str, Any],
        player_id: str,
    ) -> List[LegalAction]:
        """
        列出指定玩家在当回合可执行的合法操作。

        :param state: 当前对局状态。
        :param player_id: 玩家 ID。
        :return: 合法操作列表。
        """
        runtime_state = self._parse_state(state)
        normalized_id = str(player_id).strip()
        if runtime_state.phase == "finished":
            return []
        player_state = runtime_state.players.get(normalized_id)
        if player_state is None:
            return []
        if player_state.seatStatus == _SEAT_SPECTATING:
            return []
        if player_state.seatStatus == _SEAT_LEFT:
            return []
        if not is_player_turn(runtime_state, normalized_id):
            return []
        room_config = self._resolve_room_config_from_state(state)
        context = self._build_rule_context(runtime_state, room_config, normalized_id)
        if runtime_state.pendingDraw is not None:
            return self._list_pending_draw_actions(runtime_state, context, normalized_id)
        if runtime_state.drawDecision in (
            "DRAW_END_TURN",
            "PENDING_DRAW_RESOLVED",
            "DRAW_EMPTY",
        ):
            return []
        if runtime_state.drewThisTurn:
            return self._list_post_draw_actions(runtime_state, context, normalized_id, room_config)
        return self._list_normal_turn_actions(runtime_state, context, normalized_id)

    def apply_action(
        self,
        state: Dict[str, Any],
        action: GameAction,
    ) -> Dict[str, Any]:
        """
        校验并应用玩家操作。

        :param state: 当前对局状态。
        :param action: 玩家操作。
        :return: 应用后的对局状态。
        """
        runtime_state = self._parse_state(state)
        if runtime_state.phase == "finished":
            raise ValidationException("对局已结束，无法继续操作")
        room_config = self._resolve_room_config_from_state(state)
        player_id = str(action.playerId).strip()
        legal_actions = self.list_legal_actions(state, player_id)
        matched = self._match_legal_action(action, legal_actions)
        context = self._build_rule_context(
            runtime_state,
            room_config,
            player_id,
            event_sequence=self._read_event_sequence(state),
        )
        if matched.actionType == _ACTION_PLAY_CARD:
            self._apply_play_card(runtime_state, context, matched, room_config)
            runtime_state.drewThisTurn = False
            runtime_state.lastDrawnCardInstanceId = None
        elif matched.actionType == _ACTION_DRAW_CARD:
            self._apply_draw_card(runtime_state, context, matched, room_config)
        elif matched.actionType == _ACTION_PASS_TURN:
            self._apply_pass_turn(runtime_state, context)
            runtime_state.drewThisTurn = False
            runtime_state.lastDrawnCardInstanceId = None
        else:
            raise ValidationException("不支持的操作类型: {0}".format(matched.actionType))
        sync_game_over_phase(runtime_state, room_config)
        dumped = self._dump_state(runtime_state, context.newEvents)
        dumped["roomConfig"] = room_config
        return dumped

    def advance(
        self,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        在操作结算后推进到下一位仍在 PLAYING 座位的玩家。

        :param state: 当前对局状态。
        :return: 推进后的对局状态。
        """
        runtime_state = self._parse_state(state)
        room_config = self._resolve_room_config_from_state(state)
        runtime_state.drawDecision = None
        runtime_state.drawSource = None
        if runtime_state.phase == "finished":
            dumped = self._dump_state(runtime_state)
            dumped["roomConfig"] = room_config
            return dumped
        if runtime_state.drewThisTurn:
            dumped = self._dump_state(runtime_state)
            dumped["roomConfig"] = room_config
            return dumped
        if runtime_state.effectAdvanceHandled:
            runtime_state.effectAdvanceHandled = False
            dumped = self._dump_state(runtime_state)
            dumped["roomConfig"] = room_config
            return dumped
        previous_player_id = runtime_state.currentPlayerId
        next_player_id = advance_turn(runtime_state, 1)
        if next_player_id != previous_player_id:
            context = self._build_rule_context(
                runtime_state,
                room_config,
                next_player_id,
                event_sequence=self._read_event_sequence(state),
            )
            self._append_engine_event(
                context,
                "uno.turn.advanced",
                {
                    "previousPlayerId": previous_player_id,
                    "nextPlayerId": next_player_id,
                },
            )
            dumped = self._dump_state(runtime_state, context.newEvents)
            dumped["roomConfig"] = room_config
            return dumped
        dumped = self._dump_state(runtime_state)
        dumped["roomConfig"] = room_config
        return dumped

    def build_view(
        self,
        state: Dict[str, Any],
        viewer_player_id: str,
    ) -> GameView:
        """
        构建含 ``publicState`` / ``privateState`` 的玩家视图。

        :param state: 当前对局状态。
        :param viewer_player_id: 视角玩家 ID。
        :return: 对局视图。
        """
        runtime_state = self._parse_state(state)
        viewer_id = str(viewer_player_id).strip()
        public_state = self._build_public_state(runtime_state)
        private_state = self._build_private_state(runtime_state, viewer_id)
        if viewer_id == runtime_state.currentPlayerId:
            legal_actions = self.list_legal_actions(state, viewer_id)
        else:
            legal_actions = []
        return GameView(
            gameCode="uno",
            viewerPlayerId=viewer_id,
            phase=runtime_state.phase,
            currentPlayerId=runtime_state.currentPlayerId,
            legalActions=legal_actions,
            publicState=public_state,
            privateState=private_state,
            isGameOver=runtime_state.phase == "finished",
        )

    def is_game_over(
        self,
        state: Dict[str, Any],
    ) -> bool:
        """
        判断对局是否结束。

        :param state: 当前对局状态。
        :return: 已结束为 ``True``。
        """
        runtime_state = self._parse_state(state)
        return runtime_state.phase == "finished"

    def _list_normal_turn_actions(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
        player_id: str,
    ) -> List[LegalAction]:
        """
        无待抽惩罚且本回合未抽牌时的合法操作。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :param player_id: 当前玩家 ID。
        :return: 合法操作列表。
        """
        actions = self._list_play_card_actions(runtime_state, context, player_id)
        has_playable = bool(actions)
        if has_playable:
            draw_payload = {
                "mode": "normal",
                "drawSource": "voluntary",
            }
        else:
            draw_payload = {
                "mode": "normal",
                "drawSource": "forcedNoPlayable",
            }
        actions.append(
            self._build_legal_action(
                _ACTION_DRAW_CARD,
                player_id,
                "draw",
                draw_payload,
            )
        )
        if not has_playable:
            return [actions[-1]]
        return actions

    def _list_pending_draw_actions(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
        player_id: str,
    ) -> List[LegalAction]:
        """
        存在 ``pendingDraw`` 时仅允许叠加出牌或承担累计摸牌。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :param player_id: 当前玩家 ID。
        :return: 合法操作列表。
        """
        actions = self._list_play_card_actions(runtime_state, context, player_id)
        actions.append(
            self._build_legal_action(
                _ACTION_DRAW_CARD,
                player_id,
                "pending",
                {"mode": "pending", "drawSource": "pendingDraw"},
            )
        )
        return actions

    def _list_post_draw_actions(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
        player_id: str,
        room_config: Dict[str, Any],
    ) -> List[LegalAction]:
        """
        抽牌后若可出牌则列出可出牌与 ``PASS_TURN``。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :param player_id: 当前玩家 ID。
        :param room_config: 房间配置。
        :return: 合法操作列表。
        """
        actions = self._list_play_card_actions(
            runtime_state,
            context,
            player_id,
            restrict_to_last_drawn=True,
        )
        if actions:
            actions.append(
                self._build_legal_action(
                    _ACTION_PASS_TURN,
                    player_id,
                    "pass",
                    {},
                )
            )
        return actions

    def _list_play_card_actions(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
        player_id: str,
        restrict_to_last_drawn: bool = False,
    ) -> List[LegalAction]:
        """
        枚举当前可出的 ``PLAY_CARD`` 操作。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :param player_id: 当前玩家 ID。
        :param restrict_to_last_drawn: 是否仅允许打出本回合刚抽到的牌。
        :return: 合法出牌操作列表。
        """
        player_state = runtime_state.players.get(player_id)
        if player_state is None:
            return []
        actions = []
        for card in player_state.handCards:
            if restrict_to_last_drawn:
                if card.cardInstanceId != runtime_state.lastDrawnCardInstanceId:
                    continue
            rule = get_card_rule_by_card_type(card.cardType)
            if rule is None or not rule.can_play(context, card):
                continue
            if card.cardType in _WILD_CARD_TYPES:
                for color in _VALID_CHOOSE_COLORS:
                    payload = {
                        "cardInstanceId": card.cardInstanceId,
                        "chooseColor": color,
                    }
                    actions.append(
                        self._build_legal_action(
                            _ACTION_PLAY_CARD,
                            player_id,
                            "{0}|{1}".format(card.cardInstanceId, color),
                            payload,
                            card_instance_id=card.cardInstanceId,
                        )
                    )
                continue
            actions.append(
                self._build_legal_action(
                    _ACTION_PLAY_CARD,
                    player_id,
                    card.cardInstanceId,
                    {"cardInstanceId": card.cardInstanceId},
                    card_instance_id=card.cardInstanceId,
                )
            )
        return actions

    def _apply_play_card(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
        legal_action: LegalAction,
        room_config: Dict[str, Any],
    ) -> None:
        """
        执行出牌并应用牌型效果。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :param legal_action: 已匹配的合法操作。
        :param room_config: 房间配置。
        """
        payload = legal_action.payload
        card_instance_id = str(payload.get("cardInstanceId", "")).strip()
        if not card_instance_id:
            raise ValidationException("cardInstanceId 不能为空")
        player_state = runtime_state.players.get(legal_action.playerId)
        if player_state is None:
            raise ValidationException("玩家不在对局中")
        card = self._find_card_in_hand(player_state, card_instance_id)
        if card is None:
            raise ValidationException("手牌中不存在指定牌")
        self._assert_play_allowed_under_pending_draw(runtime_state, context, card)
        card = self._remove_card_from_hand(player_state, card_instance_id)
        rule = get_card_rule_by_card_type(card.cardType)
        if rule is None:
            raise ValidationException("未注册的牌型: {0}".format(card.cardType))
        runtime_state.effectAdvanceHandled = False
        previous_player_id = runtime_state.currentPlayerId
        rule.apply_effect(context, card, payload)
        if runtime_state.currentPlayerId != previous_player_id:
            runtime_state.effectAdvanceHandled = True
        if not player_state.handCards:
            mark_player_finished(runtime_state, legal_action.playerId, now_ms())
            sync_game_over_phase(runtime_state, room_config)

    def _apply_draw_card(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
        legal_action: LegalAction,
        room_config: Dict[str, Any],
    ) -> None:
        """
        执行抽牌：承担 ``pendingDraw``、主动抽牌或无牌可出时抽牌。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :param legal_action: 已匹配的合法操作。
        :param room_config: 房间配置。
        """
        seed = UNO_ONLINE_GAME_RULE_SEED
        player_state = runtime_state.players.get(legal_action.playerId)
        if player_state is None:
            raise ValidationException("玩家不在对局中")
        pending = runtime_state.pendingDraw
        runtime_state.drawDecision = None
        runtime_state.drawSource = None
        if pending is not None:
            draw_count = pending.amount
            runtime_state.pendingDraw = None
        else:
            draw_count = 1
        draw_source = str(legal_action.payload.get("drawSource", "")).strip() or None
        if draw_source is not None:
            runtime_state.drawSource = draw_source
        drawn_cards = draw_cards_from_pile(runtime_state, seed, draw_count, room_config)
        if drawn_cards:
            player_state.handCards.extend(drawn_cards)
        self._append_engine_event(
            context,
            "uno.cards.drawn",
            {
                "count": len(drawn_cards),
                "cardInstanceIds": [card.cardInstanceId for card in drawn_cards],
                "mode": legal_action.payload.get("mode", "normal"),
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
        post_context = self._build_rule_context(
            runtime_state,
            room_config,
            legal_action.playerId,
            event_sequence=context.nextEventSequence,
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
        """
        if not runtime_state.drewThisTurn:
            raise ValidationException("当前不可 PASS_TURN")
        self._append_engine_event(context, "uno.turn.passed", {})
        runtime_state.effectAdvanceHandled = False

    def _match_legal_action(
        self,
        action: GameAction,
        legal_actions: List[LegalAction],
    ) -> LegalAction:
        """
        按 ``actionId`` 匹配合法操作，并以服务端 ``legalAction`` 为准。

        :param action: 玩家提交的操作。
        :param legal_actions: 当前合法操作列表。
        :return: 匹配到的合法操作。
        """
        normalized_id = str(action.actionId).strip()
        if not normalized_id:
            raise ValidationException("actionId 不能为空")
        matched = None
        for legal_action in legal_actions:
            if legal_action.actionId == normalized_id:
                matched = legal_action
                break
        if matched is None:
            raise ValidationException("actionId 与当前局势不匹配")
        return matched

    def _build_card_selection(self, card_instance_id: str) -> Dict[str, Any]:
        """
        构建出牌类 ``selection``（单张牌实例）。

        :param card_instance_id: 牌实例 ID。
        :return: selection 字典。
        """
        return {
            "mode": "CARD_SET",
            "matchPolicy": {"matchFields": ["cardInstanceId"]},
            "requiredGroups": [
                {
                    "groupType": "SINGLE",
                    "count": 1,
                    "matchValue": {"cardInstanceId": card_instance_id},
                }
            ],
        }

    def _build_action_only_selection(self) -> Dict[str, Any]:
        """
        构建无牌选择的 ``selection``（摸牌、跳过等）。

        :return: selection 字典。
        """
        return {"mode": "ACTION_ONLY"}

    def _build_legal_action(
        self,
        action_type: str,
        player_id: str,
        token: str,
        payload: Dict[str, Any],
        card_instance_id: Optional[str] = None,
    ) -> LegalAction:
        """
        构造带稳定 ``actionId`` 与 ``selection`` 的合法操作。

        :param action_type: 操作类型。
        :param player_id: 玩家 ID。
        :param token: 局势 token。
        :param payload: 操作载荷（由服务端在匹配后使用）。
        :param card_instance_id: 出牌时关联的牌实例 ID，可空。
        :return: 合法操作。
        """
        action_id = self._build_action_id(action_type, player_id, token)
        if card_instance_id:
            selection = self._build_card_selection(card_instance_id)
        else:
            selection = self._build_action_only_selection()
        return LegalAction(
            actionType=action_type,
            actionId=action_id,
            playerId=player_id,
            payload=dict(payload),
            selection=selection,
        )

    def _build_action_id(
        self,
        action_type: str,
        player_id: str,
        token: str,
    ) -> str:
        """
        根据当前局势生成稳定的 actionId。

        :param action_type: 操作类型。
        :param player_id: 玩家 ID。
        :param token: 局势 token。
        :return: actionId。
        """
        return "{0}|{1}|{2}".format(action_type, player_id, token)

    def _build_rule_context(
        self,
        runtime_state: UnoRuntimeState,
        room_config: Dict[str, Any],
        acting_player_id: str,
        event_sequence: int = 0,
    ) -> UnoRuleContext:
        """
        构建牌型规则判定上下文。

        :param runtime_state: 运行时状态。
        :param room_config: 房间配置。
        :param acting_player_id: 当前行动玩家 ID。
        :param event_sequence: 事件起始序号。
        :return: 规则上下文。
        """
        return UnoRuleContext(
            runtimeState=runtime_state,
            runtimeRule={},
            roomConfig=room_config,
            actingPlayerId=acting_player_id,
            newEvents=[],
            nextEventSequence=event_sequence,
        )

    def _append_engine_event(
        self,
        context: UnoRuleContext,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        向上下文追加一条引擎事件。

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

    def _assert_play_allowed_under_pending_draw(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
        card: UnoCard,
    ) -> None:
        """
        存在 ``pendingDraw`` 时二次校验出牌牌型，防止绕过 ``list_legal_actions``。

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

    def _find_card_in_hand(
        self,
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

    def _remove_card_from_hand(
        self,
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

    def _first_playing_player_id(
        self,
        player_ids: List[str],
        players: Dict[str, UnoPlayerState],
    ) -> str:
        """
        取座位顺序中首位 PLAYING 玩家作为开局当前玩家。

        :param player_ids: 玩家顺序。
        :param players: 玩家状态映射。
        :return: 当前玩家 ID。
        """
        for player_id in player_ids:
            player_state = players.get(player_id)
            if player_state is not None and player_state.seatStatus == _SEAT_PLAYING:
                return player_id
        return player_ids[0]

    def _resolve_ai_player_ids(self, runtime_rule: StrategyTurnRuntimeRule) -> Set[str]:
        """
        从运行时规则配置解析 AI 玩家 ID 集合。

        :param runtime_rule: 运行时规则。
        :return: AI 玩家 ID 集合。
        """
        config = runtime_rule.config if isinstance(runtime_rule.config, dict) else {}
        raw_ids = config.get("aiPlayerIds", [])
        if not isinstance(raw_ids, list):
            return set()
        result = set()
        for item in raw_ids:
            normalized = str(item).strip()
            if normalized:
                result.add(normalized)
        return result

    def _resolve_room_config(self, runtime_rule: StrategyTurnRuntimeRule) -> Dict[str, Any]:
        """
        合并运行时规则中的房间配置与种子默认值。

        :param runtime_rule: 运行时规则。
        :return: 房间配置字典。
        """
        merged = resolve_room_config_defaults(UNO_ONLINE_GAME_RULE_SEED)
        if isinstance(runtime_rule.config, dict):
            merged.update(runtime_rule.config)
        return merged

    def _resolve_room_config_from_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        从状态字典中的运行时规则快照解析房间配置。

        :param state: 对局状态字典。
        :return: 房间配置字典。
        """
        merged = resolve_room_config_defaults(UNO_ONLINE_GAME_RULE_SEED)
        runtime_rule = state.get("runtimeRule")
        if isinstance(runtime_rule, dict):
            config = runtime_rule.get("config")
            if isinstance(config, dict):
                merged.update(config)
        room_config = state.get("roomConfig")
        if isinstance(room_config, dict):
            merged.update(room_config)
        return merged

    def _build_public_state(self, runtime_state: UnoRuntimeState) -> Dict[str, Any]:
        """
        构建所有玩家可见的公有状态。

        :param runtime_state: 运行时状态。
        :return: 公有状态字典。
        """
        player_summaries = []
        for player_id in runtime_state.playerIds:
            player_state = runtime_state.players.get(player_id)
            if player_state is None:
                continue
            player_summaries.append(
                {
                    "playerId": player_id,
                    "handCount": len(player_state.handCards),
                    "seatStatus": player_state.seatStatus,
                    "isAi": player_state.isAi,
                    "isFinished": player_state.isFinished,
                    "finishRank": player_state.finishRank,
                }
            )
        pending_draw = None
        if runtime_state.pendingDraw is not None:
            pending_draw = runtime_state.pendingDraw.model_dump()
        discard_top_card = None
        if runtime_state.topDiscard is not None:
            discard_top_card = runtime_state.topDiscard.model_dump()
        return {
            "phase": runtime_state.phase,
            "playerIds": list(runtime_state.playerIds),
            "players": player_summaries,
            "drawPileCount": len(runtime_state.drawPile),
            "discardPileCount": len(runtime_state.discardPile),
            "discardTopCard": discard_top_card,
            "currentPlayerId": runtime_state.currentPlayerId,
            "playDirection": runtime_state.playDirection,
            "pendingDraw": pending_draw,
            "currentColor": runtime_state.currentColor,
            "rankings": [item.model_dump() for item in runtime_state.rankings],
            "completionOrder": [item.playerId for item in runtime_state.rankings],
            "deckSetCount": runtime_state.deckSetCount,
            "discardPileRecentCards": [
                item.model_dump() for item in runtime_state.discardPileRecentCards
            ],
            "currentTurnStartedAt": runtime_state.currentTurnStartedAt,
            "turnTimeoutSeconds": runtime_state.turnTimeoutSeconds,
            "currentTurnDeadlineAt": runtime_state.currentTurnDeadlineAt,
        }

    def _build_private_state(
        self,
        runtime_state: UnoRuntimeState,
        viewer_player_id: str,
    ) -> Dict[str, Any]:
        """
        构建仅视角玩家可见的私有状态。

        :param runtime_state: 运行时状态。
        :param viewer_player_id: 视角玩家 ID。
        :return: 私有状态字典。
        """
        player_state = runtime_state.players.get(viewer_player_id)
        hand_cards = []
        if player_state is not None:
            hand_cards = [card.model_dump() for card in player_state.handCards]
        return {
            "handCards": hand_cards,
        }

    def _parse_state(self, state: Dict[str, Any]) -> UnoRuntimeState:
        """
        将对局状态字典解析为 ``UnoRuntimeState``。

        :param state: 状态字典。
        :return: 运行时状态模型。
        """
        cleaned = dict(state)
        cleaned.pop(_STATE_EVENTS_KEY, None)
        cleaned.pop("roomConfig", None)
        cleaned.pop("eventSequence", None)
        return UnoRuntimeState.model_validate(cleaned)

    def _dump_state(
        self,
        runtime_state: UnoRuntimeState,
        new_events: Optional[List[GameEvent]] = None,
    ) -> Dict[str, Any]:
        """
        序列化运行时状态并附带本次产生的事件。

        :param runtime_state: 运行时状态。
        :param new_events: 新事件列表，可空。
        :return: 状态字典。
        """
        dumped = runtime_state.model_dump()
        if new_events:
            dumped[_STATE_EVENTS_KEY] = [event.model_dump() for event in new_events]
        return dumped

    def _read_event_sequence(self, state: Dict[str, Any]) -> int:
        """
        读取状态中记录的下一条事件序号。

        :param state: 状态字典。
        :return: 事件序号。
        """
        raw_value = state.get("eventSequence", 0)
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return 0
