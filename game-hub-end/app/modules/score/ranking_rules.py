"""各游戏排行榜排序规则。"""

import json
from typing import Any, Dict, List, Optional, Tuple

from app.modules.ranking.schemas import LeaderboardRow
from app.modules.score.models import ScoreRecord

SCORE_RESULT_WIN = "win"
MATCH3_GAME_CODE = "match3"
MATCH3_TIMED_MODE = "timed"
MATCH3_ENDLESS_MODE = "endless"
MATCH3_LEADERBOARD_CANDIDATE_LIMIT = 1000


def resolve_order_by(game_code: str) -> List[Any]:
    """
    按游戏编码解析 ORDER BY 子句。

    :param game_code: 游戏编码。
    :return: SQLAlchemy 排序表达式列表。
    """
    if game_code == "minesweeper":
        return _minesweeper_order_by()
    return _default_order_by()


def is_match3_leaderboard(game_code: str, mode: str) -> bool:
    """
    判断是否使用 Color Crush 专属排行榜排序。

    :param game_code: 游戏编码。
    :param mode: 玩法模式。
    :return: 需要按 match3 规则排序时返回 True。
    """
    return game_code == MATCH3_GAME_CODE and mode in (MATCH3_TIMED_MODE, MATCH3_ENDLESS_MODE)


def sort_match3_leaderboard_rows(rows: List[LeaderboardRow], mode: str, limit: int) -> List[LeaderboardRow]:
    """
    按 Color Crush 模式规则排序排行榜候选行。

    :param rows: 候选排行榜行。
    :param mode: 玩法模式。
    :param limit: 返回条数上限。
    :return: 排序并截断后的排行榜行。
    """
    if mode == MATCH3_TIMED_MODE:
        sorted_rows = sorted(rows, key=_match3_timed_sort_key)
    else:
        sorted_rows = sorted(rows, key=_match3_endless_sort_key)
    return sorted_rows[:limit]


def _minesweeper_order_by() -> List[Any]:
    """
    扫雷排行：用时升序、分数降序、创建时间升序。

    :return: 排序表达式列表。
    """
    return [
        ScoreRecord.duration_ms.asc(),
        ScoreRecord.score.desc(),
        ScoreRecord.created_at.asc(),
    ]


def _default_order_by() -> List[Any]:
    """
    通用默认排行：分数降序、创建时间升序。

    :return: 排序表达式列表。
    """
    return [
        ScoreRecord.score.desc(),
        ScoreRecord.created_at.asc(),
    ]


def _match3_timed_sort_key(row: LeaderboardRow) -> Tuple[int, int, int, int]:
    """
    Color Crush timed 排序：分数降序、最大连击降序、用时升序。

    :param row: 排行榜候选行。
    :return: Python 排序键。
    """
    payload = _parse_payload_json(row.payload_json)
    return (
        -row.score,
        -_payload_int(payload, "comboMax"),
        _duration_sort_value(row.duration_ms),
        row.created_at,
    )


def _match3_endless_sort_key(row: LeaderboardRow) -> Tuple[int, int, int, int]:
    """
    Color Crush endless 排序：分数降序、最大连击降序、步数降序。

    :param row: 排行榜候选行。
    :return: Python 排序键。
    """
    payload = _parse_payload_json(row.payload_json)
    return (
        -row.score,
        -_payload_int(payload, "comboMax"),
        -_payload_int(payload, "moves"),
        row.created_at,
    )


def _parse_payload_json(payload_json: Optional[str]) -> Dict[str, Any]:
    """
    解析成绩附加 payload；异常或非对象时按空对象处理。

    :param payload_json: ``score_record.payload_json`` 原始文本。
    :return: payload 字典。
    """
    if payload_json is None or not payload_json.strip():
        return {}
    try:
        payload = json.loads(payload_json)
    except (TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _payload_int(payload: Dict[str, Any], key: str) -> int:
    """
    从 payload 中读取整数字段；缺失或非法时按 0 处理。

    :param payload: payload 字典。
    :param key: 字段名。
    :return: 整数值。
    """
    value = payload.get(key)
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _duration_sort_value(duration_ms: Optional[int]) -> int:
    """
    生成用时升序排序值；缺失用时排在最后。

    :param duration_ms: 用时毫秒数。
    :return: 排序值。
    """
    if duration_ms is None:
        return 9223372036854775807
    return duration_ms
