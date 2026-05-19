"""道具域数据访问。"""

from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

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

    def list_all(self, *, enabled: Optional[bool] = None) -> List[PropDefinition]:
        """
        列出未软删的道具定义。

        :param enabled: 为 ``True``/``False`` 时按启用状态过滤，为 ``None`` 时不过滤。
        :return: 按 ``created_at`` 升序排列的定义列表。
        """
        stmt = select(PropDefinition).where(PropDefinition.deleted_at.is_(None))
        if enabled is not None:
            stmt = stmt.where(PropDefinition.enabled == (1 if enabled else 0))
        stmt = stmt.order_by(PropDefinition.created_at.asc())
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

    def list_enabled_by_game(self, game_code: str) -> List[GamePropRule]:
        """列出某游戏下已启用的道具规则。"""
        stmt = (
            select(GamePropRule)
            .where(
                GamePropRule.game_code == game_code,
                GamePropRule.enabled == 1,
                GamePropRule.deleted_at.is_(None),
            )
            .order_by(GamePropRule.prop_code.asc())
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
            .order_by(GamePropRule.prop_code.asc())
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
