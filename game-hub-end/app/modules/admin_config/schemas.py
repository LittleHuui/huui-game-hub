"""管理配置导入 Pydantic 模型。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.common.camel_schema import CAMEL_MODEL_CONFIG, camel_field


class GameSeedProp(BaseModel):
    """平台道具定义种子项。"""

    model_config = CAMEL_MODEL_CONFIG

    propCode: str = camel_field("propCode", min_length=1)
    propName: str = camel_field("propName", min_length=1)
    description: Optional[str] = None
    icon: Optional[str] = None
    basePrice: int = camel_field("basePrice", ge=0)
    enabled: bool


class GameSeedDifficulty(BaseModel):
    """游戏难度种子项。"""

    model_config = CAMEL_MODEL_CONFIG

    difficultyCode: str = camel_field("difficultyCode", min_length=1)
    difficultyName: str = camel_field("difficultyName", min_length=1)
    enabled: bool
    sortNo: int = camel_field("sortNo")
    config: Dict[str, Any]


class GameSeedClientConfig(BaseModel):
    """游戏客户端配置种子项。"""

    model_config = CAMEL_MODEL_CONFIG

    difficultyCode: Optional[str] = camel_field("difficultyCode", default=None)
    clientType: str = camel_field("clientType", min_length=1)
    enabled: bool
    config: Dict[str, Any]


class GameSeedPropRule(BaseModel):
    """游戏道具规则种子项。"""

    model_config = CAMEL_MODEL_CONFIG

    propCode: str = camel_field("propCode", min_length=1)
    price: int = Field(ge=0)
    maxUsePerMatch: Optional[int] = camel_field("maxUsePerMatch", default=None, ge=0)
    triggerType: Optional[str] = None
    effectType: Optional[str] = None
    enabled: bool
    rule: Dict[str, Any]


class GameSeedGame(BaseModel):
    """游戏定义种子项。"""

    model_config = CAMEL_MODEL_CONFIG

    gameCode: str = camel_field("gameCode", min_length=1)
    gameName: str = camel_field("gameName", min_length=1)
    gameSubName: Optional[str] = camel_field("gameSubName", default=None)
    supportOnline: bool = camel_field("supportOnline")
    enabled: bool
    sortNo: int = camel_field("sortNo")
    config: Dict[str, Any]
    difficulties: List[GameSeedDifficulty] = Field(default_factory=list)
    clientConfigs: List[GameSeedClientConfig] = Field(default_factory=list)
    propRules: List[GameSeedPropRule] = Field(default_factory=list)


class ImportGameSeedRequest(BaseModel):
    """游戏种子配置导入请求体。"""

    model_config = CAMEL_MODEL_CONFIG

    props: List[GameSeedProp] = Field(default_factory=list)
    games: List[GameSeedGame] = Field(default_factory=list)


class ImportGameSeedResponse(BaseModel):
    """游戏种子配置导入结果。"""

    model_config = CAMEL_MODEL_CONFIG

    importedGames: int = 0
    importedDifficulties: int = 0
    importedClientConfigs: int = 0
    importedProps: int = 0
    importedPropRules: int = 0
    updatedGames: int = 0
    updatedDifficulties: int = 0
    updatedClientConfigs: int = 0
    updatedProps: int = 0
    updatedPropRules: int = 0
