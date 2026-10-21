"""斗地主状态投影器。"""

from typing import Any, Dict, List

from app.modules.game_impls.doudizhu.doudizhu_constants import PHASE_FINISHED, PHASE_SETTLEMENT
from app.modules.game_impls.doudizhu.doudizhu_state_codec import parse_state
from app.modules.game_impls.doudizhu.doudizhu_state_helpers import parse_cards
from app.modules.strategy_turn.lifecycle import GameStateProjector
from app.modules.strategy_turn.schemas import GameStateProjection


class DoudizhuStateProjector(GameStateProjector):
    """斗地主对局状态投影器。"""

    def project(
        self,
        state: Dict[str, Any],
        viewer_player_id: str,
        current_time_ms: int = None,
    ) -> GameStateProjection:
        """
        构建指定玩家的可见状态投影。

        :param state: 当前对局状态。
        :param viewer_player_id: 视角玩家 ID。
        :return: 状态投影。
        """
        del current_time_ms
        state = parse_state(state)
        viewer_id = str(viewer_player_id).strip()
        phase = str(state.get("phase") or "")
        public_players = self._build_public_players(state, viewer_id)
        public_state = {
            "players": public_players,
            "gameState": self._build_public_game_state(state),
        }
        private_state = self._build_private_state(state, viewer_id)
        return GameStateProjection(
            phase=phase,
            currentPlayerId=state.get("currentPlayerId"),
            publicState=public_state,
            privateState=private_state,
        )

    def _build_public_players(
        self,
        state: Dict[str, Any],
        viewer_player_id: str,
    ) -> List[Dict[str, Any]]:
        """
        构建公开玩家列表。

        :param state: 对局状态。
        :param viewer_player_id: 视角玩家 ID。
        :return: 公开玩家信息列表。
        """
        del viewer_player_id
        phase = str(state.get("phase") or "")
        reveal_all = phase in (PHASE_SETTLEMENT, PHASE_FINISHED)
        players = state.get("players") or {}
        public_players = []
        for player_id in list(state.get("playerIds") or []):
            player_raw = players.get(player_id) or {}
            hand_cards = parse_cards(player_raw.get("handCards") or [])
            visible_cards = []
            if bool(player_raw.get("showCards")) or reveal_all:
                visible_cards = [card.model_dump() for card in hand_cards]
            public_players.append(
                {
                    "playerId": player_id,
                    "seatIndex": player_raw.get("seatIndex"),
                    "role": player_raw.get("role"),
                    "isLandlord": bool(player_raw.get("isLandlord")),
                    "handCount": int(player_raw.get("handCount") or len(hand_cards)),
                    "showCards": bool(player_raw.get("showCards")),
                    "visibleCards": visible_cards,
                    "isDoubled": bool(player_raw.get("isDoubled")),
                    "playCount": int(player_raw.get("playCount") or 0),
                    "passCount": int(player_raw.get("passCount") or 0),
                }
            )
        return public_players

    def _build_public_game_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建公开对局状态。

        :param state: 对局状态。
        :return: 公开 gameState。
        """
        return {
            "phase": state.get("phase"),
            "currentPlayerId": state.get("currentPlayerId"),
            "landlordPlayerId": state.get("landlordPlayerId"),
            "bottomCards": state.get("bottomCards") if state.get("bottomCardsRevealed") else [],
            "bottomCardsRevealed": bool(state.get("bottomCardsRevealed")),
            "enableLaizi": bool(state.get("enableLaizi")),
            "laiziRankCode": state.get("laiziRankCode"),
            "laiziRankValue": state.get("laiziRankValue"),
            "laiziCardCodes": list(state.get("laiziCardCodes") or []),
            "lastPlay": state.get("lastPlay"),
            "lastPlayCards": list(state.get("lastPlayCards") or []),
            "lastPlayPlayerId": state.get("lastPlayPlayerId"),
            "lastActionEvent": self._build_public_last_action_event(state),
            "passPlayerIds": list(state.get("passPlayerIds") or []),
            "consecutivePassCount": int(state.get("consecutivePassCount") or 0),
            "roundLeadPlayerId": state.get("roundLeadPlayerId"),
            "globalMultiplier": int(state.get("globalMultiplier") or 1),
            "multiplierDetails": list(state.get("multiplierDetails") or []),
            "bombCount": int(state.get("bombCount") or 0),
            "rocketCount": int(state.get("rocketCount") or 0),
            "currentTurnStartedAt": state.get("currentTurnStartedAt"),
            "currentTurnDeadlineAt": state.get("currentTurnDeadlineAt"),
            "winnerRole": state.get("winnerRole"),
            "springType": state.get("springType"),
            "settlement": state.get("settlement"),
            "callingStartPlayerId": state.get("callingStartPlayerId"),
            "callingStartSeatIndex": state.get("callingStartSeatIndex"),
            "allowSingleAttachment": bool(
                (state.get("roomConfig") or {}).get("allowSingleAttachment", True)
            ),
        }

    @staticmethod
    def _build_public_last_action_event(state: Dict[str, Any]) -> Dict[str, str]:
        """
        构建最近竞价动作的公开展示事件。

        :param state: 当前对局状态。
        :return: 仅包含操作者和动作类型的公开事件；不存在时返回空字典。
        """
        raw_event = state.get("lastActionEvent")
        if not isinstance(raw_event, dict):
            return {}
        player_id = str(raw_event.get("playerId") or "").strip()
        action_type = str(raw_event.get("actionType") or "").strip()
        if not player_id or not action_type:
            return {}
        return {"playerId": player_id, "actionType": action_type}

    def _build_private_state(
        self,
        state: Dict[str, Any],
        viewer_player_id: str,
    ) -> Dict[str, Any]:
        """
        构建私有状态（仅当前玩家手牌）。

        :param state: 对局状态。
        :param viewer_player_id: 视角玩家 ID。
        :return: 私有状态字典。
        """
        players = state.get("players") or {}
        player_raw = players.get(viewer_player_id) or {}
        hand_cards = player_raw.get("handCards") or []
        return {"handCards": list(hand_cards)}
