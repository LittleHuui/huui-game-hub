"""策略回合制运行时通用 Pydantic 模型。"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Annotated

from app.modules.strategy_turn.terminal_schemas import TerminalMetadata


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


class EnumeratedActionInput(BaseModel):
    """枚举型动作提交入参。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["ENUMERATED"]
    actionId: str = Field(min_length=1, description="服务端下发的枚举动作 ID")


class ComposedActionInput(BaseModel):
    """构造型动作提交入参。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["COMPOSED"]
    selection: Dict[str, Any] = Field(default_factory=dict, description="客户端构造的选择内容")


ActionInput = Annotated[
    Union[EnumeratedActionInput, ComposedActionInput],
    Field(discriminator="kind"),
]


class ActionSubmission(BaseModel):
    """外部不可信动作意图。"""

    model_config = ConfigDict(extra="forbid")

    actionType: str = Field(min_length=1, description="动作类型")
    input: ActionInput


class ResolvedGameAction(BaseModel):
    """已解析、校验并归一化的可执行动作。"""

    model_config = ConfigDict(extra="forbid")

    actionId: str = Field(min_length=1, description="具体动作 ID")
    actionType: str = Field(min_length=1, description="动作类型")
    playerId: str = Field(min_length=1, description="行动玩家 ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="标准化动作载荷")


class EnumeratedActionOption(BaseModel):
    """枚举动作的一个可选项。"""

    model_config = ConfigDict(extra="forbid")

    actionId: str = Field(min_length=1, description="可提交的动作 ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="动作载荷")
    selection: Dict[str, Any] = Field(default_factory=dict, description="前端选择信息")


class EnumeratedActionOffer(BaseModel):
    """枚举型动作能力声明。"""

    model_config = ConfigDict(extra="forbid")

    actionType: str = Field(min_length=1, description="动作类型")
    interactionMode: Literal["ENUMERATED"]
    options: List[EnumeratedActionOption] = Field(default_factory=list, description="枚举选项")


class ComposedActionCapability(BaseModel):
    """构造型动作能力说明。"""

    model_config = ConfigDict(extra="forbid")

    selectionSource: str = Field(min_length=1, description="选择来源")
    selectionMode: str = Field(min_length=1, description="选择模式")
    minPick: int = Field(default=0, ge=0, description="最少选择数量")
    maxPick: int = Field(default=0, ge=0, description="最多选择数量")
    supportsPreview: bool = Field(default=False, description="是否支持预览")
    supportsSuggestions: bool = Field(default=False, description="是否支持提示")


class ComposedActionOffer(BaseModel):
    """构造型动作能力声明。"""

    model_config = ConfigDict(extra="forbid")

    actionType: str = Field(min_length=1, description="动作类型")
    interactionMode: Literal["COMPOSED"]
    capability: ComposedActionCapability


ActionOffer = Annotated[
    Union[EnumeratedActionOffer, ComposedActionOffer],
    Field(discriminator="interactionMode"),
]


class GameStateProjection(BaseModel):
    """面向单个玩家的状态投影。"""

    model_config = ConfigDict(extra="forbid")

    phase: str = Field(description="对局阶段")
    currentPlayerId: Optional[str] = Field(default=None, description="当前行动玩家")
    publicState: Dict[str, Any] = Field(default_factory=dict, description="公开状态")
    privateState: Dict[str, Any] = Field(default_factory=dict, description="视角玩家私有状态")


class ActionPreview(BaseModel):
    """构造动作的只读预览结果。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["VALID", "INVALID", "INCOMPLETE"]
    actionType: str = Field(min_length=1, description="动作类型")
    summary: Dict[str, Any] = Field(default_factory=dict, description="可展示摘要")
    reason: Optional[str] = Field(default=None, description="无效或不完整原因")


class ActionCandidate(BaseModel):
    """可用于提示或自动决策的候选动作。"""

    model_config = ConfigDict(extra="forbid")

    candidateId: str = Field(min_length=1, description="候选 ID")
    actionType: str = Field(min_length=1, description="动作类型")
    submission: ActionSubmission = Field(description="最终选中后重新提交的动作意图")
    normalizedAction: ResolvedGameAction = Field(description="仅供当前状态评分的标准化动作")
    features: Dict[str, Any] = Field(default_factory=dict, description="候选评分特征")


class ActionCandidatePage(BaseModel):
    """动作候选分页结果。"""

    model_config = ConfigDict(extra="forbid")

    candidates: List[ActionCandidate] = Field(default_factory=list, description="候选列表")
    nextCursor: Optional[str] = Field(default=None, description="下一页游标")


class CandidateScore(BaseModel):
    """动作候选评分结果。"""

    model_config = ConfigDict(extra="forbid")

    candidateId: str = Field(min_length=1, description="候选 ID")
    score: float = Field(description="候选分数")
    reason: str = Field(default="", description="评分原因")


class ActionDecisionContext(BaseModel):
    """自动决策上下文。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str = Field(min_length=1, description="游戏编码")
    roomId: Optional[str] = Field(default=None, description="房间 ID")
    playerId: str = Field(min_length=1, description="决策玩家 ID")
    runtimeRule: StrategyTurnRuntimeRule = Field(description="运行时规则")
    state: Dict[str, Any] = Field(default_factory=dict, description="运行时状态")
    version: int = Field(default=0, ge=0, description="房间版本")


class DomainEventDraft(BaseModel):
    """生命周期产生的领域事件草稿（不含 sequence 与 createdAt）。"""

    model_config = ConfigDict(extra="forbid")

    eventType: str = Field(min_length=1, description="事件类型")
    playerId: Optional[str] = Field(default=None, description="关联玩家 ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="事件载荷")


class InitialStateOutcome(BaseModel):
    """生命周期构建初始状态后的结果。"""

    model_config = ConfigDict(extra="forbid")

    state: Dict[str, Any] = Field(default_factory=dict, description="初始对局状态")
    events: List[DomainEventDraft] = Field(default_factory=list, description="开局产生的事件草稿")
    gameOver: bool = Field(default=False, description="初始状态是否已终局")


class ActionOutcome(BaseModel):
    """生命周期执行动作后的结果。"""

    model_config = ConfigDict(extra="forbid")

    resolvedAction: ResolvedGameAction = Field(description="已应用的标准化动作")
    state: Dict[str, Any] = Field(default_factory=dict, description="执行后的状态")
    events: List[DomainEventDraft] = Field(default_factory=list, description="本次动作产生的事件草稿")
    gameOver: bool = Field(default=False, description="执行后是否已终局")


class AdvanceOutcome(BaseModel):
    """生命周期自动推进后的结果。"""

    model_config = ConfigDict(extra="forbid")

    state: Dict[str, Any] = Field(default_factory=dict, description="推进后的状态")
    events: List[DomainEventDraft] = Field(default_factory=list, description="本次推进产生的事件草稿")
    gameOver: bool = Field(default=False, description="推进后是否已终局")


class GameEvent(BaseModel):
    """对局事件日志条目（用于回放、同步或推送）。"""

    model_config = ConfigDict(extra="forbid")

    eventType: str
    sequence: int = Field(ge=0, description="对局内单调递增序号")
    playerId: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    createdAt: int = Field(description="事件发生时间，Unix 毫秒")


class HintSuggestion(BaseModel):
    """面向真人玩家的公开动作提示。"""

    model_config = ConfigDict(extra="forbid")

    selection: Dict[str, Any] = Field(default_factory=dict, description="前端选择信息")
    summary: Dict[str, Any] = Field(default_factory=dict, description="可展示摘要")


class HintSuggestionPage(BaseModel):
    """真人动作提示分页结果。"""

    model_config = ConfigDict(extra="forbid")

    items: List[HintSuggestion] = Field(default_factory=list, description="提示列表")
    nextCursor: Optional[str] = Field(default=None, description="下一页游标")


class GameView(BaseModel):
    """面向单个玩家的对局视图（含私有与公有信息）。"""

    model_config = ConfigDict(extra="forbid")

    roomId: Optional[str] = None
    gameCode: str
    viewerPlayerId: str
    phase: str = Field(description="对局阶段标识，由具体规则引擎定义")
    currentPlayerId: Optional[str] = None
    actionOffers: List[ActionOffer] = Field(default_factory=list)
    publicState: Dict[str, Any] = Field(default_factory=dict)
    privateState: Dict[str, Any] = Field(default_factory=dict)
    isGameOver: bool = False
    terminalMetadata: Optional[TerminalMetadata] = Field(
        default=None,
        description="终局展示与平台结算状态",
    )
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
    commitVersion: Optional[int] = Field(
        default=None,
        ge=0,
        description="写入 Redis 时的对局版本号，用于读取一致性校验",
    )
    terminalMetadata: Optional[TerminalMetadata] = Field(
        default=None,
        description="终局阶段元数据（如结算状态）",
    )
    terminalDirective: Optional["TerminalDirective"] = Field(
        default=None,
        description="游戏模块提供的平台级终局指令",
    )


class TheoreticalPlayerSettlement(BaseModel):
    """平台理论结算中的单玩家盈亏。"""

    model_config = ConfigDict(extra="forbid")

    playerId: str = Field(min_length=1)
    expectedDelta: int = Field(description="理论积分变动，赢家为正、输家为负")


class TheoreticalSettlement(BaseModel):
    """游戏层输出的零和理论结算。"""

    model_config = ConfigDict(extra="forbid")

    settlementType: str = Field(min_length=1)
    playerSettlements: List[TheoreticalPlayerSettlement] = Field(default_factory=list)
    ruleDetails: Dict[str, Any] = Field(default_factory=dict)


class TerminalDirective(BaseModel):
    """游戏模块向房间平台提供的终局指令。"""

    model_config = ConfigDict(extra="forbid")

    requiresPlatformSettlement: bool = Field(default=False)
    settlementType: Optional[str] = Field(default=None)
    theoreticalSettlement: Optional[TheoreticalSettlement] = Field(default=None)
    displayDurationMs: int = Field(default=3000, ge=0)


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
    """提交已解析玩家操作命令。"""

    model_config = ConfigDict(extra="forbid")

    action: ResolvedGameAction


class ApplyActionResult(BaseModel):
    """提交玩家操作结果。"""

    model_config = ConfigDict(extra="forbid")

    snapshot: RuntimeSnapshot
    newEvents: List[GameEvent] = Field(default_factory=list, description="本次操作产生的新事件")
