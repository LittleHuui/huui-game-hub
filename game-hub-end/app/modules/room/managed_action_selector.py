"""托管动作选择器。"""

import logging
import math
from typing import Dict, List, Optional, Set

from app.modules.room.action_scorer import ActionScore, ManagedActionScorerRegistry
from app.modules.strategy_turn.schemas import GameView, LegalAction

logger = logging.getLogger(__name__)


class ManagedActionSelector(object):
    """托管动作选择入口。"""

    def __init__(self, scorer_registry: Optional[ManagedActionScorerRegistry] = None) -> None:
        self._scorer_registry = scorer_registry

    def select_action_id(
        self,
        view: GameView,
        legal_actions: List[LegalAction],
        player_context: Optional[Dict[str, object]] = None,
    ) -> Optional[str]:
        """
        从合法动作列表中选择托管 actionId。

        :param view: 当前玩家视角 GameView。
        :param legal_actions: 当前合法动作列表。
        :param player_context: 玩家上下文。
        :return: 选中的 actionId，无可用动作时返回 ``None``。
        """
        del player_context
        try:
            scored_action_id = self._select_scored_action_id(view, legal_actions)
            if scored_action_id:
                return scored_action_id
        except Exception:
            logger.exception("managed action scorer failed, fallback used")
        return self._select_fallback_action_id(legal_actions)

    def _select_scored_action_id(
        self,
        view: GameView,
        legal_actions: List[LegalAction],
    ) -> Optional[str]:
        """
        通过评分器选择最高分 actionId。

        :param view: 当前玩家视角 GameView。
        :param legal_actions: 合法动作列表。
        :return: 最高分 actionId，无法评分时返回 ``None``。
        """
        if self._scorer_registry is None:
            return None
        game_code = str(getattr(view, "gameCode", "") or "").strip()
        if not game_code:
            return None
        scorer = self._scorer_registry.get(game_code)
        if scorer is None:
            return None
        player_id = str(getattr(view, "viewerPlayerId", "") or "").strip()
        if not player_id:
            return None
        scores = scorer.score_actions(
            game_code=game_code,
            game_view=view,
            legal_actions=legal_actions,
            player_id=player_id,
        )
        legal_action_ids = {
            str(action.actionId or "").strip()
            for action in legal_actions
            if str(action.actionId or "").strip()
        }
        valid_scores = self._normalize_valid_scores(scores, legal_action_ids)
        if not valid_scores:
            return None
        valid_scores.sort(key=lambda item: item.score, reverse=True)
        return valid_scores[0].actionId

    def _select_fallback_action_id(self, legal_actions: List[LegalAction]) -> Optional[str]:
        """
        按既有规则遍历合法动作，返回第一个非空 actionId。

        :param legal_actions: 合法动作列表。
        :return: 选中的 actionId，无可用动作时返回 ``None``。
        """
        for action in legal_actions:
            action_id = str(action.actionId or "").strip()
            if action_id:
                return action_id
        return None

    def _normalize_valid_scores(
        self,
        scores: Optional[List[ActionScore]],
        legal_action_ids: Set[str],
    ) -> List[ActionScore]:
        """
        过滤非法评分项。

        :param scores: 原始评分列表。
        :param legal_action_ids: 合法 actionId 集合。
        :return: 有效评分列表。
        """
        if not scores:
            return []
        valid_scores: List[ActionScore] = []
        for item in scores:
            action_id = str(getattr(item, "actionId", "") or "").strip()
            if not action_id or action_id not in legal_action_ids:
                continue
            raw_score = getattr(item, "score", None)
            if not isinstance(raw_score, (int, float)):
                continue
            if not math.isfinite(float(raw_score)):
                continue
            reason = str(getattr(item, "reason", "") or "")
            valid_scores.append(
                ActionScore(actionId=action_id, score=float(raw_score), reason=reason),
            )
        return valid_scores
