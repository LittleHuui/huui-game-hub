"""UNO 在线游戏规则种子。"""

from typing import Dict, List, Tuple

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
_UNO_COLOR_LABELS: Dict[str, str] = {
    "RED": "红色",
    "YELLOW": "黄色",
    "BLUE": "蓝色",
    "GREEN": "绿色",
}
_UNO_ACTION_CARD_SPECS: Tuple[Tuple[str, str, str, List[str]], ...] = (
    ("DISABLE", "disable", "禁止", ["UNO", "DISABLE"]),
    ("REVERSE", "reverse", "反转", ["UNO", "REVERSE"]),
    ("DRAW_TWO", "draw_two", "+2", ["UNO", "DRAW_TWO"]),
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
        suit_label = _UNO_COLOR_LABELS[color]
        cards.append(
            CardDefinition(
                cardCode="{0}_0".format(color_prefix),
                category="NUMBER",
                rankCode="0",
                rankValue=0,
                suitCode=color,
                suitLabel=suit_label,
                displayLabel="0",
                countPerDeckSet=1,
                image="games/uno/cards/{0}_0.png".format(color_prefix),
                description="{0} 0".format(suit_label),
                tags=["UNO", "COLOR_CARD"],
                metadata={},
            )
        )
        for number_value in range(1, 10):
            cards.append(
                CardDefinition(
                    cardCode="{0}_{1}".format(color_prefix, number_value),
                    category="NUMBER",
                    rankCode=str(number_value),
                    rankValue=number_value,
                    suitCode=color,
                    suitLabel=suit_label,
                    displayLabel=str(number_value),
                    countPerDeckSet=2,
                    image="games/uno/cards/{0}_{1}.png".format(
                        color_prefix, number_value
                    ),
                    description="{0} {1}".format(suit_label, number_value),
                    tags=["UNO", "COLOR_CARD"],
                    metadata={},
                )
            )
        for rank_code, code_suffix, display_label, tags in _UNO_ACTION_CARD_SPECS:
            cards.append(
                CardDefinition(
                    cardCode="{0}_{1}".format(color_prefix, code_suffix),
                    category="ACTION",
                    rankCode=rank_code,
                    rankValue=None,
                    suitCode=color,
                    suitLabel=suit_label,
                    displayLabel=display_label,
                    countPerDeckSet=2,
                    image="games/uno/cards/{0}_{1}.png".format(
                        color_prefix, code_suffix
                    ),
                    description="{0} {1}".format(suit_label, display_label),
                    tags=tags,
                    metadata={"actionType": rank_code},
                )
            )
    cards.append(
        CardDefinition(
            cardCode="wild",
            category="WILD",
            rankCode="WILD",
            rankValue=None,
            suitCode=None,
            suitLabel=None,
            displayLabel="变色",
            countPerDeckSet=4,
            image="games/uno/cards/wild.png",
            description="万能换色牌",
            tags=["UNO", "WILD"],
            metadata={"actionType": "WILD"},
        )
    )
    cards.append(
        CardDefinition(
            cardCode="wild_draw4",
            category="WILD",
            rankCode="WILD_DRAW4",
            rankValue=None,
            suitCode=None,
            suitLabel=None,
            displayLabel="+4",
            countPerDeckSet=4,
            image="games/uno/cards/wild_draw4.png",
            description="万能 +4 牌",
            tags=["UNO", "WILD", "DRAW_FOUR"],
            metadata={"actionType": "WILD_DRAW4"},
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
                RoomConfigFieldOption(value="FIRST_FINISH", label="首位真人完成结束"),
                RoomConfigFieldOption(
                    value="UNTIL_REAL_PLAYER_COUNT",
                    label="未结束对局剩余真人玩家数达阈值时结束",
                ),
            ],
        ),
        RoomConfigFieldDefinition(
            key="remainingRealPlayerCountToEnd",
            type="number",
            label="未结束对局剩余真人玩家数",
            defaultValue=2,
            min=0,
            max=9,
            description="结束模式为 未结束对局剩余真人玩家数达阈值时结束 时生效",
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
