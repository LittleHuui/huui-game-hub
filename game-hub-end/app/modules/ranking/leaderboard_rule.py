"""从游戏配置解析排行榜排序规则并执行排序。"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import asc, desc

from app.modules.ranking.schemas import LeaderboardRow
from app.modules.score.models import ScoreRecord

SCORE_RESULT_WIN = "win"
DEFAULT_CANDIDATE_LIMIT = 1000
NULL_DURATION_SORT_VALUE = 9223372036854775807

SQL_METRICS = frozenset({"score", "durationMs", "createdAt"})


@dataclass(frozen=True)
class TieBreakerRule:
    """并列时的次级排序指标。"""

    metric: str
    order_direction: str


@dataclass(frozen=True)
class LeaderboardModeRule:
    """单个 gameCode + mode 的排行榜排序规则。"""

    primary_metric: str
    order_direction: str
    tie_breakers: Tuple[TieBreakerRule, ...]
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT

    def all_metrics(self) -> List[Tuple[str, str]]:
        """
        展开主指标与 tieBreakers 为 (metric, direction) 列表。

        :return: 按排序优先级排列的指标列表。
        """
        metrics: List[Tuple[str, str]] = [(self.primary_metric, self.order_direction)]
        for item in self.tie_breakers:
            metrics.append((item.metric, item.order_direction))
        return metrics


def resolve_mode_rule(game_config: Optional[Dict[str, Any]], mode: str) -> LeaderboardModeRule:
    """
    从 ``game_definition.config`` 中解析指定模式的排行规则。

    须在 ``ranking.modes[mode]`` 下配置 ``primaryMetric`` / ``orderDirection`` / ``tieBreakers``。
    缺失配置时抛出 ``ValueError``。

    :param game_config: 游戏扩展配置对象，可空。
    :param mode: 玩法模式。
    :return: 解析后的规则。
    :raises ValueError: 配置缺失或非法。
    """
    if not game_config:
        raise ValueError("游戏未配置 ranking")
    ranking = game_config.get("ranking")
    if not isinstance(ranking, dict):
        raise ValueError("游戏 ranking 配置无效")
    modes = ranking.get("modes")
    if not isinstance(modes, dict):
        raise ValueError("游戏 ranking.modes 配置无效")
    mode_config = modes.get(mode)
    if not isinstance(mode_config, dict):
        raise ValueError(f"游戏未配置 ranking.modes.{mode}")
    candidate_limit = _parse_candidate_limit(ranking)
    if "primaryMetric" not in mode_config:
        raise ValueError(f"ranking.modes.{mode} 缺少 primaryMetric")
    return _parse_primary_metric_rule(mode_config, candidate_limit)


def rule_requires_payload_sort(rule: LeaderboardModeRule) -> bool:
    """
    判断规则是否包含 ``score_record`` 列以外的 payload 指标。

    :param rule: 模式规则。
    :return: 需要 Python 层排序时返回 True。
    """
    for metric, _ in rule.all_metrics():
        if metric not in SQL_METRICS:
            return True
    return False


def build_sql_order_by(rule: LeaderboardModeRule) -> List[Any]:
    """
    将仅含 SQL 列的规则转为 ORDER BY 表达式列表。

    :param rule: 模式规则。
    :return: SQLAlchemy 排序表达式。
    :raises ValueError: 规则含 payload 指标时抛出。
    """
    if rule_requires_payload_sort(rule):
        raise ValueError("规则含 payload 指标，不能使用纯 SQL 排序")
    order_exprs: List[Any] = []
    for metric, direction in rule.all_metrics():
        column = _sql_column(metric)
        order_exprs.append(desc(column) if direction == "desc" else asc(column))
    return order_exprs


def candidate_preorder_by(rule: LeaderboardModeRule) -> List[Any]:
    """
    含 payload 指标时，数据库预筛选用的 ORDER BY（通常按 score 降序）。

    :param rule: 模式规则。
    :return: SQLAlchemy 排序表达式。
    """
    if rule.primary_metric == "score":
        direction = rule.order_direction
    else:
        direction = "desc"
    column = _sql_column("score")
    return [desc(column) if direction == "desc" else asc(column)]


def sort_leaderboard_rows(
    rows: List[LeaderboardRow],
    rule: LeaderboardModeRule,
    limit: int,
) -> List[LeaderboardRow]:
    """
    按配置规则对候选行排序并截断。

    :param rows: 候选排行榜行。
    :param rule: 模式规则。
    :param limit: 返回条数上限。
    :return: 排序后的行列表。
    """
    sorted_rows = sorted(rows, key=lambda row: _python_sort_key(row, rule))
    return sorted_rows[:limit]


def _parse_candidate_limit(ranking: Dict[str, Any]) -> int:
    """
    读取排行榜候选池上限。

    :param ranking: ``config.ranking`` 对象。
    :return: 候选条数上限。
    """
    value = ranking.get("candidateLimit", DEFAULT_CANDIDATE_LIMIT)
    if isinstance(value, bool) or value is None:
        return DEFAULT_CANDIDATE_LIMIT
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_CANDIDATE_LIMIT
    if parsed <= 0:
        return DEFAULT_CANDIDATE_LIMIT
    return parsed


def _parse_primary_metric_rule(mode_config: Dict[str, Any], candidate_limit: int) -> LeaderboardModeRule:
    """
    解析 primaryMetric / tieBreakers 形态的配置。

    :param mode_config: 单模式配置对象。
    :param candidate_limit: 候选池上限。
    :return: 模式规则。
    """
    primary_metric = _require_metric(mode_config.get("primaryMetric"), "primaryMetric")
    order_direction = _normalize_direction(mode_config.get("orderDirection"), "primaryMetric")
    tie_breakers = _parse_tie_breakers(mode_config.get("tieBreakers"))
    return LeaderboardModeRule(
        primary_metric=primary_metric,
        order_direction=order_direction,
        tie_breakers=tie_breakers,
        candidate_limit=candidate_limit,
    )


def _parse_tie_breakers(raw: Any) -> Tuple[TieBreakerRule, ...]:
    """
    解析 tieBreakers 数组。

    :param raw: 原始配置值。
    :return: tieBreaker 规则元组。
    """
    if not isinstance(raw, list):
        return ()
    items: List[TieBreakerRule] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        metric = _require_metric(entry.get("metric"), "tieBreakers.metric")
        direction = _normalize_direction(entry.get("orderDirection"), "tieBreakers.orderDirection")
        items.append(TieBreakerRule(metric=metric, order_direction=direction))
    return tuple(items)


def _require_metric(value: Any, field_name: str) -> str:
    """
    校验并返回指标名。

    :param value: 原始值。
    :param field_name: 字段名（错误提示用）。
    :return: 去除空白后的指标名。
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 不能为空")
    return value.strip()


def _normalize_direction(value: Any, field_name: str) -> str:
    """
    规范化排序方向为 asc 或 desc。

    :param value: 原始方向。
    :param field_name: 字段名（错误提示用）。
    :return: ``asc`` 或 ``desc``。
    """
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须为 asc 或 desc")
    direction = value.strip().lower()
    if direction not in ("asc", "desc"):
        raise ValueError(f"{field_name} 必须为 asc 或 desc")
    return direction


def _sql_column(metric: str) -> Any:
    """
    将 camelCase 指标映射为 ORM 列。

    :param metric: 指标名。
    :return: SQLAlchemy 列对象。
    """
    if metric == "score":
        return ScoreRecord.score
    if metric == "durationMs":
        return ScoreRecord.duration_ms
    if metric == "createdAt":
        return ScoreRecord.created_at
    raise ValueError(f"不支持的 SQL 指标: {metric}")


def _python_sort_key(row: LeaderboardRow, rule: LeaderboardModeRule) -> Tuple[Any, ...]:
    """
    生成 Python 排序键元组。

    :param row: 排行榜行。
    :param rule: 模式规则。
    :return: 排序键。
    """
    return tuple(_metric_sort_component(row, metric, direction) for metric, direction in rule.all_metrics())


def _metric_sort_component(row: LeaderboardRow, metric: str, direction: str) -> Any:
    """
    生成单个指标的排序分量（升序语义，方向由取反实现）。

    :param row: 排行榜行。
    :param metric: 指标名。
    :param direction: asc 或 desc。
    :return: 可比较的分量。
    """
    value = _metric_value(row, metric)
    if direction == "desc":
        if isinstance(value, int):
            return -value
        return value
    return value


def _metric_value(row: LeaderboardRow, metric: str) -> int:
    """
    读取行上的指标值。

    :param row: 排行榜行。
    :param metric: 指标名。
    :return: 整型比较值。
    """
    if metric == "score":
        return row.score
    if metric == "durationMs":
        return _duration_sort_value(row.duration_ms)
    if metric == "createdAt":
        return row.created_at
    payload = _parse_payload_json(row.payload_json)
    return _payload_int(payload, metric)


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
        return NULL_DURATION_SORT_VALUE
    return duration_ms
