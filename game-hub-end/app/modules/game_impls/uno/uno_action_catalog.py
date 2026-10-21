"""UNO 枚举动作目录与合法操作构建。"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional

from app.modules.game_impls.uno.schemas import UnoRuleContext, UnoRuntimeState
from app.modules.game_impls.uno.uno_card_rule_registry import get_card_rule_by_card_type
from app.modules.game_impls.uno.uno_constants import (
    ACTION_DRAW_CARD,
    ACTION_PASS_TURN,
    ACTION_PLAY_CARD,
    SEAT_LEFT,
    SEAT_SPECTATING,
    VALID_CHOOSE_COLORS,
    WILD_CARD_TYPES,
)
from app.modules.game_impls.uno.uno_event_factory import build_rule_context
from app.modules.game_impls.uno.uno_state_codec import parse_state, resolve_room_config_from_state
from app.modules.game_impls.uno.uno_turn_rule import is_player_turn


@dataclass(frozen=True)
class UnoEnumeratedOption(object):
    """UNO 枚举动作可选项。"""

    actionType: str
    actionId: str
    playerId: str
    payload: Mapping[str, Any]
    cardInstanceId: Optional[str] = None

    @property
    def selection(self) -> Dict[str, Any]:
        """为调用方构造独立选择元数据，避免修改目录选项。"""
        if self.cardInstanceId:
            return build_card_selection(self.cardInstanceId)
        return build_action_only_selection()


class UnoActionCatalog(object):
    """UNO 合法枚举动作目录。"""

    def list_enumerated_options(
        self,
        state: Dict[str, Any],
        player_id: str,
        action_type: str,
    ) -> List[UnoEnumeratedOption]:
        """
        列出指定动作类型的枚举可选项。

        :param state: 当前对局状态。
        :param player_id: 玩家 ID。
        :param action_type: 动作类型。
        :return: 枚举可选项列表。
        """
        normalized_type = str(action_type or "").strip()
        all_options = self.list_all_options(state, player_id)
        return [
            option
            for option in all_options
            if option.actionType == normalized_type
        ]

    def list_all_options(
        self,
        state: Dict[str, Any],
        player_id: str,
    ) -> List[UnoEnumeratedOption]:
        """
        列出当前玩家全部枚举可选项。

        :param state: 当前对局状态。
        :param player_id: 玩家 ID。
        :return: 枚举可选项列表。
        """
        runtime_state = parse_state(state)
        normalized_id = str(player_id).strip()
        if runtime_state.phase == "finished":
            return []
        player_state = runtime_state.players.get(normalized_id)
        if player_state is None:
            return []
        if player_state.seatStatus == SEAT_SPECTATING:
            return []
        if player_state.seatStatus == SEAT_LEFT:
            return []
        if not is_player_turn(runtime_state, normalized_id):
            return []
        room_config = resolve_room_config_from_state(state)
        context = build_rule_context(runtime_state, room_config, normalized_id)
        if runtime_state.pendingDraw is not None:
            return self._list_pending_draw_actions(runtime_state, context, normalized_id)
        if runtime_state.drawDecision in (
            "DRAW_END_TURN",
            "PENDING_DRAW_RESOLVED",
            "DRAW_EMPTY",
        ):
            return []
        if runtime_state.drewThisTurn:
            return self._list_post_draw_actions(runtime_state, context, normalized_id)
        return self._list_normal_turn_actions(runtime_state, context, normalized_id)

    def _list_normal_turn_actions(
        self,
        runtime_state: UnoRuntimeState,
        context: UnoRuleContext,
        player_id: str,
    ) -> List[UnoEnumeratedOption]:
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
            build_legal_action(
                ACTION_DRAW_CARD,
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
    ) -> List[UnoEnumeratedOption]:
        """
        存在 ``pendingDraw`` 时仅允许叠加出牌或承担累计摸牌。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :param player_id: 当前玩家 ID。
        :return: 合法操作列表。
        """
        actions = self._list_play_card_actions(runtime_state, context, player_id)
        actions.append(
            build_legal_action(
                ACTION_DRAW_CARD,
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
    ) -> List[UnoEnumeratedOption]:
        """
        抽牌后若可出牌则列出可出牌与 ``PASS_TURN``。

        :param runtime_state: 运行时状态。
        :param context: 规则上下文。
        :param player_id: 当前玩家 ID。
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
                build_legal_action(
                    ACTION_PASS_TURN,
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
    ) -> List[UnoEnumeratedOption]:
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
            if card.cardType in WILD_CARD_TYPES:
                for color in VALID_CHOOSE_COLORS:
                    payload = {
                        "cardInstanceId": card.cardInstanceId,
                        "chooseColor": color,
                    }
                    actions.append(
                        build_legal_action(
                            ACTION_PLAY_CARD,
                            player_id,
                            "{0}|{1}".format(card.cardInstanceId, color),
                            payload,
                            card_instance_id=card.cardInstanceId,
                        )
                    )
                continue
            actions.append(
                build_legal_action(
                    ACTION_PLAY_CARD,
                    player_id,
                    card.cardInstanceId,
                    {"cardInstanceId": card.cardInstanceId},
                    card_instance_id=card.cardInstanceId,
                )
            )
        return actions


def build_action_id(
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


def build_card_selection(card_instance_id: str) -> Dict[str, Any]:
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


def build_action_only_selection() -> Dict[str, Any]:
    """
    构建无牌选择的 ``selection``（摸牌、跳过等）。

    :return: selection 字典。
    """
    return {"mode": "ACTION_ONLY"}


def build_legal_action(
    action_type: str,
    player_id: str,
    token: str,
    payload: Dict[str, Any],
    card_instance_id: Optional[str] = None,
) -> UnoEnumeratedOption:
    """
    构造带稳定 actionId 与 selection 的枚举可选项。

    :param action_type: 操作类型。
    :param player_id: 玩家 ID。
    :param token: 局势 token。
    :param payload: 操作载荷。
    :param card_instance_id: 出牌时关联的牌实例 ID，可空。
    :return: 枚举可选项。
    """
    action_id = build_action_id(action_type, player_id, token)
    return UnoEnumeratedOption(
        actionType=action_type,
        actionId=action_id,
        playerId=player_id,
        payload=MappingProxyType(dict(payload)),
        cardInstanceId=card_instance_id,
    )
