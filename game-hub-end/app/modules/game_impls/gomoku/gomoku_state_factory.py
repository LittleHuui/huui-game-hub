"""五子棋初始对局状态构建。"""

from typing import Any, Dict

from app.common.exceptions import ValidationException
from app.core.time_utils import now_ms
from app.modules.game_impls.gomoku.gomoku_constants import (
    BOARD_SIZE,
    WIN_LENGTH,
    DEFAULT_UNDO_REQUEST_EXPIRE_SECONDS,
    PHASE_PLAYING,
)
from app.modules.strategy_turn.schemas import StrategyTurnRuntimeRule


class GomokuStateFactory(object):
    """五子棋开局状态工厂。"""

    def build_initial_state(
        self,
        runtime_rule: StrategyTurnRuntimeRule,
    ) -> Dict[str, Any]:
        """
        根据运行时规则构建初始对局状态。

        :param runtime_rule: 运行时规则。
        :return: 对局状态字典。
        """
        current_time = now_ms()
        player_ids = list(runtime_rule.playerIds)
        if len(player_ids) != 2:
            raise ValidationException("五子棋需要且仅需要 2 名玩家")
        config = dict(runtime_rule.config or {})
        board_size = read_int_config(config, "boardSize", BOARD_SIZE)
        win_length = read_int_config(config, "winLength", WIN_LENGTH)
        turn_timeout_seconds = read_int_config(config, "turnTimeoutSeconds", 30)
        undo_request_expire_seconds = read_int_config(
            config,
            "undoRequestExpireSeconds",
            DEFAULT_UNDO_REQUEST_EXPIRE_SECONDS,
        )
        if board_size != BOARD_SIZE:
            raise ValidationException("五子棋棋盘尺寸必须为 {0}".format(BOARD_SIZE))
        if win_length < 3:
            raise ValidationException("五子棋连子长度不能小于 3")
        if win_length > board_size:
            raise ValidationException("五子棋连子长度不能大于棋盘尺寸")
        if turn_timeout_seconds < 10:
            raise ValidationException("五子棋回合时间不能小于 10 秒")
        if turn_timeout_seconds > 120:
            raise ValidationException("五子棋回合时间不能大于 120 秒")
        if undo_request_expire_seconds < 10:
            raise ValidationException("五子棋悔棋请求有效时间不能小于 10 秒")
        if undo_request_expire_seconds > 120:
            raise ValidationException("五子棋悔棋请求有效时间不能大于 120 秒")
        state = {
            "phase": PHASE_PLAYING,
            "boardSize": board_size,
            "winLength": win_length,
            "turnTimeoutSeconds": turn_timeout_seconds,
            "undoRequestExpireSeconds": undo_request_expire_seconds,
            "board": [[None for _ in range(board_size)] for _ in range(board_size)],
            "players": [
                {"playerId": player_ids[0], "seatIndex": 0, "stone": "BLACK"},
                {"playerId": player_ids[1], "seatIndex": 1, "stone": "WHITE"},
            ],
            "currentPlayerId": player_ids[0],
            "currentStone": "BLACK",
            "moves": [],
            "lastPlaceMoveId": None,
            "lastPlaceRow": None,
            "lastPlaceCol": None,
            "undoRequest": None,
            "winnerPlayerId": None,
            "winnerStone": None,
            "finishReason": None,
            "currentTurnStartedAt": current_time,
            "currentTurnDeadlineAt": current_time + turn_timeout_seconds * 1000,
            "roomConfig": config,
            "enableUndo": read_bool_config(config, "enableUndo", True),
            "moveCounter": 0,
        }
        return state


def read_int_config(
    config: Dict[str, Any],
    key: str,
    default: int,
) -> int:
    """
    安全读取整数配置项。

    :param config: 房间配置。
    :param key: 配置键。
    :param default: 默认值。
    :return: 整数值。
    """
    raw_value = config.get(key, default)
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        raise ValidationException("五子棋配置 {0} 必须是数字".format(key))


def read_bool_config(
    config: Dict[str, Any],
    key: str,
    default: bool,
) -> bool:
    """
    安全读取布尔配置项。

    :param config: 房间配置。
    :param key: 配置键。
    :param default: 默认值。
    :return: 布尔值。
    """
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "1", "yes", "on"):
            return True
        if normalized in ("false", "0", "no", "off"):
            return False
    raise ValidationException("五子棋配置 {0} 必须是布尔值".format(key))
