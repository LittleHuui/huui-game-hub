"""排行榜规则解析与排序单元测试。"""

import pytest

from app.modules.ranking.schemas import LeaderboardRow
from app.modules.score.leaderboard_rule import (
    resolve_mode_rule,
    rule_requires_payload_sort,
    sort_leaderboard_rows,
)


def test_resolve_minesweeper_single_rule() -> None:
    """扫雷 single 模式应解析为用时升序 + 分数降序。"""
    config = {
        "ranking": {
            "modes": {
                "single": {
                    "primaryMetric": "durationMs",
                    "orderDirection": "asc",
                    "tieBreakers": [
                        {"metric": "score", "orderDirection": "desc"},
                        {"metric": "createdAt", "orderDirection": "asc"},
                    ],
                },
            },
        },
    }
    rule = resolve_mode_rule(config, "single")
    assert rule.primary_metric == "durationMs"
    assert rule.order_direction == "asc"
    assert rule.tie_breakers[0].metric == "score"
    assert not rule_requires_payload_sort(rule)


def test_resolve_match3_timed_rule() -> None:
    """match3 timed 模式应解析 primaryMetric 与 tieBreakers。"""
    config = {
        "ranking": {
            "modes": {
                "timed": {
                    "primaryMetric": "score",
                    "orderDirection": "desc",
                    "tieBreakers": [
                        {"metric": "comboMax", "orderDirection": "desc"},
                        {"metric": "durationMs", "orderDirection": "asc"},
                    ],
                },
            },
        },
    }
    rule = resolve_mode_rule(config, "timed")
    assert rule.primary_metric == "score"
    assert rule.tie_breakers[0].metric == "comboMax"
    assert rule_requires_payload_sort(rule)


def test_sort_match3_timed_by_combo_and_duration() -> None:
    """timed 模式：同分比 comboMax，再比用时。"""
    config = {
        "ranking": {
            "modes": {
                "timed": {
                    "primaryMetric": "score",
                    "orderDirection": "desc",
                    "tieBreakers": [
                        {"metric": "comboMax", "orderDirection": "desc"},
                        {"metric": "durationMs", "orderDirection": "asc"},
                    ],
                },
            },
        },
    }
    rule = resolve_mode_rule(config, "timed")
    rows = [
        LeaderboardRow(
            user_id="a",
            nickname="A",
            score=1000,
            duration_ms=90000,
            created_at=1,
            payload_json='{"comboMax": 5}',
        ),
        LeaderboardRow(
            user_id="b",
            nickname="B",
            score=1000,
            duration_ms=60000,
            created_at=2,
            payload_json='{"comboMax": 8}',
        ),
        LeaderboardRow(
            user_id="c",
            nickname="C",
            score=1000,
            duration_ms=50000,
            created_at=3,
            payload_json='{"comboMax": 8}',
        ),
    ]
    sorted_rows = sort_leaderboard_rows(rows, rule, 10)
    assert [row.user_id for row in sorted_rows] == ["c", "b", "a"]


def test_resolve_mode_rule_raises_when_config_missing() -> None:
    """无 ranking 配置时应直接报错。"""
    with pytest.raises(ValueError, match="ranking"):
        resolve_mode_rule(None, "single")
