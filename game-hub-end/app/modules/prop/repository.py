"""道具域数据访问。"""

from typing import List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.time_utils import now_ms
from app.modules.prop.models import GamePropRule, PropDefinition


class PropDefinitionRepository:
    """``prop_definition`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_prop_code(self, prop_code: str, *, active_only: bool = True) -> Optional[PropDefinition]:
        """按道具编码查询定义。"""
        stmt = select(PropDefinition).where(PropDefinition.prop_code == prop_code)
        if active_only:
            stmt = stmt.where(PropDefinition.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_all(
        self,
        *,
        enabled: Optional[bool] = None,
        active_only: bool = True,
    ) -> List[PropDefinition]:
        """
        列出道具定义。

        :param enabled: 为 ``True``/``False`` 时按启用状态过滤，为 ``None`` 时不过滤。
        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 按 ``prop_code`` 升序排列的定义列表。
        """
        stmt = select(PropDefinition)
        if active_only:
            stmt = stmt.where(PropDefinition.deleted_at.is_(None))
        if enabled is not None:
            stmt = stmt.where(PropDefinition.enabled == (1 if enabled else 0))
        stmt = stmt.order_by(PropDefinition.prop_code.asc())
        return list(self._session.scalars(stmt).all())

    def add(self, entity: PropDefinition) -> PropDefinition:
        """插入道具定义。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: PropDefinition) -> PropDefinition:
        """持久化道具定义变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: PropDefinition) -> PropDefinition:
        """软删除道具定义并禁用。"""
        now = now_ms()
        entity.deleted_at = now
        entity.enabled = 0
        entity.updated_at = now
        return self.save(entity)

    def physical_delete(self, entity: PropDefinition) -> None:
        """物理删除道具定义。"""
        self._session.delete(entity)
        self._session.flush()


class GamePropRuleRepository:
    """``game_prop_rule`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_game_and_prop(
        self,
        game_code: str,
        prop_code: str,
        *,
        active_only: bool = True,
    ) -> Optional[GamePropRule]:
        """按游戏与道具编码查询规则。"""
        stmt = select(GamePropRule).where(
            GamePropRule.game_code == game_code,
            GamePropRule.prop_code == prop_code,
        )
        if active_only:
            stmt = stmt.where(GamePropRule.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_by_game(
        self,
        game_code: str,
        *,
        active_only: bool = True,
    ) -> List[GamePropRule]:
        """
        列出某游戏下全部道具规则。

        :param game_code: 游戏编码。
        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 规则列表。
        """
        stmt = select(GamePropRule).where(GamePropRule.game_code == game_code)
        if active_only:
            stmt = stmt.where(GamePropRule.deleted_at.is_(None))
        stmt = stmt.order_by(GamePropRule.sort_no.asc(), GamePropRule.prop_code.asc())
        return list(self._session.scalars(stmt).all())

    def list_by_prop_code(
        self,
        prop_code: str,
        *,
        active_only: bool = True,
    ) -> List[GamePropRule]:
        """
        列出引用指定道具编码的全部游戏规则。

        :param prop_code: 道具编码。
        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 规则列表。
        """
        stmt = select(GamePropRule).where(GamePropRule.prop_code == prop_code)
        if active_only:
            stmt = stmt.where(GamePropRule.deleted_at.is_(None))
        stmt = stmt.order_by(GamePropRule.game_code.asc(), GamePropRule.sort_no.asc())
        return list(self._session.scalars(stmt).all())

    def list_enabled_by_game(self, game_code: str) -> List[GamePropRule]:
        """列出某游戏下已启用的道具规则。"""
        stmt = (
            select(GamePropRule)
            .where(
                GamePropRule.game_code == game_code,
                GamePropRule.enabled == 1,
                GamePropRule.deleted_at.is_(None),
            )
            .order_by(GamePropRule.sort_no.asc(), GamePropRule.prop_code.asc())
        )
        return list(self._session.scalars(stmt).all())

    def list_enabled_with_definitions(
        self,
        game_code: str,
    ) -> List[Tuple[GamePropRule, PropDefinition]]:
        """联结查询某游戏下已启用规则及对应道具定义。"""
        stmt = (
            select(GamePropRule, PropDefinition)
            .join(PropDefinition, PropDefinition.prop_code == GamePropRule.prop_code)
            .where(
                GamePropRule.game_code == game_code,
                GamePropRule.enabled == 1,
                GamePropRule.deleted_at.is_(None),
                PropDefinition.enabled == 1,
                PropDefinition.deleted_at.is_(None),
            )
            .order_by(GamePropRule.sort_no.asc(), GamePropRule.prop_code.asc())
        )
        return list(self._session.execute(stmt).all())

    def add(self, entity: GamePropRule) -> GamePropRule:
        """插入游戏规则。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: GamePropRule) -> GamePropRule:
        """持久化游戏规则变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: GamePropRule) -> GamePropRule:
        """软删除游戏规则并禁用。"""
        now = now_ms()
        entity.deleted_at = now
        entity.enabled = 0
        entity.updated_at = now
        return self.save(entity)

    def physical_delete(self, entity: GamePropRule) -> None:
        """物理删除游戏规则。"""
        self._session.delete(entity)
        self._session.flush()

    def physical_delete_by_game_code(self, game_code: str) -> int:
        """
        按游戏编码物理删除全部道具规则。

        :param game_code: 游戏编码。
        :return: 删除行数。
        """
        stmt = delete(GamePropRule).where(GamePropRule.game_code == game_code)
        result = self._session.execute(stmt)
        self._session.flush()
        return int(result.rowcount or 0)

    def physical_delete_by_prop_code(self, prop_code: str) -> int:
        """
        按道具编码物理删除全部游戏规则。

        :param prop_code: 道具编码。
        :return: 删除行数。
        """
        stmt = delete(GamePropRule).where(GamePropRule.prop_code == prop_code)
        result = self._session.execute(stmt)
        self._session.flush()
        return int(result.rowcount or 0)
