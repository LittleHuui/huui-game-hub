# UNO 后端链路手动自检（curl）

前置：

1. 后端已启动（默认 `http://127.0.0.1:8000`）。
2. Redis 可用（与 `app/core/config.py` 中 `REDIS_*` 一致，Docker Compose 默认密码 `123456`）。
3. 以下变量按环境替换：

```bash
BASE=http://127.0.0.1:8000/api/game-hub
```

> **说明**：`waiting` 房间中房主可调用 `POST /rooms/{roomId}/ai` 添加 AI；是否允许由 `rule-definition.roomRule.allowAi` 控制，数量受 `maxAiCount` 与 `maxPlayers` 限制。AI 不写入 `player:{playerId}:room` 索引，对局内由平台托管动作链路代管。

## 0. 创建测试用户（房主）

```bash
OWNER_JSON=$(curl -s -X POST "$BASE/users/" -H "Content-Type: application/json" -d "{\"clientId\":\"uno_owner_cli\",\"username\":\"uno_owner\",\"nickname\":\"UNO房主\"}")
OWNER_ID=$(echo "$OWNER_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['data']['serverId'])")
echo "OWNER_ID=$OWNER_ID"
```

成功响应须满足：`code == 0` 且 `success == true`。

## 1. 创建第二名真人玩家

```bash
GUEST_JSON=$(curl -s -X POST "$BASE/users/" -H "Content-Type: application/json" -d "{\"clientId\":\"uno_guest_cli\",\"username\":\"uno_guest\",\"nickname\":\"UNO玩家2\"}")
GUEST_ID=$(echo "$GUEST_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['data']['serverId'])")
echo "GUEST_ID=$GUEST_ID"
```

## 2. 获取 UNO rule-definition

```bash
curl -s "$BASE/games/uno/rule-definition" | python -m json.tool
```

检查要点：

- `data.gameCode` 为 `uno`
- `data.roomRule.minPlayers` 为 `2`
- `data.roomConfigSchema` 为字段定义数组，每项含 `key` / `type` / `label` / `defaultValue`
- `allowDrawStacking` 字段 `defaultValue` 为 `true`
- `finishMode` 字段 `defaultValue` 为 `UNTIL_REAL_PLAYER_COUNT`
- `remainingRealPlayerCountToEnd` 含 `visibleWhen`（依赖 `finishMode`）
- `data.cardDefinitions[0].cardType` 为大写枚举（如 `NUMBER`、`DISABLE`）
- `data.cardDefinitions[].color` 为大写枚举（如 `RED`）或 `null`
- 单套牌张数：`sum(countPerDeckSet)` 为 `108`

## 3. 创建 UNO 房间

房主通过请求头 `X-Game-Hub-User-Id` 标识：

```bash
ROOM_JSON=$(curl -s -X POST "$BASE/rooms" \
  -H "Content-Type: application/json" \
  -H "X-Game-Hub-User-Id: $OWNER_ID" \
  -d "{\"gameCode\":\"uno\",\"mode\":\"classic\"}")
ROOM_ID=$(echo "$ROOM_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['data']['roomId'])")
echo "ROOM_ID=$ROOM_ID"
```

## 4. 第二名真人加入房间

```bash
curl -s -X POST "$BASE/rooms/$ROOM_ID/join" \
  -H "X-Game-Hub-User-Id: $GUEST_ID" | python -m json.tool
```

确认 `data.memberCount >= 2`。

## 5. 房主开始游戏

```bash
START_JSON=$(curl -s -X POST "$BASE/rooms/$ROOM_ID/start" \
  -H "X-Game-Hub-User-Id: $OWNER_ID")
echo "$START_JSON" | python -m json.tool
```

记录：

- `data.roomId` 与 `ROOM_ID` 一致
- `data.currentPlayerId`
- `data.version`
- `data.publicState`（含 `currentColor`、`discardTopCard`、`players`、`drawPileCount` 等）
- `data.privateState.handCards`
- `data.legalActions`（当前行动玩家至少包含 `DRAW_CARD` 或可出的 `PLAY_CARD`）
- `data.events` 为空数组（`gameStarted` 不进入对局动画事件）
- 开局后当前玩家可立即提交 `legalActions[0].actionId`

## 6. 两名玩家分别获取 GameView

将 `CURRENT_ID` 替换为第 5 步的 `currentPlayerId`：

```bash
CURRENT_ID=<currentPlayerId>
curl -s "$BASE/rooms/$ROOM_ID/view" \
  -H "X-Game-Hub-User-Id: $CURRENT_ID" | python -m json.tool
```

非当前行动玩家查询（将 `OTHER_ID` 换为另一名真人 ID）：

```bash
OTHER_ID=<另一名玩家ID>
curl -s "$BASE/rooms/$ROOM_ID/view" \
  -H "X-Game-Hub-User-Id: $OTHER_ID" | python -m json.tool
```

确认：

- `roomId` 与 `ROOM_ID` 一致
- `viewerPlayerId` 与请求头用户一致
- `publicState.players[]` 仅有 `handCount`，无 `handCards`
- `privateState.handCards` 仅对应当前视角玩家
- 非当前行动玩家 `legalActions` 为空数组

## 7. 从 legalActions 取 actionId

```bash
ACTION_ID=$(echo "$START_JSON" | python -c "import sys,json; d=json.load(sys.stdin)['data']; acts=d.get('legalActions') or []; print(acts[0]['actionId'] if acts else '')")
echo "ACTION_ID=$ACTION_ID"
```

也可从第 6 步 view 响应中读取 `legalActions[0].actionId`。

## 8. 当前玩家提交 actionId

仅提交 `actionId`（及可选 `clientSeq`），**无需** `actionType` 与 `payload`：

```bash
curl -s -X POST "$BASE/rooms/$ROOM_ID/actions" \
  -H "Content-Type: application/json" \
  -H "X-Game-Hub-User-Id: $CURRENT_ID" \
  -d "{\"actionId\":\"$ACTION_ID\",\"baseVersion\":$(echo "$START_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['data']['version'])"),\"clientSeq\":1}" \
  | python -m json.tool
```

确认返回 `GameView` 含 `roomId`、`version`、`viewerPlayerId`、`publicState`、`privateState`、`legalActions`、`events`（本帧规则事件，非 `gameStarted`）。

## 9. 校验私有态不泄露（可选）

分别以 `OWNER_ID` 与 `GUEST_ID` 查询 view，比较 `privateState.handCards` 的 `cardInstanceId` 集合应互不相交。

## 10. finishMode 手动验证（可选）

### FIRST_FINISH

创建房间时 `roomConfig.finishMode` 设为 `FIRST_FINISH`，两名真人开局后，让其中一人出完所有手牌。预期：

- 运行时阶段（runtime `phase`）可进入 `finished`，或 `GameView.isGameOver` 为 `true`
- `room.status` 只允许 `waiting` / `playing`
- 对局结束后 `room.status` 从 `playing` 回到 `waiting`

### UNTIL_REAL_PLAYER_COUNT

默认 `finishMode=UNTIL_REAL_PLAYER_COUNT` 且 `remainingRealPlayerCountToEnd=2`。三人局中一名真人出完手牌后，若仍有 2 名真人处于 `PLAYING`，对局继续；当仅剩 1 名真人未结束时，对局结束。

## 11. allowDrawStacking 手动验证（可选）

### allowDrawStacking=false

创建房间时 `roomConfig.allowDrawStacking` 设为 `false`。在对方出 +2 形成 `pendingDraw` 后，当前玩家 `legalActions` 中不应出现可出的 `PLAY_CARD`（+2/+4）；只能 `DRAW_CARD` 承担惩罚。

### allowDrawStacking=true

默认 `true`：+2 后可继续出 +2 或 +4；若顶链为 +4，则只能再接 +4。

## 自动化 pytest

Redis 可用时执行：

```bash
cd game-hub-end
python -m pytest tests/test_uno_room_flow.py tests/test_game_rule_definition.py tests/test_uno_turn_finish_rules.py tests/test_uno_draw_stacking.py -v
```

Redis 不可用时房间链路用例自动 `SKIPPED`，不视为业务失败。
