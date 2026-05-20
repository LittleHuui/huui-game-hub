# 架构说明

本文描述 **huui-game-hub** 当前稳定架构：平台层提供账号、资产、同步、排行榜；游戏层只实现玩法与 UI，通过配置与注册表接入。

---

## 1. 总体关系

```
┌─────────────────────────────────────────────────────────┐
│  平台层（game-hub / game-hub-end）                        │
│  用户 · 钱包 · 背包 · 商城 · 同步 · 排行榜 · 游戏配置      │
└───────────────────────────┬─────────────────────────────┘
                            │ gameCode + config + capabilities
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   minesweeper           match3            (your-game)
   games/minesweeper/    games/match3/
```

**原则**

- 平台不知道具体游戏规则；游戏不直接访问 HTTP / localStorage。
- 对外数据一律 **camelCase**；对局字段见 [api.md §1.9](api.md#19-对局记录业务字段match_record)。

---

## 2. 前端架构

### 2.1 目录职责

| 目录 | 职责 |
|------|------|
| `src/pages/` | 平台页：大厅、不可用页 |
| `src/games/{gameCode}/` | 单游戏：Page、Engine、Config、游戏专用组件 |
| `src/components/game/` | 跨游戏 UI：`GamePlayLayout`、`GameShopPanel` 等 |
| `src/services/` | 业务编排：开局、结算、同步、商城 |
| `src/repositories/` | 数据访问：local / remote / sync 屏蔽 |
| `src/stores/` | Pinia 响应式状态快照 |
| `src/composables/` | 跨组件 UI 逻辑（动画队列、主题等） |
| `src/constants/` | `GAME_REGISTRY`、`GAME_SEED_CONFIG` |
| `src/mappers/` | API DTO → 领域对象 |
| `src/api/` | HTTP 封装（`request.js`、`gameHubApi.js`） |

### 2.2 依赖方向

```
Page / games/*Page.vue
    → services（+ 可选 games/*Service.js）
        → repositories → api / localRepository
stores ← 仅由 services 写入，供 UI 读取
games/*Engine.js ← 纯算法，无 Vue / DOM / 网络
```

### 2.3 注册表与配置

| 来源 | 文件 | 用途 |
|------|------|------|
| 前端能力 | `constants/gameRegistry.js` | `modes`、`capabilities`（leaderboard/shop/inventory） |
| 离线种子 | `constants/gameSeedConfig.js`（`GAME_SEED_CONFIG`，**唯一业务种子源码**） |
| 种子 JSON | `npm run export:seed` → `dist/game-seed.json`（与上者一致，供导入 / curl） |
| 在线配置 | `gameConfigService` → `GET /games/{gameCode}/config` | 覆盖种子；失败回退种子 |

### 2.4 游戏生命周期

进入游戏页时调用 `gameLifecycleService.activateGame(gameCode, options)`：

1. `loadGameConfig` — 合并服务端/种子配置  
2. `loadGameShop` — 有 `shop` 能力时加载商城到 `shopStore`  
3. `refreshGameBag` — `includeInventory` 时刷新背包  
4. 排行榜侧栏由 `GameRankingPanel` 根据 `gameCode` / `mode` / `difficultyCode` props 自行加载并写入 `rankingStore`；`activateGame` 不承载游戏页排行榜展示数据的拉取职责。

对局流程由 `gameSessionService` 编排：开局 → 进行中 → 结算 → 写历史 / pending → `syncService.flushPendingIfOnline`。

### 2.5 数据模式（本地 / 在线）

| `repositoryMode` | 行为 |
|------------------|------|
| `local` | 纯本地，不主动拉远端榜、不 flush 同步 |
| `auto` | 探测后端可用性；在线则 remote + 同步 |
| `remote` | 强制走远端（需 health 通过） |

实现：`dataModeService`、`remoteGate.canFetchRemote()`。

### 2.6 统一游戏页布局

`GamePlayLayout` 提供 slots：`config` / `shop` / `ranking` / `hud` / `board` / `inventory`。游戏页注入 `GameConfigPanel`、`GameShopPanel`、`GameRankingPanel` 等，详见 [new-game-guide.md](new-game-guide.md)。

---

## 3. 后端架构

### 3.1 分层（每个 module）

```
api.py → module_service.py → entity_service.py → repository.py → models.py
schemas.py：Pydantic 入参/出参（JSON camelCase）
deps.py：FastAPI Depends
```

### 3.2 模块职责

| 模块 | 职责 |
|------|------|
| `boot` | 健康检查、`/boot/context`、**`POST /sync/cloud-save`** |
| `auth` | 用户名登录 |
| `user` | 用户、设备、系统/游戏设置 |
| `game` | 游戏列表、配置详情 |
| `prop` | 道具定义 |
| `wallet` | 钱包与流水 |
| `inventory` | 背包数量、使用记录 |
| `purchase` | 购买道具 |
| `match` | 对局记录查询 |
| `score` | 成绩实体、排行榜规则计算 |
| `ranking` | 排行榜 HTTP 查询 |
| `sync` | 同步编排（逻辑在 `module_service`，路由挂在 boot） |
| `admin_config` | 种子导入（运维）；**唯一业务种子源码**在前端 `GAME_SEED_CONFIG`，可用 `npm run export:seed` 生成 JSON |
| `system` | 系统 KV 配置 |

### 3.3 数据库初始化与业务种子

- 应用启动时 `init_db()` 仅负责注册 ORM 元数据并 `create_all` **建表**，**不**写入游戏定义、难度、道具、排行榜规则等业务行。
- 业务数据须通过 `POST /admin/config/import-game-seed` 导入；请求体应与前端 `game-hub/src/constants/gameSeedConfig.js` 中 `GAME_SEED_CONFIG` 一致，开发/CI 可在 `game-hub` 目录执行 `npm run export:seed` 生成 `dist/game-seed.json` 再导入。
- Docker 镜像构建阶段已执行 `export:seed`，运行时可通过静态路径 **`/game-seed.json`** 拉取同源 JSON 并 POST 至上述接口（详见 [docker-guide.md](docker-guide.md)）。

### 3.4 API 前缀

- 默认：`/api/game-hub`（`settings.API_PREFIX`）
- Docker 内：nginx `location /api/` → uvicorn `127.0.0.1:8000`

---

## 4. 核心数据流

### 4.1 启动

```
前端 bootService
  → POST /boot/context { userId?, deviceId, clientTime }
  ← games[], user?, systemSetting, serverTime
  → platformStore / userStore / settingStore
```

### 4.2 云同步（sync）

```
离线操作 → historyRepository 入队 pendingEvents
结算或显式同步 → syncService.sync()
  → POST /sync/cloud-save { userId, deviceId, pendingEvents[], clientSnapshotVersion }
  ← 快照：wallet, inventory, matchRecords, scoreRecords, ...
  → syncRepository.applyCloudSnapshot + clearSyncedPending
```

**事件类型**：`match_record`、`score_record`、`prop_purchase`、`prop_usage`、`wallet_ledger`、`user_update` 等。  
**合并策略**：状态按 `updatedAt`；事件按 `clientId` 幂等。

### 4.3 排行榜（ranking）

游戏页展示路径（由 `GameRankingPanel` 发起请求，**游戏页不直调** ranking 层）：

```
GameRankingPanel（onMounted / watch props）
  → rankingRepository / rankingService（组件内封装）
  → GET /rankings?gameCode&mode&difficultyCode&limit
  ← 服务端按 game_definition.config.ranking.modes[mode] 排序 score_record
  → rankingStore
  → GameRankingPanel 渲染
```

胜利结算后，`gameSessionService` 可通过 `syncService.refreshRemoteAfterSettle({ includeRanking: true, ... })` 在**结算链路**中触发与排行榜相关的远端刷新，用于尽快对齐服务端视图；与 `{Game}Page` 内排行榜展示请求的职责分离。

必须带齐 `gameCode`、`mode`、`difficultyCode`（有难度时）。

### 4.4 背包与商城（inventory / purchase）

```
shopService.loadGameShop(gameCode)
  → propRules + 定义 → shopStore → GameShopPanel

purchaseService.buyProp → POST /purchases → wallet + inventory 更新

inventoryService.refreshGameBag → GET /users/{userId}/inventory?gameCode
  → inventoryStore → GameInventoryPanel（只读展示，使用由 Page 处理）
```

### 4.5 对局（match）

```
gameSessionService 结算
  → 构造 match_record（gameCode, mode, difficultyCode, result, score, durationMs, propUses[], payload{}）
  → 本地历史 + pendingEvents（eventType: match_record）
  → flushPendingIfOnline → 云端持久化
  → GET /users/{userId}/matches 刷新列表（可选）
```

---

## 5. 前后端协作边界

| 能力 | 权威方 | 说明 |
|------|--------|------|
| 计分 / 防作弊 | 服务端（在线） | 前端乐观展示 |
| 棋盘状态 | 前端内存 | 结算后写入对局记录 |
| 道具价格 | 服务端 propRules | 前端只展示 |
| 排行榜顺序 | 服务端 ranking 配置 | 前端只请求与展示 |

---

## 6. 相关文档

- 接口明细：[api.md](api.md)
- 新游戏接入：[new-game-guide.md](new-game-guide.md)
- 前端规范：[code-style/frontend-code-style.md](code-style/frontend-code-style.md)
- 后端规范：[code-style/backend-code-style.md](code-style/backend-code-style.md)
- 部署：[docker-guide.md](docker-guide.md)
