"""成绩域模块级编排服务。"""

from typing import List, Tuple

from app.modules.score.entity_service import ScoreRecordEntityService
from app.modules.score.models import ScoreRecord
from app.modules.match.schemas import ScoreRecordCreate


class ScoreModuleService:
    """成绩模块：有效成绩记录与查询，不处理对局与钱包。"""

    def __init__(self, score_entity: ScoreRecordEntityService) -> None:
        self._scores = score_entity

    def create_score_record_if_not_exists(self, payload: ScoreRecordCreate) -> Tuple[ScoreRecord, bool]:
        """
        幂等创建可参与排行榜的成绩记录。

        :param payload: 创建请求体。
        :return: ``(成绩记录, 是否新创建)``。
        """
        return self._scores.create_score_record_if_not_exists(payload)

    def list_user_score_records(self, user_id: str, limit: int = 200) -> List[ScoreRecord]:
        """
        查询用户成绩记录列表。

        :param user_id: 用户主键。
        :param limit: 返回条数上限。
        :return: 成绩列表。
        """
        return self._scores.list_by_user(user_id, limit)

    def score_record_exists(self, user_id: str, client_id: str) -> bool:
        """
        判断成绩记录是否已存在（幂等去重）。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 已存在为 True。
        """
        return self._scores.exists_by_user_and_client_id(user_id, client_id)
