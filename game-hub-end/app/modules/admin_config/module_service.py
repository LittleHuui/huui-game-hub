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

    def import_game_seed(self, request: ImportGameSeedRequest) -> ImportGameSeedResponse:
        """
        导入统一游戏种子配置（upsert，不删除未提及记录）。

        :param request: 导入请求体。
        :return: 导入统计结果。
        :raises BizException: 校验失败时抛出。
        """
        self._validate_request(request)
        result = ImportGameSeedResponse()
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

        return result

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
