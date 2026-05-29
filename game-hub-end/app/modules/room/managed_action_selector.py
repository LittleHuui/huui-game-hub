"""托管动作选择器。"""

from typing import Dict, List, Optional

from app.modules.strategy_turn.schemas import GameView, LegalAction


class ManagedActionSelector(object):
    """托管动作选择入口。"""

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
        del view
        del player_context
        for action in legal_actions:
            action_id = str(action.actionId or "").strip()
            if action_id:
                return action_id
        return None
