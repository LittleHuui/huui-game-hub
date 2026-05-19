"""排行榜域模块级编排服务。"""

from typing import List, Optional

from app.modules.ranking.entity_service import RankingEntityService
from app.modules.ranking.schemas import LeaderboardEntry, LeaderboardResponse, LeaderboardRow


class RankingModuleService:
    """排行榜模块对外业务能力（不落库，仅聚合查询）。"""

    def __init__(self, ranking_entity: RankingEntityService) -> None:
        self._ranking = ranking_entity

    def get_leaderboard(
        self,
        game_code: str,
        mode: str,
        difficulty_code: Optional[str],
        limit: int,
    ) -> LeaderboardResponse:
        """
        查询排行榜并组装 API 响应结构。

        :param game_code: 游戏编码。
        :param mode: 玩法模式。
        :param difficulty_code: 难度编码，可为空表示不按难度过滤。
        :param limit: 返回条数上限。
        :return: 带名次的排行榜数据。
        """
        rows = self._ranking.list_leaderboard(game_code, mode, difficulty_code, limit)
        items = self._build_leaderboard_entries(rows)
        return LeaderboardResponse(
            gameCode=game_code,
            mode=mode,
            difficultyCode=difficulty_code,
            items=items,
        )

    def _build_leaderboard_entries(self, rows: List[LeaderboardRow]) -> List[LeaderboardEntry]:
        """
        将仓储原始行转为带名次的排行榜条目列表。

        :param rows: 仓储层原始行。
        :return: API 展示用排行榜条目列表。
        """
        items = []
        for idx, row in enumerate(rows, start=1):
            items.append(
                LeaderboardEntry(
                    rank=idx,
                    userId=row.user_id,
                    nickname=row.nickname,
                    score=row.score,
                    durationMs=row.duration_ms,
                    createdAt=row.created_at,
                )
            )
        return items
