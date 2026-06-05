"""五子棋在线游戏规则种子。"""

from app.modules.game_seed.schemas import (
    GameRuleInfo,
    OnlineGameRuleSeed,
    RoomConfigFieldDefinition,
    RoomRule,
)

GOMOKU_ONLINE_GAME_RULE_SEED = OnlineGameRuleSeed(
    gameCode="gomoku",
    ruleVersion="1.0.0",
    runtimeType="strategy-turn-multiplayer",
    gameRuleInfo=GameRuleInfo(
        description="在线双人五子棋",
        ruleDescription="黑白双方轮流落子，先连成五子者获胜。",
        cardBackImage="",
        singleDeckCardCount=0,
    ),
    cardDefinitions=[],
    roomRule=RoomRule(
        minPlayers=2,
        maxPlayers=2,
        allowAi=True,
        minAiCount=0,
        maxAiCount=1,
        defaultExpireSeconds=86400,
    ),
    roomConfigSchema=[
        RoomConfigFieldDefinition(
            key="turnTimeoutSeconds",
            type="number",
            label="回合时间",
            defaultValue=30,
            min=10,
            max=120,
        ),
        RoomConfigFieldDefinition(
            key="enableUndo",
            type="boolean",
            label="允许悔棋",
            defaultValue=True,
        ),
        RoomConfigFieldDefinition(
            key="undoRequestExpireSeconds",
            type="number",
            label="悔棋请求有效时间",
            defaultValue=30,
            min=10,
            max=120,
        ),
    ],
    extensionConfig={
        "rule": {
            "name": "gomoku",
            "config": {
                "boardSize": 15,
                "winLength": 5,
            },
        },
    },
)
