"""游戏规则定义种子查询接口测试。"""

from fastapi.testclient import TestClient

from app.main import app

RULE_DEFINITION_PATH = "/api/game-hub/games/{game_code}/rule-definition"


def _schema_field_map(schema_fields):
    """
    将 roomConfigSchema 字段列表转为 key -> field 映射。

    :param schema_fields: 字段定义列表。
    :return: 映射字典。
    """
    return {item["key"]: item for item in schema_fields}


def test_get_uno_rule_definition_returns_seed_fields() -> None:
    """已注册 UNO 规则种子时应返回规定字段且不含展示信息。"""
    with TestClient(app) as client:
        response = client.get(RULE_DEFINITION_PATH.format(game_code="uno"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["message"] == "success"
    data = payload["data"]
    assert data["gameCode"] == "uno"
    assert data["ruleVersion"] == "1.0.0"
    assert data["runtimeType"] == "strategy-turn-multiplayer"
    assert data["gameRuleInfo"]["singleDeckCardCount"] == 108
    assert "cardsPerDeckSet" not in data["gameRuleInfo"]
    assert data["gameRuleInfo"]["cardBackImage"] == "games/uno/cards/card_back.png"
    assert data["cardDefinitions"][0]["image"].startswith("games/uno/cards/")
    assert data["roomRule"]["minPlayers"] == 2
    assert data["roomRule"]["maxPlayers"] == 10
    assert data["roomRule"]["allowAi"] is True
    assert data["roomRule"]["defaultExpireSeconds"] == 86400
    assert len(data["cardDefinitions"]) > 0
    schema_map = _schema_field_map(data["roomConfigSchema"])
    assert schema_map["initialHandCount"]["defaultValue"] == 7
    assert schema_map["allowDrawStacking"]["defaultValue"] is True
    assert schema_map["finishMode"]["defaultValue"] == "UNTIL_REAL_PLAYER_COUNT"
    assert schema_map["finishMode"]["type"] == "enum"
    assert data["roomRule"]["maxAiCount"] == 9
    deck_total = sum(item["countPerDeckSet"] for item in data["cardDefinitions"])
    assert deck_total == 108
    assert data["cardDefinitions"][0]["cardType"] == "NUMBER"
    assert len(data["extensionConfig"]["initialDeckSetRules"]) >= 1
    assert "displayName" not in data
    assert "logo" not in data
    assert "route" not in data
    assert "sortOrder" not in data
    assert "name" not in data
    assert "icon" not in data


def test_get_rule_definition_not_found_returns_biz_error() -> None:
    """未注册规则种子的游戏应返回业务错误，而非空对象。"""
    with TestClient(app) as client:
        response = client.get(RULE_DEFINITION_PATH.format(game_code="minesweeper"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 30004
    assert payload["message"] == "游戏规则定义不存在"
    assert payload.get("data") is None
