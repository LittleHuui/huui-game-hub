"""对局域模块级编排服务。"""

from typing import List, Optional, Tuple

from app.common.page_response import PageResponse
from app.common.exceptions import NotFoundException
from app.modules.boot.schemas import MatchRecordResponse
from app.modules.match.entity_service import MatchActionRecordEntityService, MatchRecordEntityService
from app.modules.match.models import MatchActionRecord, MatchRecord
from app.modules.match.schemas import (
    MatchActionBatchCreate,
    MatchActionBatchResult,
    MatchActionRecordCreate,
    MatchRecordCreate,
    to_match_record_response,
)
from app.modules.user.entity_service import UserAccountEntityService


class MatchModuleService:
    """对局模块：历史对局记录与查询，不处理成绩与钱包。"""

    def __init__(
        self,
        match_entity: MatchRecordEntityService,
        action_entity: MatchActionRecordEntityService,
        user_accounts: UserAccountEntityService,
    ) -> None:
        self._matches = match_entity
        self._actions = action_entity
        self._users = user_accounts

    def create_match_record_if_not_exists(self, payload: MatchRecordCreate) -> Tuple[MatchRecord, bool]:
        """
        幂等创建对局记录。

        :param payload: 创建请求体。
        :return: ``(对局记录, 是否新创建)``。
        """
        return self._matches.create_match_record_if_not_exists(payload)

    def create_match_action_if_not_exists(self, payload: MatchActionRecordCreate) -> MatchActionRecord:
        """
        幂等创建单条对局操作记录。

        :param payload: 创建请求体。
        :return: 操作记录（已存在则返回既有行）。
        """
        record, _ = self._actions.create_match_action_if_not_exists(payload)
        return record

    def batch_create_match_actions(self, body: MatchActionBatchCreate) -> MatchActionBatchResult:
        """
        批量幂等创建对局操作记录。

        :param body: 批量请求体。
        :return: 全部操作记录及新创建条数。
        """
        created_count = 0
        for item in body.items:
            _record, is_new = self._actions.create_match_action_if_not_exists(item)
            if is_new:
                created_count += 1
        return MatchActionBatchResult(createdCount=created_count)

    def list_user_matches(self, user_id: str, limit: int = 50) -> List[MatchRecord]:
        """
        查询用户最近对局列表（供启动/同步内部使用）。

        :param user_id: 用户主键。
        :param limit: 返回条数上限。
        :return: 对局列表。
        """
        return self._matches.list_by_user(user_id, limit)

    def page_user_match_records(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        mode: Optional[str] = None,
        result: Optional[str] = None,
        difficulty_code: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> PageResponse[MatchRecordResponse]:
        """
        分页查询用户历史对局并转为 API 响应。

        :param user_id: 用户主键。
        :param game_code: 游戏编码，非空时过滤。
        :param mode: 玩法模式，非空时过滤。
        :param result: 对局结果，非空时过滤。
        :param difficulty_code: 难度编码，非空时过滤。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :return: 分页对局响应。
        :raises NotFoundException: 用户不存在。
        """
        if self._users.get_by_server_id(user_id, active_only=True) is None:
            raise NotFoundException("用户不存在")
        total = self._matches.count_by_user_filtered(
            user_id,
            game_code=game_code,
            mode=mode,
            result=result,
            difficulty_code=difficulty_code,
        )
        rows = self._matches.page_by_user_filtered(
            user_id,
            game_code=game_code,
            mode=mode,
            result=result,
            difficulty_code=difficulty_code,
            page_num=page_num,
            page_size=page_size,
        )
        return PageResponse(
            pageNum=page_num,
            pageSize=page_size,
            total=total,
            items=[to_match_record_response(row) for row in rows],
        )

    def get_match_record_detail(self, match_id: str) -> MatchRecordResponse:
        """
        查询单局对局详情。

        :param match_id: 对局主键（``match_record.server_id``）。
        :return: 对局详情响应。
        :raises NotFoundException: 对局不存在或已软删。
        """
        record = self._matches.get_by_server_id(match_id)
        if record is None:
            raise NotFoundException("对局不存在")
        return to_match_record_response(record)

    def list_match_actions(self, match_id: str) -> List[MatchActionRecord]:
        """
        查询某局全部操作记录（按 ``action_seq`` 升序）。

        :param match_id: 对局主键。
        :return: 操作列表。
        """
        return self._actions.list_by_match_id(match_id)

    def match_record_exists(self, user_id: str, client_id: str) -> bool:
        """
        判断对局记录是否已存在。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 已存在为 True。
        """
        return self._matches.get_by_user_and_client_id(user_id, client_id) is not None
