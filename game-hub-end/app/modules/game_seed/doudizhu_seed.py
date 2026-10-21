"""斗地主在线游戏规则种子。"""

from typing import List

from app.modules.game_impls.doudizhu.doudizhu_constants import (
    DOUDIZHU_JOKER_SPECS,
    DOUDIZHU_RANK_SPECS,
    DOUDIZHU_SINGLE_DECK_CARD_COUNT,
    DOUDIZHU_SUIT_DISPLAY_COLORS,
    DOUDIZHU_SUIT_LABELS,
    DOUDIZHU_SUITS,
)
from app.modules.game_seed.schemas import (
    CardDefinition,
    GameRuleInfo,
    OnlineGameRuleSeed,
    RoomConfigFieldDefinition,
    RoomRule,
)

_DOUDIZHU_FIXED_RULE_CONFIG = {
    "playerCount": 3,
    "deckSetCount": 1,
    "handCount": 17,
    "bottomCardCount": 3,
    "turnTimeoutSeconds": 30,
    "biddingTimeoutSeconds": 20,
    "doublingTimeoutSeconds": 15,
    "baseScore": 1,
    "showCardsMultiplier": 2,
    "doubleMultiplier": 2,
    "bombMultiplier": 2,
    "rocketMultiplier": 2,
    "springMultiplier": 2,
    "enableShowCards": True,
    "enableDouble": True,
    "enableSpring": True,
    "allowFourWithTwoSingles": True,
    "allowFourWithTwoPairs": True,
    "straightMinLength": 5,
    "pairStraightMinLength": 3,
    "airplaneMinLength": 2,
    "animationDurationsMs": {
        "dealing": 1000,
        "laiziReveal": 1200,
        "landlordConfirm": 1500,
        "bottomCardsReveal": 1200,
        "settlement": 2200,
    },
}


def _build_doudizhu_card_definitions() -> List[CardDefinition]:
    """
    构建斗地主标准 54 张/套的牌型定义列表。

    :return: 牌型定义列表。
    """
    cards = []
    for suit_code in DOUDIZHU_SUITS:
        suit_prefix = suit_code.lower()
        suit_label = DOUDIZHU_SUIT_LABELS[suit_code]
        display_color = DOUDIZHU_SUIT_DISPLAY_COLORS[suit_code]
        color_tag = display_color
        for rank_code, display_label, rank_value in DOUDIZHU_RANK_SPECS:
            rank_suffix = rank_code.lower()
            card_code = "{0}_{1}".format(suit_prefix, rank_suffix)
            cards.append(
                CardDefinition(
                    cardCode=card_code,
                    category="STANDARD",
                    rankCode=rank_code,
                    rankValue=rank_value,
                    suitCode=suit_code,
                    suitLabel=suit_label,
                    displayLabel=display_label,
                    countPerDeckSet=1,
                    image="games/doudizhu/cards/{0}.png".format(card_code),
                    description="{0} {1}".format(suit_label, display_label),
                    tags=["POKER", color_tag],
                    metadata={"displayColor": display_color},
                )
            )
    for (
        card_code,
        rank_code,
        display_label,
        rank_value,
        display_color,
    ) in DOUDIZHU_JOKER_SPECS:
        cards.append(
            CardDefinition(
                cardCode=card_code,
                category="JOKER",
                rankCode=rank_code,
                rankValue=rank_value,
                suitCode=None,
                suitLabel=None,
                displayLabel=display_label,
                countPerDeckSet=1,
                image="games/doudizhu/cards/{0}.png".format(card_code),
                description=display_label,
                tags=["POKER", display_color],
                metadata={"displayColor": display_color},
            )
        )
    return cards


DOUDIZHU_ONLINE_GAME_RULE_SEED = OnlineGameRuleSeed(
    gameCode="doudizhu",
    ruleVersion="2.0.0",
    runtimeType="strategy-turn-multiplayer",
    gameRuleInfo=GameRuleInfo(
        description="经典三人斗地主",
        ruleDescription="按座次叫 1、2、3 分或不叫，最高叫分者成为地主；全员不叫则重新发牌。地主取得底牌并完成加倍阶段后先出牌，先出完手牌者所在阵营获胜。",
        cardBackImage="games/doudizhu/cards/card_back.png",
        singleDeckCardCount=DOUDIZHU_SINGLE_DECK_CARD_COUNT,
    ),
    cardDefinitions=_build_doudizhu_card_definitions(),
    roomRule=RoomRule(
        minPlayers=3,
        maxPlayers=3,
        allowAi=True,
        minAiCount=0,
        maxAiCount=2,
        defaultExpireSeconds=86400,
    ),
    roomConfigSchema=[
        RoomConfigFieldDefinition(
            key="enableLaizi",
            type="boolean",
            label="癞子玩法",
            defaultValue=False,
            description="开局先独立随机确定癞子点数，再洗牌发牌",
        ),
        RoomConfigFieldDefinition(
            key="allowSingleAttachment",
            type="boolean",
            label="允许带单牌",
            defaultValue=True,
            description="控制三带一、飞机带单是否允许",
        ),
    ],
    extensionConfig={
        "rule": {
            "name": "doudizhu",
            "config": _DOUDIZHU_FIXED_RULE_CONFIG,
        },
    },
)
