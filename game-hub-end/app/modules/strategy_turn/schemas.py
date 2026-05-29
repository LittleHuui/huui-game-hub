"""策略回合制运行时通用 Pydantic 模型。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrategyTurnRoomRule(BaseModel):
    """房间级规则配置（建房时确定）。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    mode: str
    playerCount: int = Field(ge=2, description="参与玩家数量")
    config: Dict[str, Any] = Field(default_factory=dict, description="玩法扩展配置")


class StrategyTurnRuntimeRule(BaseModel):
    """对局运行时生效规则（房间规则与游戏定义合并后的快照）。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    mode: str
    playerIds: List[str] = Field(min_length=2, description="按座位顺序排列的玩家 ID 列表")
    config: Dict[str, Any] = Field(default_factory=dict, description="运行时扩展配置")


class StrategyTurnRuleDefinition(BaseModel):
    """已注册游戏的策略回合规则定义种子（供 GET rule-definition 返回）。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    ruleVersion: str
    roomRule: Dict[str, Any] = Field(
        default_factory=dict,
        description="房间级规则种子，建房时合并",
    )
    runtimeRule: Dict[str, Any] = Field(
        default_factory=dict,
        description="对局运行时规则种子",
    )
    actionTypes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="支持的操作类型定义列表",
    )
    assets: Dict[str, Any] = Field(
        default_factory=dict,
        description="规则相关静态资源引用",
    )


class LegalAction(BaseModel):
    """当前玩家在合法时机可执行的操作。"""

    model_config = ConfigDict(extra="forbid")

    actionType: str
    actionId: str = Field(description="本回合内唯一标识，用于提交校验")
    playerId: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    selection: Dict[str, Any] = Field(default_factory=dict)


class GameAction(BaseModel):
    """玩家提交并待规则引擎校验的操作。"""

    model_config = ConfigDict(extra="forbid")

    actionId: str = Field(min_length=1, description="合法操作 ID，与 LegalAction.actionId 一致")
    playerId: str
    actionType: str = Field(default="", description="由规则引擎根据 actionId 匹配后补齐")
    payload: Dict[str, Any] = Field(default_factory=dict)
    clientId: Optional[str] = Field(default=None, description="客户端幂等 ID，可选")


class GameEvent(BaseModel):
    """对局事件日志条目（用于回放、同步或推送）。"""

    model_config = ConfigDict(extra="forbid")

    eventType: str
    sequence: int = Field(ge=0, description="对局内单调递增序号")
    playerId: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    createdAt: int = Field(description="事件发生时间，Unix 毫秒")


class GameView(BaseModel):
    """面向单个玩家的对局视图（含私有与公有信息）。"""

    model_config = ConfigDict(extra="forbid")

    roomId: Optional[str] = None
    gameCode: str
    viewerPlayerId: str
    phase: str = Field(description="对局阶段标识，由具体规则引擎定义")
    currentPlayerId: Optional[str] = None
    legalActions: List[LegalAction] = Field(default_factory=list)
    publicState: Dict[str, Any] = Field(default_factory=dict)
    privateState: Dict[str, Any] = Field(default_factory=dict)
    isGameOver: bool = False
    version: int = Field(default=0, ge=0, description="房间对局版本号，用于客户端去重")
    events: List[GameEvent] = Field(
        default_factory=list,
        description="本帧待播放事件；查询视图为空，开始/提交操作时为增量或首帧事件",
    )


class RuntimeSnapshot(BaseModel):
    """策略回合制对局运行时快照（由上层持久化到 Redis 等）。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    roomId: Optional[str] = None
    runtimeRule: StrategyTurnRuntimeRule
    state: Dict[str, Any] = Field(default_factory=dict, description="规则引擎维护的对局状态")
    eventLog: List[GameEvent] = Field(default_factory=list, description="对局事件日志")
    eventSequence: int = Field(default=0, ge=0, description="下一条事件序号")
    startedAt: int = Field(description="对局开始时间，Unix 毫秒")
    updatedAt: int = Field(description="快照更新时间，Unix 毫秒")
    isGameOver: bool = False


class StartGameCommand(BaseModel):
    """开始对局命令。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    runtimeRule: StrategyTurnRuntimeRule
    roomId: Optional[str] = None


class StartGameResult(BaseModel):
    """开始对局结果。"""

    model_config = ConfigDict(extra="forbid")

    snapshot: RuntimeSnapshot
    newEvents: List[GameEvent] = Field(default_factory=list, description="开局产生的新事件")


class ApplyActionCommand(BaseModel):
    """提交玩家操作命令。"""

    model_config = ConfigDict(extra="forbid")

    action: GameAction


class ApplyActionResult(BaseModel):
    """提交玩家操作结果。"""

    model_config = ConfigDict(extra="forbid")

    snapshot: RuntimeSnapshot
    newEvents: List[GameEvent] = Field(default_factory=list, description="本次操作产生的新事件")
