"""排行集成测试用最小种子（仅含排行榜解析所需游戏定义，非完整业务 GAME_SEED_CONFIG）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

IMPORT_GAME_SEED_PATH = "/api/game-hub/admin/config/import-game-seed"

RANKING_TEST_SEED_BODY: dict = {
    "props": [],
    "games": [
        {
            "gameCode": "minesweeper",
            "gameName": "雷区突围",
            "supportOnline": False,
            "enabled": True,
            "sortNo": 1,
            "config": {
                "ranking": {
                    "modes": {
                        "single": {
                            "primaryMetric": "durationMs",
                            "orderDirection": "asc",
                            "tieBreakers": [
                                {"metric": "score", "orderDirection": "desc"},
                                {"metric": "createdAt", "orderDirection": "asc"},
                            ],
                        }
                    }
                }
            },
            "difficulties": [],
            "clientConfigs": [],
            "propRules": [],
        },
        {
            "gameCode": "match3",
            "gameName": "幻彩碰撞",
            "supportOnline": False,
            "enabled": True,
            "sortNo": 2,
            "config": {
                "ranking": {
                    "enabled": True,
                    "candidateLimit": 1000,
                    "modes": {
                        "timed": {
                            "primaryMetric": "score",
                            "orderDirection": "desc",
                            "tieBreakers": [
                                {"metric": "comboMax", "orderDirection": "desc"},
                                {"metric": "durationMs", "orderDirection": "asc"},
                                {"metric": "createdAt", "orderDirection": "asc"},
                            ],
                        },
                        "endless": {
                            "primaryMetric": "score",
                            "orderDirection": "desc",
                            "tieBreakers": [
                                {"metric": "comboMax", "orderDirection": "desc"},
                                {"metric": "moves", "orderDirection": "desc"},
                                {"metric": "createdAt", "orderDirection": "asc"},
                            ],
                        },
                    },
                }
            },
            "difficulties": [],
            "clientConfigs": [],
            "propRules": [],
        },
    ],
}


def import_ranking_test_seed(client: TestClient) -> None:
    """
    通过管理接口写入排行测试所需的最小游戏定义。

    :param client: FastAPI TestClient。
    """
    resp = client.post(IMPORT_GAME_SEED_PATH, json=RANKING_TEST_SEED_BODY)
    assert resp.status_code == 200, resp.text
