"""排行榜域单实体服务（查询参数与边界校验）。"""

import json
from typing import Any, Dict, List, Optional

from app.common.exceptions import ValidationException
from app.modules.ranking.schemas import LeaderboardRow
from app.modules.score.repository import ScoreRecordRepository
from app.modules.game_config.repository import GameDefinitionRepository
from app.modules.ranking.leaderboard_rule import (
    SCORE_RESULT_WIN, resolve_mode_rule, rule_requires_payload_sort,
    build_sql_order_by, candidate_preorder_by, sort_leaderboard_rows,
)


def _require_non_blank(value: str, field_name: str) -> str:
    """
    校验字符串非空白。

    :param value: 待校验值。
    :param field_name: 字段名（用于错误提示）。
    :return: 去除首尾空白后的值。
    :raises ValidationException: 值为空或仅空白时抛出。
    """
    stripped = value.strip()
    if not stripped:
        raise ValidationException(f"{field_name} 不能为空")
    return stripped


class RankingEntityService:
    """排行榜查询参数校验与成绩仓储聚合。"""

    def __init__(self, score_repository: ScoreRecordRepository, game_definitions: GameDefinitionRepository) -> None:
        """注入只读成绩与游戏定义仓库。"""
        self._score_records = score_repository
        self._game_definitions = game_definitions

    def list_leaderboard(
        self,
        game_code: str,
        mode: str,
        difficulty_code: Optional[str],
        limit: int,
    ) -> List[LeaderboardRow]:
        """
        读取排行榜原始数据。

        :param game_code: 游戏编码。
        :param mode: 玩法模式。
        :param difficulty_code: 难度编码，可为空表示不按难度过滤。
        :param limit: 返回条数上限。
        :return: 排行榜原始行列表。
        """
        if limit <= 0 or limit > 100:
            raise ValidationException("limit 必须在 1-100 之间")
        game_code = _require_non_blank(game_code, "game_code")
        mode = _require_non_blank(mode, "mode")
        if difficulty_code is not None:
            difficulty_code = _require_non_blank(difficulty_code, "difficulty_code")
        rule = resolve_mode_rule(self._load_game_config(game_code), mode)
        payload_sort = rule_requires_payload_sort(rule)
        rows = self._score_records.query_leaderboard_rows(
            game_code, mode, difficulty_code, SCORE_RESULT_WIN,
            candidate_preorder_by(rule) if payload_sort else build_sql_order_by(rule),
            rule.candidate_limit if payload_sort else limit,
            payload_sort,
        )
        return sort_leaderboard_rows(rows, rule, limit) if payload_sort else rows

    def _load_game_config(self, game_code: str) -> Dict[str, Any]:
        """
        读取游戏扩展配置对象。

        :param game_code: 游戏编码。
        :return: 配置字典，缺失或解析失败时返回空对象。
        """
        game = self._game_definitions.get_by_game_code(game_code)
        if game is None or game.config_json is None or not str(game.config_json).strip():
            return {}
        try:
            parsed = json.loads(game.config_json)
        except (TypeError, ValueError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed
