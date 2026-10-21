"""斗地主对局内部状态 Pydantic 模型（camelCase 字段）。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.common.camel_schema import CAMEL_MODEL_CONFIG


class DoudizhuCard(BaseModel):
    """单张斗地主牌实例。"""

    model_config = CAMEL_MODEL_CONFIG

    cardInstanceId: str = Field(min_length=1, description="牌实例唯一 ID")
    cardCode: str = Field(min_length=1, description="牌型编码")
    category: str = Field(min_length=1, description="牌类：STANDARD / JOKER")
    rankCode: str = Field(min_length=1, description="点数或功能编码")
    rankValue: int = Field(description="可排序点数")
    suitCode: Optional[str] = Field(default=None, description="花色编码，王牌为 null")
    suitLabel: Optional[str] = Field(default=None, description="花色展示文案，王牌为 null")
    displayLabel: str = Field(min_length=1, description="牌面展示标签")
    displayColor: str = Field(min_length=1, description="展示颜色：BLACK / RED")
    image: str = Field(min_length=1, description="牌面图片资源路径")
    isJoker: bool = Field(default=False, description="是否为大小王")
    isLaizi: bool = Field(default=False, description="是否为癞子牌")


class DoudizhuDealResult(BaseModel):
    """斗地主初始发牌结果。"""

    model_config = CAMEL_MODEL_CONFIG

    playerHands: Dict[str, List[DoudizhuCard]] = Field(
        default_factory=dict,
        description="各玩家手牌映射",
    )
    bottomCards: List[DoudizhuCard] = Field(
        default_factory=list,
        description="底牌列表",
    )
    remainingCards: List[DoudizhuCard] = Field(
        default_factory=list,
        description="发牌后剩余牌（通常为空）",
    )


class DoudizhuLaiziUsage(BaseModel):
    """癞子在牌型归一中的使用明细。"""

    model_config = CAMEL_MODEL_CONFIG

    laiziCardInstanceId: str = Field(min_length=1, description="癞子牌实例 ID")
    assignedRankCode: str = Field(min_length=1, description="归一后替代的点数编码")
    assignedRankValue: int = Field(description="归一后替代的点数值")


class DoudizhuComboInfo(BaseModel):
    """斗地主牌型识别结果，供出牌校验与托管评分使用。"""

    model_config = CAMEL_MODEL_CONFIG

    comboType: str = Field(min_length=1, description="牌型编码")
    cardInstanceIds: List[str] = Field(
        default_factory=list,
        description="参与牌型的牌实例 ID 列表",
    )
    mainRankCode: str = Field(min_length=1, description="主牌点数编码")
    mainRankValue: int = Field(description="主牌点数值，用于牌型比较")
    cardCount: int = Field(description="出牌总张数")
    chainLength: int = Field(default=1, description="顺子/连对/飞机主体连续组数")
    attachmentType: Optional[str] = Field(
        default=None,
        description="附带牌类型：NONE / SINGLE / PAIR",
    )
    isBomb: bool = Field(default=False, description="是否为炸弹类（含癞子炸弹）")
    isRocket: bool = Field(default=False, description="是否为王炸")
    isLaiziCombo: bool = Field(default=False, description="是否使用了癞子")
    isLaiziBomb: bool = Field(default=False, description="是否为癞子炸弹")
    isNaturalBomb: bool = Field(default=False, description="是否为天然炸弹（四张同点非癞子）")
    naturalCardCount: int = Field(default=0, description="天然牌张数")
    laiziCardCount: int = Field(default=0, description="癞子牌张数")
    normalizedRankValues: List[int] = Field(
        default_factory=list,
        description="归一后各主牌点数值列表",
    )
    laiziUsage: List[DoudizhuLaiziUsage] = Field(
        default_factory=list,
        description="癞子归一使用明细",
    )
    breaksNaturalBomb: bool = Field(
        default=False,
        description="是否拆了天然炸弹结构（供托管评分）",
    )
    breaksRocket: bool = Field(
        default=False,
        description="是否拆了王炸结构（供托管评分）",
    )
    breaksStraight: bool = Field(
        default=False,
        description="是否拆了顺子结构（供托管评分）",
    )
    breaksAirplane: bool = Field(
        default=False,
        description="是否拆了飞机结构（供托管评分）",
    )


class DoudizhuPlayCardsPayload(BaseModel):
    """斗地主正式出牌归一载荷。"""

    model_config = CAMEL_MODEL_CONFIG

    cardInstanceIds: List[str] = Field(min_length=1)
    normalizedCombo: DoudizhuComboInfo
    comboSignature: str = Field(min_length=1)
    lastPlaySignature: str = Field(min_length=1)


class DoudizhuPlayerSettlement(BaseModel):
    """单名玩家结算明细。"""

    model_config = CAMEL_MODEL_CONFIG

    playerId: str = Field(min_length=1, description="玩家 ID")
    role: str = Field(min_length=1, description="角色：landlord / farmer")
    scoreDelta: int = Field(description="理论积分变动")


class DoudizhuSettlementResult(BaseModel):
    """斗地主对局理论结算结果。"""

    model_config = CAMEL_MODEL_CONFIG

    rulesVersion: int = Field(description="本局规则版本：1 为旧全桌，2 为经典叫分成对")
    bidScore: Optional[int] = Field(default=None, description="最终叫分；旧叫抢规则为空")
    landlordPlayerId: str = Field(min_length=1, description="地主玩家 ID")
    winnerRole: str = Field(min_length=1, description="胜方角色：landlord / farmer")
    baseScore: int = Field(description="底分")
    globalMultiplier: int = Field(description="本局规则对应的牌局倍率；新版仅含公共事件")
    springType: Optional[str] = Field(default=None, description="春天类型")
    multiplierDetails: Dict[str, Any] = Field(
        default_factory=dict,
        description="倍数明细",
    )
    playerSettlements: List[DoudizhuPlayerSettlement] = Field(
        default_factory=list,
        description="各玩家结算",
    )
