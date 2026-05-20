"""游戏域 Pydantic 模型。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from app.common.base_entity import BaseEntityResponse


# ---------------------------------------------------------------------------
# GameDefinition
# ---------------------------------------------------------------------------

class GameDefinitionRead(BaseModel):
    """游戏定义响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    game_code: str
    game_name: str
    game_sub_name: Optional[str] = None
    support_online: int
    enabled: int
    sort_no: int
    config_json: Optional[str] = None
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


# ---------------------------------------------------------------------------
# GameDifficulty
# ---------------------------------------------------------------------------

class GameDifficultyRead(BaseModel):
    """难度配置响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    game_code: str
    difficulty_code: str
    difficulty_name: str
    config_json: str
    enabled: int
    sort_no: int
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


# ---------------------------------------------------------------------------
# GameClientConfig
# ---------------------------------------------------------------------------

class GameClientConfigRead(BaseModel):
    """客户端配置响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    game_code: str
    difficulty_code: Optional[str] = None
    client_type: str
    config_json: str
    enabled: int
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


# ---------------------------------------------------------------------------
# 游戏摘要
# ---------------------------------------------------------------------------

class GameSummaryResponse(BaseModel):
    """游戏列表摘要响应。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    gameName: str
    gameSubName: Optional[str] = None
    supportOnline: bool
    enabled: bool
    sortNo: int


class GameDifficultyResponse(BaseEntityResponse):
    """游戏难度配置响应。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    difficultyCode: str
    difficultyName: str
    config: Dict[str, Any]
    enabled: bool
    sortNo: int


class GameClientConfigResponse(BaseEntityResponse):
    """游戏客户端适配配置响应。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    difficultyCode: Optional[str] = None
    clientType: str
    config: Dict[str, Any]
    enabled: bool


class GamePropRuleResponse(BaseEntityResponse):
    """游戏道具规则响应。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    propCode: str
    propName: Optional[str] = None
    price: int
    maxUsePerMatch: Optional[int] = None
    triggerType: Optional[str] = None
    effectType: Optional[str] = None
    rule: Optional[Dict[str, Any]] = None
    enabled: bool
    sortNo: int


class GameConfigResponse(BaseModel):
    """GET /games/{gameCode}/config 响应体。"""

    model_config = ConfigDict(extra="forbid")

    game: GameSummaryResponse
    difficulties: List[GameDifficultyResponse] = []
    clientConfigs: List[GameClientConfigResponse] = []
    props: List[GamePropRuleResponse] = []


class GameClientConfigListData(BaseModel):
    """GET /games/{game_code}/client-config 响应体。"""

    items: List[GameClientConfigRead]
