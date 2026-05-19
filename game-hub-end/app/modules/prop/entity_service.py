"""道具域单实体服务。"""

from typing import List, Optional, Tuple

from app.core.exceptions import NotFoundException
from app.modules.prop.models import GamePropRule, PropDefinition
from app.modules.prop.repository import GamePropRuleRepository, PropDefinitionRepository


class PropDefinitionEntityService:
    """道具定义实体服务。"""

    def __init__(self, repository: PropDefinitionRepository) -> None:
        self._repository = repository

    def get_by_prop_code(self, prop_code: str) -> Optional[PropDefinition]:
        """
        按道具编码读取定义。

        :param prop_code: 道具编码。
        :return: 定义实体或 ``None``。
        """
        return self._repository.get_by_prop_code(prop_code)

    def list_all(self, *, enabled: Optional[bool] = None) -> List[PropDefinition]:
        """
        列出未软删的道具定义。

        :param enabled: 为 ``True``/``False`` 时按启用状态过滤，为 ``None`` 时不过滤。
        :return: 道具定义列表。
        """
        return self._repository.list_all(enabled=enabled)

    def require_enabled(self, prop_code: str) -> PropDefinition:
        """
        读取已启用道具定义。

        :param prop_code: 道具编码。
        :return: 道具定义。
        :raises NotFoundException: 不存在或未启用。
        """
        entity = self._repository.get_by_prop_code(prop_code)
        if entity is None or entity.enabled != 1:
            raise NotFoundException("道具不存在或未启用")
        return entity


class GamePropRuleEntityService:
    """游戏道具规则实体服务。"""

    def __init__(self, repository: GamePropRuleRepository) -> None:
        self._repository = repository

    def list_enabled_with_definitions(self, game_code: str) -> List[Tuple[GamePropRule, PropDefinition]]:
        """
        列出某游戏下已启用规则及道具定义。

        :param game_code: 游戏编码。
        :return: ``(规则, 定义)`` 元组列表。
        """
        return self._repository.list_enabled_with_definitions(game_code)

    def list_enabled_by_game(self, game_code: str) -> List[GamePropRule]:
        """
        列出某游戏下已启用且未软删的道具规则。

        :param game_code: 游戏编码。
        :return: 道具规则列表。
        """
        return self._repository.list_enabled_by_game(game_code)

    def require_enabled_rule(self, game_code: str, prop_code: str) -> GamePropRule:
        """
        读取某游戏下已启用道具规则。

        :param game_code: 游戏编码。
        :param prop_code: 道具编码。
        :return: 游戏规则。
        :raises NotFoundException: 不存在或未启用。
        """
        entity = self._repository.get_by_game_and_prop(game_code, prop_code)
        if entity is None or entity.enabled != 1:
            raise NotFoundException("该游戏未配置此道具或规则未启用")
        return entity
