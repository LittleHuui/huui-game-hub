# Game Hub API 文档

HTTP API 前缀为 `/api/game-hub`。JSON 字段使用 camelCase；成功响应的 `code` 为 `0`，业务失败由响应中的 `code` 和 `message` 表示。

## 认证

`POST /auth/login` 接收：

```json
{
  "username": "alice",
  "deviceId": "device-1"
}
```

登录响应中的 `data` 包含用户上下文、`accessToken` 和 `expiresAt`。受保护 HTTP 请求使用：

```http
Authorization: Bearer <accessToken>
```

`POST /auth/realtime-ticket` 没有请求体，要求 HTTP Bearer 认证。响应 `data` 为：

```json
{
  "ticket": "rt_...",
  "expiresAt": 1710000000000
}
```

Ticket 存储在 Redis，短时有效且只能消费一次。房间及实时操作从认证上下文取得身份，不信任客户端身份声明。

当前认证边界尚未覆盖全部平台接口：管理种子导入、系统配置写入与云同步未接入认证，云同步仍采用请求中的 `userId`；钱包等部分用户资源接口虽要求登录，但未校验目标用户与登录用户一致。WebSocket 尚未保留原 Access Token 的到期边界，也未在连接期间主动关闭或重认证，连接合同见 [WebSocket 与认证接入](websocket-auth-integration.md)。

## 平台与房间

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | 存活检查别名，返回与 `/health/live` 相同的结果。 |
| `GET` | `/health/live` | 进程存活检查。 |
| `GET` | `/health/ready` | 依赖就绪检查。 |
| `POST` | `/boot/context` | 加载用户上下文、平台配置、游戏列表与服务时间。 |
| `POST` | `/sync/cloud-save` | 按事件 SAVEPOINT 执行同步，返回批次计数与完整快照。 |
| `GET` | `/online/users` | 查询在线用户展示信息。 |
| `POST` | `/online/status` | 写入认证用户的在线状态。 |
| `GET` | `/rooms` | 按游戏查询房间。 |
| `POST` | `/rooms` | 创建房间。 |
| `GET` | `/rooms/my-active` | 查询当前认证用户的活跃房间。 |
| `GET` | `/rooms/{roomId}` | 查询房间详情。 |
| `POST` | `/rooms/{roomId}/join` | 加入等待中的房间。 |
| `POST` | `/rooms/{roomId}/rejoin` | 恢复 shell 席位。 |
| `POST` | `/rooms/{roomId}/leave` | 离开房间。 |
| `POST` | `/rooms/{roomId}/start` | 开始对局。 |
| `GET` | `/rooms/{roomId}/view` | 获取权威 GameView。 |
| `POST` | `/rooms/{roomId}/actions` | 提交对局动作。 |
| `POST` | `/rooms/{roomId}/action-preview` | 只读预览 COMPOSED 动作。 |
| `POST` | `/rooms/{roomId}/action-suggestions` | 查询提示候选。 |

房间、在线状态和对局接口使用 HTTP Bearer 认证。

`POST /rooms/{roomId}/action-suggestions` 的 Path 参数 `roomId` 为房间 ID，Body 包含必填 `baseVersion`（整数）、`actionType`（字符串），以及可选 `cursor`（字符串或 `null`）和 `limit`（整数）。响应 `data` 包含 `items`（提示数组）、`nextCursor`（字符串或 `null`）及 `hasLegalAction`（布尔值或 `null`，默认 `null`）。该字段只描述请求的 `actionType`：`true` 表示存在合法提交，`false` 只表示服务端已完整核验不存在合法提交；`null` 表示未确认，包括搜索数量或耗时预算耗尽。空 `items` 本身不表示无法出牌。例如 `{"items":[],"nextCursor":null,"hasLegalAction":false}` 才是已确认无合法提示动作。斗地主查询 `PLAY_CARDS` 得到这个结果，且同一版本存在合法 `PASS` Offer 时，允许客户端复用普通动作提交执行不出；查询本身不会提交动作。

`GET /rooms/my-active` 无请求体、无 `gameCode` 筛选，按当前认证用户查询跨游戏的活跃房间。响应 `data.room` 为房间详情对象（含 `roomId`、`gameCode`、`status`、`members`、`roomVersion` 等现有字段），无有效占用时为 `null`。有效占用要求房间处于 `waiting` 或 `playing`，且当前用户为非 AI、非 shell 成员；终局展示和待结算仍属于 `playing`，不会提前释放占用。

`GET /rooms/{roomId}` 的 `status`、`ownerPlayerId`、`members` 与 `roomVersion` 来自同一次原子读取，不混用 Finalize 前后的事实和版本。终局展示期间仍返回 `playing`；开始游戏、添加 AI 和移除成员等等待房间操作须以服务端返回的 `waiting` 为准。

该查询与创建、加入、恢复席位共用成员事实核对。房间已不存在、成员已移除、已转为 shell 或房间状态已失效时，仅清理仍属于该房间的旧索引；有效的其他房间仍返回 `90006`（玩家已在其他房间中）。无法可靠读取的损坏事实返回明确错误，不作为“无房间”放行。创建、加入与恢复成功时，成员和活跃占用在同一原子提交中写入。

大厅显示跨游戏的当前房间，可按其实际 `gameCode` 返回，或由用户确认后调用现有 `POST /rooms/{roomId}/leave` 退出。未知游戏不能进入时仍可明确发起通用退出；不会自动退出或改变该房间既有托管、解散规则。历史多重归属及缺失游戏模块的处理边界见 [房间成员归属](architecture.md#房间成员归属)。

## 健康检查

`GET /health/live` 不读取外部依赖，成功时返回：

```json
{
  "code": 0,
  "success": true,
  "data": {
    "status": "ok",
    "serverTime": 1710000000000,
    "components": {}
  }
}
```

`GET /health/ready` 检查 `database`、`redis`、`roomBackgroundCoordinator` 和 `gameModuleRegistryFrozen`。所有组件为 `true` 时返回 HTTP 200；存在未就绪组件时返回 HTTP 503：

```json
{
  "code": 10003,
  "success": false,
  "message": "服务依赖未就绪",
  "detail": {
    "status": "unready",
    "serverTime": 1710000000000,
    "components": {
      "database": true,
      "redis": false,
      "roomBackgroundCoordinator": true,
      "gameModuleRegistryFrozen": true
    }
  }
}
```

前端 `readinessCheck` 只请求 `/health/ready`，接受 JSON 响应并在 4 秒后中止请求。远端模式和自动模式依据该结果决定远端可用性。

后端数据库与 Redis 探测并行，各限 3 秒。数据库探测在线程自己的会话中执行；超时后保留同一在途探测，不为后续请求重复创建线程。启动 await 总期限为 30 秒，Redis 连接/I/O 分别限 3/5 秒。同步驱动永久阻塞时，asyncio 无法强制结束其线程。

## 云存档同步

`POST /sync/cloud-save` 的请求字段均保持现有合同：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| userId / deviceId | string | 是 | 服务端用户与设备 ID |
| clientSnapshotVersion | integer / null | 否 | 客户端快照版本 |
| clientTime | integer | 是 | Unix 毫秒 |
| pendingEvents | array | 否 | 默认空；每项有 clientId、eventType、createdAt、updatedAt、payload |

事件 clientId/eventType 为 string，createdAt/updatedAt 为整数毫秒，payload 为对象，五项均必填。批次内 clientId 不得重复；本地 ownerUserId 不属于 API 载荷。

响应 data 包含 serverTime、cloudSnapshotVersion、syncResult、user、systemSetting、wallet、inventory、userGameSettings、walletLedgers、purchaseRecords、propUsageRecords、matchRecords、scoreRecords。syncResult 的 receivedCount、successCount、duplicateCount、failCount 均为整数；没有逐事件 ACK 字段。walletLedgers 是该用户的完整有效流水，不受钱包展示 API 的分页限制。

每条事件失败只回滚自己的事实、派生重建与幂等写入；后续事件可继续。快照构建、审计或请求最终失败时，外层事务整体回滚。客户端仅在 failCount=0 且其余计数与发送集合吻合时确认完整发送集合；部分失败保留整批幂等重试。

## GameView 与动作提交

`RuntimeSnapshot` 是对局事实源，`GameView` 是按查看者投影的结果。客户端消费 `actionOffers`，不读取 `GameView.legalActions`。

`GameView.version` 与动作 `baseVersion` 属于对局版本流，在同一 `roomId` 存续期间跨局单调递增；终局回到等待页不归零，下一次开局继续递增。房间详情的 `roomVersion` 是独立的元数据版本，不能由对局版本替代。HTTP、动作响应与 WebSocket GameView 使用同一版本语义。

斗地主癞子玩法的初始阶段为 `laizi_reveal`：`publicState.gameState` 已公开 `enableLaizi`、`laiziRankCode`、`laiziRankValue` 和 `laiziCardCodes`，此时玩家手牌与底牌尚未生成。自动推进到 `dealing` 后，`privateState.handCards` 中对应点数牌的 `isLaizi` 为 `true`；底牌在地主确认前仍通过 `bottomCards: []` 隐藏。癞子点数独立于底牌确定，普通玩法直接从 `dealing` 开始。

斗地主 `GET /rooms/{roomId}/view` 的倍率与理论结算字段如下，开局、动作响应及实时 GameView 使用相同投影：

| JSON 路径（相对 `publicState`） | 类型 | 说明与示例 |
| --- | --- | --- |
| `gameState.rulesVersion` | integer，必填 | `1` 为旧叫抢与全桌计分，`2` 为经典叫分与成对计分；新局为 `2`。历史缺版本字段的快照只归入 `1`，未知版本拒绝。 |
| `gameState.baseScore` | integer / null，必填 | 本局底分。版本 `2` 未定地主前为 `null`，确认后为本局房间基础分乘最终叫分，例如 `10 × 3 = 30`；版本 `1` 保留原基础分。 |
| `gameState.bidScore` | integer / null，必填 | 版本 `2` 本轮当前最高叫分，初始 `0`，合法出价为 `1 / 2 / 3`；旧叫抢快照可能为 `null`，不能将其解释为叫分结果。 |
| `gameState.globalMultiplier` | integer，必填 | 版本 `2` 的公共倍率，初始 `1`，仅实际炸弹、王炸、春天 / 反春天累乘此值；叫分进入底分，明牌和加倍只影响对应个人因素。版本 `1` 保留原全桌倍率含义。 |
| `gameState.multiplierDetails` | array，必填 | 倍率来源，初始 `[]`；新明细包含 `scope`（`GLOBAL` / `PLAYER`）、`type`、`playerId`、`multiplier`、`eventType`，仅 `GLOBAL` 明细含 `globalMultiplierAfter`。历史明细可能未携带 `scope`，按本局旧规则解释。 |
| `players[].showCards` / `players[].isDoubled` | boolean，必填 | 玩家是否选择明牌 / 加倍，例如 `true`；用于行为标签，不返回个人倍率数字字段。版本 `2` 计分时由行为与本局固定系数派生个人因素。 |
| `gameState.lastActionEvent.payload.bidScore` | integer，可选 | 最近叫分动作的实际分值，配合 `playerId / actionType` 显示座位反馈；不叫及其他动作没有该参数。 |
| `gameState.settlement` | object / null，必填 | 未结算为 `null`；新生成结算含 `rulesVersion`、`bidScore`（新版最终叫分，旧版为 `null`）、`baseScore`、`globalMultiplier`、`landlordPlayerId`、`winnerRole`、`springType`、`multiplierDetails.entries`、`playerSettlements`。历史已生成对象原样保留。 |
| `gameState.settlement.playerSettlements[]` | object | 每项含 `playerId`、`role`、`scoreDelta`；版本 `2` 每名农民按 `baseScore × globalMultiplier × 地主个人因素 × 该农民个人因素` 计分，地主为两份的相反合计，例如 `+360 / -240 / -120`。 |

`CALL_LANDLORD` 在版本 `2` 中提供携带 `payload.bidScore` 的合法更高分值选项；`PASS_CALL` 表示不叫。每人至多一次，`3` 分立即定地主，一轮结束取最高分；全部不叫重新发牌。该版本不提供抢地主动作。版本 `1` 的在途局继续原叫抢与全桌结算，不中途切换玩法。历史已生成结算（包括 `PENDING`）保留原结果，实际钱包入账仍以 `terminalMetadata.settlementResult.playerSettlements[].actualDelta` 为准。

```json
{
  "baseVersion": 12,
  "requestId": "room-action-uuid",
  "submission": {
    "actionType": "PLAY_CARDS",
    "input": {
      "kind": "COMPOSED",
      "selection": {
        "cardInstanceIds": ["c1", "c2"]
      }
    }
  }
}
```

`requestId` 位于房间命令顶层。相同 `roomId + playerId + requestId` 且请求内容相同会幂等返回；相同键但请求内容不同会产生冲突。`baseVersion` 必须对应提交时的权威版本。

`ENUMERATED` 输入提交 `actionId`，`COMPOSED` 输入提交 `selection`。两种输入都由交互层解析为 `ResolvedGameAction` 后进入同一 Runtime 和 Lifecycle 执行链。Preview 和 Suggestions 不写入快照、不递增版本，也不替代提交时的合法性校验。

## WebSocket 实时通道

唯一实时地址为：

```text
/ws/game-hub/realtime?ticket=<ticket>
```

连接流程：登录取得 Access Token，使用 HTTP Bearer 调用 `/auth/realtime-ticket`，再将返回的单次 Ticket 放入 WebSocket 查询参数。每次连接、重连和重试都申请新 Ticket。缺失、无效或已消费 Ticket 以 close code `1008` 拒绝；握手时发现认证上下文过期以 `4003` 关闭。当前连接建立后尚未按原 Access Token 截止时间主动关闭或重认证，不能将握手检查解释为持续连接有效期保证。

Realtime 消息使用：

```json
{
  "type": "online.ping",
  "requestId": "uuid",
  "payload": {},
  "timestamp": 1710000000000
}
```

客户端收到 `gameViewUpdated` 后按版本顺序应用。出现版本缺口时，取消动画队列并通过 `GET /rooms/{roomId}/view` 获取权威快照。
