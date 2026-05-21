"""管理配置导入模块编排服务。"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from app.common.exceptions import BizException
from app.common.error_code import ErrorCode
from app.modules.admin_config.entity_service import (
    GameClientConfigImportEntityService,
    GameDefinitionImportEntityService,
    GameDifficultyImportEntityService,
    GamePropRuleImportEntityService,
    PropDefinitionImportEntityService,
)
from app.modules.admin_config.schemas import (
    GameSeedClientConfig,
    GameSeedDifficulty,
    GameSeedGame,
    GameSeedProp,
    GameSeedPropRule,
    ImportGameSeedRequest,
    ImportGameSeedResponse,
)
from app.modules.prop.entity_service import PropDefinitionEntityService
from app.modules.game.models import GameClientConfig, GameDifficulty
from app.modules.prop.models import GamePropRule


IMPORT_MODE_MERGE = "merge"
IMPORT_MODE_FULL = "full"
DELETE_MODE_LOGICAL = "logical"
DELETE_MODE_PHYSICAL = "physical"
_VALID_IMPORT_MODES = frozenset({IMPORT_MODE_MERGE, IMPORT_MODE_FULL})
_VALID_DELETE_MODES = frozenset({DELETE_MODE_LOGICAL, DELETE_MODE_PHYSICAL})


def _resolve_import_params(import_mode: str, delete_mode: str) -> Tuple[str, str]:
    """
    校验并规范化导入模式参数。

    :param import_mode: 导入模式（merge / full）。
    :param delete_mode: 删除模式（logical / physical），仅 full 时生效。
    :return: 规范化后的 ``(import_mode, delete_mode)``。
    :raises BizException: 参数非法时抛出。
    """
    mode = (import_mode or "").strip().lower()
    delete = (delete_mode or "").strip().lower()
    if mode not in _VALID_IMPORT_MODES:
        raise BizException(
            ErrorCode.PARAM_ERROR,
            message="importMode 无效，仅支持 merge、full",
        )
    if delete not in _VALID_DELETE_MODES:
        raise BizException(
            ErrorCode.PARAM_ERROR,
            message="deleteMode 无效，仅支持 logical、physical",
        )
    return mode, delete


def _client_config_composite(difficulty_code: Optional[str], client_type: str) -> Tuple[str, str]:
    """
    生成客户端配置唯一键（与请求校验一致）。

    :param difficulty_code: 难度编码，可空。
    :param client_type: 客户端类型。
    :return: ``(difficultyKey, clientType)`` 元组。
    """
    diff_key = difficulty_code if difficulty_code is not None else ""
    return diff_key, client_type


def _ensure_json_serializable(value: Any, field_label: str) -> None:
    """
    校验值可被 JSON 序列化。

    :param value: 待校验对象。
    :param field_label: 字段说明，用于错误信息。
    :raises BizException: 不可序列化时抛出。
    """
    try:
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise BizException(
            ErrorCode.PARAM_ERROR,
            message="{} 不可 JSON 序列化".format(field_label),
        ) from exc


def _ensure_not_blank(value: Optional[str], field_label: str) -> None:
    """
    校验关键编码字段非空白。

    :param value: 待校验字符串。
    :param field_label: 字段说明，用于错误信息。
    :raises BizException: 值为空或仅空白时抛出。
    """
    if value is None or not value.strip():
        raise BizException(
            ErrorCode.PARAM_ERROR,
            message="{} 不能为空".format(field_label),
        )


def _serialize_optional_config(config: Dict[str, Any], field_label: str) -> Optional[str]:
    """
    将游戏 config 序列化为 JSON 字符串；空字典时返回 None。

    :param config: 配置字典。
    :param field_label: 字段说明。
    :return: JSON 字符串或 None。
    """
    _ensure_json_serializable(config, field_label)
    if not config:
        return None
    return json.dumps(config, ensure_ascii=False, separators=(",", ":"))


class AdminConfigModuleService:
    """游戏种子配置导入编排。"""

    def __init__(
        self,
        prop_import: PropDefinitionImportEntityService,
        game_import: GameDefinitionImportEntityService,
        difficulty_import: GameDifficultyImportEntityService,
        client_config_import: GameClientConfigImportEntityService,
        prop_rule_import: GamePropRuleImportEntityService,
        prop_definitions: PropDefinitionEntityService,
    ) -> None:
        self._prop_import = prop_import
        self._game_import = game_import
        self._difficulty_import = difficulty_import
        self._client_config_import = client_config_import
        self._prop_rule_import = prop_rule_import
        self._prop_definitions = prop_definitions

    def import_game_seed(
        self,
        request: ImportGameSeedRequest,
        import_mode: str = IMPORT_MODE_MERGE,
        delete_mode: str = DELETE_MODE_LOGICAL,
    ) -> ImportGameSeedResponse:
        """
        导入统一游戏种子配置。

        merge：仅 upsert 种子中的记录，不处理库内多余项。
        full：upsert 后按 deleteMode 清理库内种子未提及的配置。

        :param request: 导入请求体。
        :param import_mode: 导入模式 ``merge`` / ``full``。
        :param delete_mode: 删除模式 ``logical`` / ``physical``，仅 ``full`` 时生效。
        :return: 导入统计结果。
        :raises BizException: 校验失败时抛出。
        """
        resolved_mode, resolved_delete = _resolve_import_params(import_mode, delete_mode)
        self._validate_request(request)
        result = ImportGameSeedResponse(
            importMode=resolved_mode,
            deleteMode=resolved_delete,
        )
        request_prop_codes = {item.propCode for item in request.props}

        for prop_item in request.props:
            _ensure_json_serializable(
                {
                    "description": prop_item.description,
                    "icon": prop_item.icon,
                },
                "props[{}]".format(prop_item.propCode),
            )
            _, created = self._prop_import.upsert(
                prop_code=prop_item.propCode,
                prop_name=prop_item.propName,
                description=prop_item.description,
                icon=prop_item.icon,
                base_price=prop_item.basePrice,
                enabled=prop_item.enabled,
            )
            if created:
                result.importedProps += 1
            else:
                result.updatedProps += 1

        for game_item in request.games:
            self._import_game(game_item, request_prop_codes, result)

        if resolved_mode == IMPORT_MODE_FULL:
            self._purge_absent_from_seed(request, resolved_delete)

        return result

    def _purge_absent_from_seed(
        self,
        request: ImportGameSeedRequest,
        delete_mode: str,
    ) -> None:
        """
        全量导入后清理种子未提及的库内配置。

        :param request: 导入请求体。
        :param delete_mode: 删除模式 ``logical`` / ``physical``。
        """
        seed_prop_codes = {item.propCode for item in request.props}
        seed_game_codes = {item.gameCode for item in request.games}
        game_nested: Dict[str, Dict[str, Any]] = {}
        for game_item in request.games:
            game_nested[game_item.gameCode] = {
                "difficulties": {d.difficultyCode for d in game_item.difficulties},
                "client_configs": {
                    _client_config_composite(c.difficultyCode, c.clientType)
                    for c in game_item.clientConfigs
                },
                "prop_rules": {r.propCode for r in game_item.propRules},
            }

        for db_game in self._game_import.list_all(active_only=False):
            if db_game.game_code not in seed_game_codes:
                self._remove_game_tree(db_game.game_code, delete_mode)

        for game_code, nested in game_nested.items():
            self._purge_game_nested_orphans(game_code, nested, delete_mode)

        for db_prop in self._prop_import.list_all(active_only=False):
            if db_prop.prop_code not in seed_prop_codes:
                self._remove_prop_orphans(db_prop.prop_code, delete_mode)

    def _purge_game_nested_orphans(
        self,
        game_code: str,
        nested: Dict[str, Any],
        delete_mode: str,
    ) -> None:
        """
        清理某游戏下种子未提及的嵌套配置。

        :param game_code: 游戏编码。
        :param nested: 种子内嵌套键集合。
        :param delete_mode: 删除模式。
        """
        for db_rule in self._prop_rule_import.list_by_game(game_code, active_only=False):
            if db_rule.prop_code not in nested["prop_rules"]:
                self._remove_prop_rule(db_rule, delete_mode)

        for db_client in self._client_config_import.list_by_game(game_code, active_only=False):
            composite = _client_config_composite(db_client.difficulty_code, db_client.client_type)
            if composite not in nested["client_configs"]:
                self._remove_client_config(db_client, delete_mode)

        for db_diff in self._difficulty_import.list_by_game(game_code, active_only=False):
            if db_diff.difficulty_code not in nested["difficulties"]:
                self._remove_difficulty(db_diff, delete_mode)

    def _remove_game_tree(self, game_code: str, delete_mode: str) -> None:
        """
        删除整棵游戏配置树（含嵌套项）。

        物理删除顺序：game_prop_rule → game_client_config → game_difficulty → game_definition。

        :param game_code: 游戏编码。
        :param delete_mode: 删除模式。
        """
        if delete_mode == DELETE_MODE_PHYSICAL:
            self._prop_rule_import.physical_remove_by_game_code(game_code)
            self._client_config_import.physical_remove_by_game_code(game_code)
            self._difficulty_import.physical_remove_by_game_code(game_code)
            for db_game in self._game_import.list_all(active_only=False):
                if db_game.game_code == game_code:
                    self._game_import.physical_remove(db_game)
                    break
            return

        for db_rule in self._prop_rule_import.list_by_game(game_code, active_only=False):
            self._prop_rule_import.logical_disable(db_rule)
        for db_client in self._client_config_import.list_by_game(game_code, active_only=False):
            self._client_config_import.logical_disable(db_client)
        for db_diff in self._difficulty_import.list_by_game(game_code, active_only=False):
            self._difficulty_import.logical_disable(db_diff)
        for db_game in self._game_import.list_all(active_only=False):
            if db_game.game_code == game_code:
                self._game_import.logical_disable(db_game)
                break

    def _remove_prop_orphans(self, prop_code: str, delete_mode: str) -> None:
        """
        删除种子未提及的道具定义及其关联规则。

        物理删除顺序：game_prop_rule（按 prop_code）→ prop_definition。

        :param prop_code: 道具编码。
        :param delete_mode: 删除模式。
        """
        if delete_mode == DELETE_MODE_PHYSICAL:
            self._prop_rule_import.physical_remove_by_prop_code(prop_code)
            for db_prop in self._prop_import.list_all(active_only=False):
                if db_prop.prop_code == prop_code:
                    self._prop_import.physical_remove(db_prop)
                    break
            return

        for db_rule in self._prop_rule_import.list_by_prop_code(prop_code, active_only=False):
            self._prop_rule_import.logical_disable(db_rule)
        for db_prop in self._prop_import.list_all(active_only=False):
            if db_prop.prop_code == prop_code:
                self._prop_import.logical_disable(db_prop)
                break

    def _remove_prop_rule(self, entity: GamePropRule, delete_mode: str) -> None:
        """
        删除单条游戏道具规则。

        :param entity: 道具规则实体。
        :param delete_mode: 删除模式。
        """
        if delete_mode == DELETE_MODE_PHYSICAL:
            self._prop_rule_import.physical_remove(entity)
        else:
            self._prop_rule_import.logical_disable(entity)

    def _remove_client_config(self, entity: GameClientConfig, delete_mode: str) -> None:
        """
        删除单条客户端配置。

        :param entity: 客户端配置实体。
        :param delete_mode: 删除模式。
        """
        if delete_mode == DELETE_MODE_PHYSICAL:
            self._client_config_import.physical_remove(entity)
        else:
            self._client_config_import.logical_disable(entity)

    def _remove_difficulty(self, entity: GameDifficulty, delete_mode: str) -> None:
        """
        删除单条难度配置。

        :param entity: 难度配置实体。
        :param delete_mode: 删除模式。
        """
        if delete_mode == DELETE_MODE_PHYSICAL:
            self._difficulty_import.physical_remove(entity)
        else:
            self._difficulty_import.logical_disable(entity)

    def _validate_request(self, request: ImportGameSeedRequest) -> None:
        """
        校验请求内重复键与跨字段引用。

        :param request: 导入请求体。
        :raises BizException: 校验失败时抛出。
        """
        prop_codes: Set[str] = set()
        for prop_item in request.props:
            _ensure_not_blank(prop_item.propCode, "props[].propCode")
            if prop_item.propCode in prop_codes:
                raise BizException(
                    ErrorCode.PARAM_ERROR,
                    message="请求内 propCode 重复: {}".format(prop_item.propCode),
                )
            prop_codes.add(prop_item.propCode)

        game_codes: Set[str] = set()
        for game_item in request.games:
            _ensure_not_blank(game_item.gameCode, "games[].gameCode")
            if game_item.gameCode in game_codes:
                raise BizException(
                    ErrorCode.PARAM_ERROR,
                    message="请求内 gameCode 重复: {}".format(game_item.gameCode),
                )
            game_codes.add(game_item.gameCode)
            self._validate_game_nested(game_item, prop_codes)

    def _validate_game_nested(self, game_item: GameSeedGame, request_prop_codes: Set[str]) -> None:
        """
        校验单个游戏下的嵌套项重复与道具引用。

        :param game_item: 游戏种子项。
        :param request_prop_codes: 本次请求中的 propCode 集合。
        :raises BizException: 校验失败时抛出。
        """
        difficulty_keys: Set[str] = set()
        for diff_item in game_item.difficulties:
            _ensure_not_blank(
                diff_item.difficultyCode,
                "games[{}].difficulties[].difficultyCode".format(game_item.gameCode),
            )
            if diff_item.difficultyCode in difficulty_keys:
                raise BizException(
                    ErrorCode.PARAM_ERROR,
                    message="游戏 {} 内 difficultyCode 重复: {}".format(
                        game_item.gameCode,
                        diff_item.difficultyCode,
                    ),
                )
            difficulty_keys.add(diff_item.difficultyCode)
            _ensure_json_serializable(
                diff_item.config,
                "games[{}].difficulties[{}].config".format(
                    game_item.gameCode,
                    diff_item.difficultyCode,
                ),
            )

        client_keys: Set[Tuple[str, str]] = set()
        for client_item in game_item.clientConfigs:
            if client_item.difficultyCode is not None:
                _ensure_not_blank(
                    client_item.difficultyCode,
                    "games[{}].clientConfigs[].difficultyCode".format(game_item.gameCode),
                )
            _ensure_not_blank(
                client_item.clientType,
                "games[{}].clientConfigs[].clientType".format(game_item.gameCode),
            )
            diff_key = client_item.difficultyCode if client_item.difficultyCode is not None else ""
            composite = (diff_key, client_item.clientType)
            if composite in client_keys:
                raise BizException(
                    ErrorCode.PARAM_ERROR,
                    message="游戏 {} 内 clientConfig 重复: difficultyCode={}, clientType={}".format(
                        game_item.gameCode,
                        client_item.difficultyCode,
                        client_item.clientType,
                    ),
                )
            client_keys.add(composite)
            _ensure_json_serializable(
                client_item.config,
                "games[{}].clientConfigs[{}].config".format(
                    game_item.gameCode,
                    client_item.clientType,
                ),
            )

        prop_rule_keys: Set[str] = set()
        for rule_item in game_item.propRules:
            _ensure_not_blank(
                rule_item.propCode,
                "games[{}].propRules[].propCode".format(game_item.gameCode),
            )
            if rule_item.propCode in prop_rule_keys:
                raise BizException(
                    ErrorCode.PARAM_ERROR,
                    message="游戏 {} 内 propCode 重复: {}".format(
                        game_item.gameCode,
                        rule_item.propCode,
                    ),
                )
            prop_rule_keys.add(rule_item.propCode)
            if not self._prop_code_exists(rule_item.propCode, request_prop_codes):
                raise BizException(
                    ErrorCode.PARAM_ERROR,
                    message="propRules.propCode 不存在: {}".format(rule_item.propCode),
                )
            _ensure_json_serializable(
                rule_item.rule,
                "games[{}].propRules[{}].rule".format(
                    game_item.gameCode,
                    rule_item.propCode,
                ),
            )

        _ensure_json_serializable(
            game_item.config,
            "games[{}].config".format(game_item.gameCode),
        )

    def _prop_code_exists(self, prop_code: str, request_prop_codes: Set[str]) -> bool:
        """
        判断道具编码是否存在于本次请求或数据库。

        :param prop_code: 道具编码。
        :param request_prop_codes: 本次请求 props 中的编码集合。
        :return: 是否存在。
        """
        if prop_code in request_prop_codes:
            return True
        return self._prop_definitions.get_by_prop_code(prop_code) is not None

    def _import_game(
        self,
        game_item: GameSeedGame,
        request_prop_codes: Set[str],
        result: ImportGameSeedResponse,
    ) -> None:
        """
        导入单个游戏及其嵌套配置。

        :param game_item: 游戏种子项。
        :param request_prop_codes: 本次请求 props 编码集合。
        :param result: 累计统计对象（原地修改）。
        """
        config_json = _serialize_optional_config(
            game_item.config,
            "games[{}].config".format(game_item.gameCode),
        )
        _, created = self._game_import.upsert(
            game_code=game_item.gameCode,
            game_name=game_item.gameName,
            game_sub_name=game_item.gameSubName,
            support_online=game_item.supportOnline,
            enabled=game_item.enabled,
            sort_no=game_item.sortNo,
            config_json=config_json,
        )
        if created:
            result.importedGames += 1
        else:
            result.updatedGames += 1

        for diff_item in game_item.difficulties:
            self._import_difficulty(game_item.gameCode, diff_item, result)

        for client_item in game_item.clientConfigs:
            self._import_client_config(game_item.gameCode, client_item, result)

        for rule_item in game_item.propRules:
            self._import_prop_rule(
                game_item.gameCode,
                rule_item,
                request_prop_codes=request_prop_codes,
                result=result,
            )

    def _import_difficulty(
        self,
        game_code: str,
        diff_item: GameSeedDifficulty,
        result: ImportGameSeedResponse,
    ) -> None:
        """
        导入单条难度配置。

        :param game_code: 游戏编码。
        :param diff_item: 难度种子项。
        :param result: 累计统计对象。
        """
        _, created = self._difficulty_import.upsert(
            game_code=game_code,
            difficulty_code=diff_item.difficultyCode,
            difficulty_name=diff_item.difficultyName,
            config=diff_item.config,
            enabled=diff_item.enabled,
            sort_no=diff_item.sortNo,
        )
        if created:
            result.importedDifficulties += 1
        else:
            result.updatedDifficulties += 1

    def _import_client_config(
        self,
        game_code: str,
        client_item: GameSeedClientConfig,
        result: ImportGameSeedResponse,
    ) -> None:
        """
        导入单条客户端配置。

        :param game_code: 游戏编码。
        :param client_item: 客户端配置种子项。
        :param result: 累计统计对象。
        """
        _, created = self._client_config_import.upsert(
            game_code=game_code,
            difficulty_code=client_item.difficultyCode,
            client_type=client_item.clientType,
            config=client_item.config,
            enabled=client_item.enabled,
        )
        if created:
            result.importedClientConfigs += 1
        else:
            result.updatedClientConfigs += 1

    def _import_prop_rule(
        self,
        game_code: str,
        rule_item: GameSeedPropRule,
        request_prop_codes: Set[str],
        result: ImportGameSeedResponse,
    ) -> None:
        """
        导入单条游戏道具规则。

        :param game_code: 游戏编码。
        :param rule_item: 道具规则种子项。
        :param request_prop_codes: 本次请求 props 编码集合。
        :param result: 累计统计对象。
        """
        if not self._prop_code_exists(rule_item.propCode, request_prop_codes):
            raise BizException(
                ErrorCode.PARAM_ERROR,
                message="propRules.propCode 不存在: {}".format(rule_item.propCode),
            )
        _, created = self._prop_rule_import.upsert(
            game_code=game_code,
            prop_code=rule_item.propCode,
            sort_no=rule_item.sortNo,
            price=rule_item.price,
            max_use_per_match=rule_item.maxUsePerMatch,
            trigger_type=rule_item.triggerType,
            effect_type=rule_item.effectType,
            rule=rule_item.rule,
            enabled=rule_item.enabled,
        )
        if created:
            result.importedPropRules += 1
        else:
            result.updatedPropRules += 1
