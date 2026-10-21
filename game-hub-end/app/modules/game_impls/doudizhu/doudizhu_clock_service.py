"""斗地主回合计时服务。"""

from typing import Any, Dict, Optional

from app.core.time_utils import now_ms


class DoudizhuClockService(object):
    """管理斗地主决策与出牌阶段的回合计时。"""

    def stamp_turn_clock(
        self,
        state: Dict[str, Any],
        timeout_seconds: Optional[int] = None,
    ) -> None:
        """
        刷新当前玩家操作回合时钟。

        :param state: 对局状态。
        :param timeout_seconds: 超时秒数；为空时使用出牌阶段默认配置。
        :return: 无。
        """
        if timeout_seconds is None:
            rule_config = state.get("ruleConfig") or {}
            timeout_seconds = int(rule_config.get("turnTimeoutSeconds", 30))
        current_time = now_ms()
        state["currentTurnStartedAt"] = current_time
        state["currentTurnDeadlineAt"] = current_time + timeout_seconds * 1000

    def stamp_decision_clock(
        self,
        state: Dict[str, Any],
        timeout_key: str,
    ) -> None:
        """
        按规则配置键刷新决策阶段回合时钟。

        :param state: 对局状态。
        :param timeout_key: 规则配置中的超时字段名。
        :return: 无。
        """
        rule_config = state.get("ruleConfig") or {}
        defaults = {
            "biddingTimeoutSeconds": 20,
            "doublingTimeoutSeconds": 15,
            "turnTimeoutSeconds": 30,
        }
        default_seconds = defaults.get(timeout_key, 20)
        timeout_seconds = int(rule_config.get(timeout_key, default_seconds))
        self.stamp_turn_clock(state, timeout_seconds)

    def clear_turn_clock(self, state: Dict[str, Any]) -> None:
        """
        清理当前回合时钟字段。

        :param state: 对局状态。
        :return: 无。
        """
        state["currentTurnStartedAt"] = None
        state["currentTurnDeadlineAt"] = None
