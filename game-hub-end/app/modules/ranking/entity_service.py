"""排行榜域单实体服务（查询参数与边界校验）。"""

from typing import List, Optional

from app.common.exceptions import ValidationException
from app.modules.ranking.schemas import LeaderboardRow
from app.modules.score.repository import ScoreRecordRepository


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

    def __init__(self, score_repository: ScoreRecordRepository) -> None:
        self._score_records = score_repository

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
        return self._score_records.list_leaderboard(game_code, mode, difficulty_code, limit)
