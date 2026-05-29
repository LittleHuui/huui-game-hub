"""UNO 在线游戏规则种子。"""

from typing import List, Tuple

from app.modules.game_seed.schemas import (
    CardDefinition,
    GameRuleInfo,
    InitialDeckSetRule,
    OnlineGameRuleSeed,
    RoomConfigFieldDefinition,
    RoomConfigFieldOption,
    RoomRule,
    UnoExtensionConfig,
)

_UNO_COLORS = ("RED", "YELLOW", "BLUE", "GREEN")
_UNO_ACTION_CARD_TYPES: Tuple[Tuple[str, str], ...] = (
    ("DISABLE", "disable"),
    ("REVERSE", "reverse"),
    ("DRAW_TWO", "draw_two"),
)

_UNO_INITIAL_DECK_SET_RULES = [
    InitialDeckSetRule(
        minPlayerCount=2,
        maxPlayerCount=4,
        deckSetCount=1,
    ),
    InitialDeckSetRule(
        minPlayerCount=5,
        maxPlayerCount=7,
        deckSetCount=2,
    ),
    InitialDeckSetRule(
        minPlayerCount=8,
        maxPlayerCount=10,
        deckSetCount=3,
    ),
]


def _build_uno_card_definitions() -> List[CardDefinition]:
    """
    构建 UNO 标准 108 张/套的牌型定义列表。

    :return: 牌型定义列表。
    """
    cards = []
    for color in _UNO_COLORS:
        color_prefix = color.lower()
        cards.append(
            CardDefinition(
                cardCode="{0}_0".format(color_prefix),
                color=color,
                cardType="NUMBER",
                numberValue=0,
                countPerDeckSet=1,
                image="games/uno/cards/{0}_0.png".format(color_prefix),
                description="{0} 0".format(color),
            )
        )
        for number_value in range(1, 10):
            cards.append(
                CardDefinition(
                    cardCode="{0}_{1}".format(color_prefix, number_value),
                    color=color,
                    cardType="NUMBER",
                    numberValue=number_value,
                    countPerDeckSet=2,
                    image="games/uno/cards/{0}_{1}.png".format(
                        color_prefix, number_value
                    ),
                    description="{0} {1}".format(color, number_value),
                )
            )
        for card_type, code_suffix in _UNO_ACTION_CARD_TYPES:
            cards.append(
                CardDefinition(
                    cardCode="{0}_{1}".format(color_prefix, code_suffix),
                    color=color,
                    cardType=card_type,
                    numberValue=None,
                    countPerDeckSet=2,
                    image="games/uno/cards/{0}_{1}.png".format(
                        color_prefix, code_suffix
                    ),
                    description="{0} {1}".format(color, card_type),
                )
            )
    cards.append(
        CardDefinition(
            cardCode="wild",
            color=None,
            cardType="WILD",
            numberValue=None,
            countPerDeckSet=4,
            image="games/uno/cards/wild.png",
            description="万能换色牌",
        )
    )
    cards.append(
        CardDefinition(
            cardCode="wild_draw4",
            color=None,
            cardType="WILD_DRAW4",
            numberValue=None,
            countPerDeckSet=4,
            image="games/uno/cards/wild_draw4.png",
            description="万能 +4 牌",
        )
    )
    return cards


UNO_ONLINE_GAME_RULE_SEED = OnlineGameRuleSeed(
    gameCode="uno",
    ruleVersion="1.0.0",
    runtimeType="strategy-turn-multiplayer",
    gameRuleInfo=GameRuleInfo(
        description="UNO 经典规则多人对战",
        ruleDescription="同色、同数字或同功能可出牌；万能牌可换色；+2/+4 叠加受房间配置控制。",
        cardBackImage="games/uno/cards/card_back.png",
        singleDeckCardCount=108,
    ),
    cardDefinitions=_build_uno_card_definitions(),
    roomRule=RoomRule(
        minPlayers=2,
        maxPlayers=10,
        allowAi=True,
        minAiCount=0,
        maxAiCount=9,
        defaultExpireSeconds=86400,
    ),
    roomConfigSchema=[
        RoomConfigFieldDefinition(
            key="allowDrawStacking",
            type="boolean",
            label="允许 +2/+4 叠加",
            defaultValue=True,
            description="开启后可在待抽惩罚下继续出 +2/+4",
        ),
        RoomConfigFieldDefinition(
            key="allowDrawAndPlay",
            type="boolean",
            label="允许抽牌后立即出牌",
            defaultValue=True,
        ),
        RoomConfigFieldDefinition(
            key="finishMode",
            type="enum",
            label="结束模式",
            defaultValue="UNTIL_REAL_PLAYER_COUNT",
            options=[
                RoomConfigFieldOption(value="FIRST_FINISH", label="首位完成结束"),
                RoomConfigFieldOption(
                    value="UNTIL_REAL_PLAYER_COUNT",
                    label="剩余真人玩家数达阈值时结束",
                ),
            ],
        ),
        RoomConfigFieldDefinition(
            key="remainingRealPlayerCountToEnd",
            type="number",
            label="结束所需剩余玩家数",
            defaultValue=2,
            min=1,
            max=10,
            description="finishMode 为 UNTIL_REAL_PLAYER_COUNT 时生效",
            visibleWhen={"field": "finishMode", "equals": "UNTIL_REAL_PLAYER_COUNT"},
        ),
        RoomConfigFieldDefinition(
            key="initialHandCount",
            type="number",
            label="初始手牌数",
            defaultValue=7,
            min=1,
            max=20,
        ),
        RoomConfigFieldDefinition(
            key="appendDeckSetWhenDrawPileEmpty",
            type="boolean",
            label="抽牌堆耗尽时补牌",
            defaultValue=True,
        ),
        RoomConfigFieldDefinition(
            key="appendDeckSetCount",
            type="number",
            label="每次补入牌组套数",
            defaultValue=1,
            min=0,
            max=5,
            visibleWhen={"field": "appendDeckSetWhenDrawPileEmpty", "equals": True},
        ),
    ],
    extensionConfig=UnoExtensionConfig(
        initialDeckSetRules=_UNO_INITIAL_DECK_SET_RULES
    ).model_dump(),
)
