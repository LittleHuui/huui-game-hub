"""只能在线游玩的游戏规则种子 Pydantic 模型。"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from app.common.camel_schema import CAMEL_MODEL_CONFIG


class CardDefinition(BaseModel):
    """单种牌的定义及在一套牌组中的数量。"""

    model_config = CAMEL_MODEL_CONFIG

    cardCode: str = Field(min_length=1, description="牌型唯一编码")
    color: Optional[str] = Field(default=None, description="花色，万能牌为 null")
    cardType: str = Field(
        min_length=1,
        description="牌型：NUMBER / DISABLE / REVERSE / DRAW_TWO / WILD / WILD_DRAW4",
    )
    numberValue: Optional[int] = Field(default=None, ge=0, le=9, description="数字牌点数")
    countPerDeckSet: int = Field(ge=1, description="每套牌组中该牌型的张数")
    image: str = Field(min_length=1, description="牌面图片资源路径或 URL")
    description: str = Field(min_length=1, description="牌型说明")


class GameRuleInfo(BaseModel):
    """游戏级规则元信息（牌组规模、静态资源等）。"""

    model_config = CAMEL_MODEL_CONFIG

    description: str = Field(min_length=1, description="游戏规则简介")
    ruleDescription: str = Field(min_length=1, description="玩法详细说明")
    cardBackImage: str = Field(min_length=1, description="牌背图相对资源路径")
    singleDeckCardCount: int = Field(ge=1, description="单套牌组总张数")


class RoomRule(BaseModel):
    """房间级规则（人数、AI、过期等）。"""

    model_config = CAMEL_MODEL_CONFIG

    minPlayers: int = Field(ge=2, description="最少玩家人数")
    maxPlayers: int = Field(ge=2, description="最多玩家人数")
    allowAi: bool = Field(description="是否允许 AI 玩家")
    minAiCount: int = Field(ge=0, description="AI 数量下限")
    maxAiCount: int = Field(ge=0, description="AI 数量上限")
    defaultExpireSeconds: int = Field(ge=1, description="房间默认 Redis TTL（秒）")


class InitialDeckSetRule(BaseModel):
    """按人数决定开局牌组套数的规则项。"""

    model_config = CAMEL_MODEL_CONFIG

    minPlayerCount: int = Field(ge=1, description="适用最少玩家数（含）")
    maxPlayerCount: int = Field(ge=1, description="适用最多玩家数（含）")
    deckSetCount: int = Field(ge=1, description="开局使用的牌组套数")


class RoomConfigFieldVisibleWhen(BaseModel):
    """建房表单字段可见性条件。"""

    model_config = CAMEL_MODEL_CONFIG

    field: str = Field(min_length=1, description="依赖的其它配置键")
    equals: Any = Field(description="依赖字段须等于的值")


class RoomConfigFieldOption(BaseModel):
    """房间配置枚举选项。"""

    model_config = CAMEL_MODEL_CONFIG

    value: Union[str, int, float, bool] = Field(description="选项值")
    label: str = Field(min_length=1, description="展示文案")


class RoomConfigFieldDefinition(BaseModel):
    """建房表单字段定义。"""

    model_config = CAMEL_MODEL_CONFIG

    key: str = Field(min_length=1, description="配置键")
    type: str = Field(min_length=1, description="字段类型：boolean / number / enum")
    label: str = Field(min_length=1, description="展示标签")
    defaultValue: Any = Field(description="默认值")
    options: Optional[List[RoomConfigFieldOption]] = Field(
        default=None,
        description="enum 类型可选列表",
    )
    min: Optional[int] = Field(default=None, description="number 类型最小值")
    max: Optional[int] = Field(default=None, description="number 类型最大值")
    description: Optional[str] = Field(default=None, description="字段说明")
    visibleWhen: Optional[RoomConfigFieldVisibleWhen] = Field(
        default=None,
        description="满足条件时才展示并提交该字段",
    )


class ExtensionConfig(BaseModel):
    """游戏扩展配置占位（按游戏按需扩展字段）。"""

    model_config = CAMEL_MODEL_CONFIG


class UnoExtensionConfig(ExtensionConfig):
    """UNO 扩展配置（非建房表单字段）。"""

    initialDeckSetRules: List[InitialDeckSetRule] = Field(
        min_length=1,
        description="按人数映射开局牌组套数",
    )


class OnlineGameRuleSeed(BaseModel):
    """只能在线游玩的游戏规则种子。"""

    model_config = CAMEL_MODEL_CONFIG

    gameCode: str = Field(min_length=1, description="游戏编码")
    ruleVersion: str = Field(min_length=1, description="规则版本标识")
    runtimeType: str = Field(min_length=1, description="前端运行时类型")
    gameRuleInfo: GameRuleInfo
    cardDefinitions: List[CardDefinition] = Field(min_length=1)
    roomRule: RoomRule
    roomConfigSchema: List[RoomConfigFieldDefinition] = Field(
        min_length=1,
        description="建房表单字段定义列表",
    )
    extensionConfig: Dict[str, Any] = Field(
        default_factory=dict,
        description="游戏扩展配置（按游戏扩展字段）",
    )


def resolve_room_config_defaults(seed: OnlineGameRuleSeed) -> Dict[str, Any]:
    """
    根据规则种子表单字段与扩展配置生成房间配置默认值。

    :param seed: 在线游戏规则种子。
    :return: 房间配置字典。
    """
    defaults: Dict[str, Any] = {}
    for field in seed.roomConfigSchema:
        defaults[field.key] = field.defaultValue
    extension = seed.extensionConfig
    if isinstance(extension, dict):
        rules = extension.get("initialDeckSetRules")
        if isinstance(rules, list):
            defaults["initialDeckSetRules"] = rules
    return defaults
