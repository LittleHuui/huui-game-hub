"""UNO 对局内部状态 Pydantic 模型（camelCase 字段）。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.common.camel_schema import CAMEL_MODEL_CONFIG
from app.modules.strategy_turn.schemas import GameEvent


class UnoCard(BaseModel):
    """单张牌实例。"""

    model_config = CAMEL_MODEL_CONFIG

    cardInstanceId: str = Field(min_length=1, description="牌实例唯一 ID")
    cardCode: str = Field(min_length=1, description="牌型编码")
    color: Optional[str] = Field(default=None, description="花色，万能牌为 null")
    cardType: str = Field(min_length=1, description="牌型标识")
    numberValue: Optional[int] = Field(default=None, ge=0, le=9, description="数字牌点数")


class UnoPlayerState(BaseModel):
    """单个玩家在对局中的状态。"""

    model_config = CAMEL_MODEL_CONFIG

    playerId: str = Field(min_length=1, description="玩家 ID")
    handCards: List[UnoCard] = Field(default_factory=list, description="手牌列表")
    seatStatus: str = Field(default="PLAYING", description="座位状态：PLAYING / SPECTATING / LEFT")
    isAi: bool = Field(default=False, description="是否为 AI 玩家")
    isFinished: bool = Field(default=False, description="是否已出完手牌")
    finishRank: Optional[int] = Field(default=None, ge=1, description="完成名次")


class UnoPendingDraw(BaseModel):
    """待结算的抽牌惩罚（如 +2/+4）。"""

    model_config = CAMEL_MODEL_CONFIG

    amount: int = Field(ge=0, description="待抽张数")
    stackable: bool = Field(default=False, description="是否允许叠加")
    sourceCardType: Optional[str] = Field(
        default=None,
        description="触发待抽的牌型规则键，如 DRAW_TWO / WILD_DRAW4",
    )


class UnoDiscardRecentCard(BaseModel):
    """弃牌区最近有效出牌记录。"""

    model_config = CAMEL_MODEL_CONFIG

    cardInstanceId: str = Field(min_length=1, description="牌实例唯一 ID")
    cardCode: str = Field(min_length=1, description="牌型编码")
    playerId: Optional[str] = Field(default=None, description="出牌玩家 ID")
    sequence: int = Field(ge=0, description="对应出牌事件序号")


class UnoRankingItem(BaseModel):
    """玩家完成名次记录。"""

    model_config = CAMEL_MODEL_CONFIG

    playerId: str = Field(min_length=1, description="玩家 ID")
    rank: int = Field(ge=1, description="名次")
    finishedAt: Optional[int] = Field(default=None, description="完成时间，Unix 毫秒")


class UnoRuntimeState(BaseModel):
    """UNO 对局运行时完整状态。"""

    model_config = CAMEL_MODEL_CONFIG

    phase: str = Field(default="playing", description="对局阶段：playing / finished")
    playerIds: List[str] = Field(min_length=2, description="按座位顺序的玩家 ID")
    players: Dict[str, UnoPlayerState] = Field(default_factory=dict, description="玩家状态映射")
    drawPile: List[UnoCard] = Field(default_factory=list, description="抽牌堆")
    discardPile: List[UnoCard] = Field(default_factory=list, description="弃牌堆")
    topDiscard: Optional[UnoCard] = Field(default=None, description="当前顶牌")
    currentPlayerId: str = Field(min_length=1, description="当前行动玩家 ID")
    playDirection: int = Field(default=1, description="出牌方向：1 顺时针，-1 逆时针")
    pendingDraw: Optional[UnoPendingDraw] = Field(default=None, description="待结算抽牌")
    currentColor: Optional[str] = Field(default=None, description="当前生效花色")
    rankings: List[UnoRankingItem] = Field(default_factory=list, description="已完成玩家名次")
    deckSetCount: int = Field(ge=1, description="当前牌局使用的牌组套数")
    drewThisTurn: bool = Field(default=False, description="本回合是否已抽牌且待决定是否出牌")
    lastDrawnCardInstanceId: Optional[str] = Field(
        default=None,
        description="本回合最近一次抽到的牌实例 ID",
    )
    effectAdvanceHandled: bool = Field(
        default=False,
        description="牌面效果已处理回合推进时为 True，避免 advance 重复推进",
    )
    drawDecision: Optional[str] = Field(
        default=None,
        description="最近一次抽牌后的决策状态标记，例如 FORCED_DRAW_AND_PLAY / DRAW_END_TURN 等",
    )
    drawSource: Optional[str] = Field(
        default=None,
        description="最近一次抽牌来源：voluntary / forced / pendingDraw 等",
    )
    discardPileRecentCards: List[UnoDiscardRecentCard] = Field(
        default_factory=list,
        description="最近两轮有效出牌（不含摸牌等非出牌事件）",
    )
    currentTurnStartedAt: Optional[int] = Field(
        default=None,
        description="当前回合开始时间，Unix 毫秒",
    )
    turnTimeoutSeconds: int = Field(default=60, ge=1, description="回合倒计时秒数")
    currentTurnDeadlineAt: Optional[int] = Field(
        default=None,
        description="当前回合截止时间，Unix 毫秒",
    )


class UnoRuleContext(BaseModel):
    """规则判定上下文：聚合运行时状态与规则参数。"""

    model_config = CAMEL_MODEL_CONFIG

    runtimeState: UnoRuntimeState
    runtimeRule: Dict[str, Any] = Field(default_factory=dict, description="运行时规则快照")
    roomConfig: Dict[str, Any] = Field(default_factory=dict, description="房间玩法配置")
    actingPlayerId: Optional[str] = Field(default=None, description="当前出牌玩家 ID")
    newEvents: List[GameEvent] = Field(default_factory=list, description="本次规则处理产生的事件")
    nextEventSequence: int = Field(default=0, ge=0, description="下一条事件序号")
