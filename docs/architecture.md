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
        ┌───────────────────┼───────────────────┬───────────────┐
        ▼                   ▼                   ▼               ▼
   minesweeper           match3              2048           sudoku
   games/minesweeper/    games/match3/    games/game2048/  games/sudoku/
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
| `src/game-templates/` | **可选**页面模板（如 `light-single`）：仅排版与容器，不含规则/API/store |
| `src/components/game/` | 跨游戏底层 UI（分包见 §2.7）：`layout/`、`panels/`、`stats/`、`controls/` |
| `src/services/` | 业务编排：开局、结算、同步、商城、在线状态、实时通道 |
| `src/repositories/` | 数据访问：local / remote / sync 屏蔽 |
| `src/stores/` | Pinia 响应式状态快照 |
| `src/composables/` | 跨组件 UI 逻辑（动画队列、主题、`usePageVisibilityPause` 等） |
| `src/constants/` | `GAME_REGISTRY`、`GAME_SEED_CONFIG` |
| `src/mappers/` | API DTO → 领域对象 |
| `src/api/` | HTTP 封装（`request.js`、`gameHubApi.js`、`onlineApi.js`） |

### 2.2 依赖方向

```
Page / games/*Page.vue
    → services（+ 可选 games/*Service.js）
        → repositories → api / localRepository
stores ← 仅由 services 写入，供 UI 读取
games/*Engine.js ← 纯算法，无 Vue / DOM / 网络
realtimeService → websocketClient → /ws/game-hub/realtime
```

### 2.3 注册表与配置

| 来源 | 文件 | 用途 |
|------|------|------|
| 前端能力 | `constants/gameRegistry.js` | `modes`、`capabilities`（leaderboard/shop/inventory）；可选 `viewTemplate`（页面模板，**不**进 seed） |
| 离线种子 | `constants/gameSeedConfig.js`（`GAME_SEED_CONFIG`，**唯一业务种子源码**） |
| 种子 JSON | `npm run export:seed` → `dist/game-seed.json`（与上者一致，供导入 / curl） |
| 在线配置 | `gameConfigService` → `GET /games/{gameCode}/config` | 覆盖种子；未加载成功时使用 `GAME_SEED_CONFIG` |

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
| `local` | 纯本地，不启用在线状态刷新、不连接 WebSocket、不刷新在线用户人数；除健康检查外，不发送远端业务请求 |
| `auto` | 探测后端可用性；在线则获取当前用户并启动在线运行时，否则使用本地数据 |
| `remote` | 强制走远端（需 health 通过），获取当前用户后启动在线运行时 |

实现：`dataModeService`、`remoteGate.canFetchRemote()`、`api/request.js`。模式切换到本地时会停止在线状态刷新、尝试标记离线、断开实时通道并清理重连与心跳；切换到在线可用状态时会健康检查、刷新当前用户上下文、执行 `markOnline()`、启动在线状态刷新并建立实时通道。

### 2.6 游戏页布局（平台布局 vs 可选模板）

| 类型 | 位置 | 定位 |
|------|------|------|
| `GamePlayLayout` | `src/components/game/layout/` | 平台通用左右分栏；slots：`config` / `shop` / `ranking` / `hud` / `board` / `inventory` |
| `LightSingleGameLayout` | `src/game-templates/light-single/` | **轻量单人可选模板**：左信息+商城+榜，右对局信息+**棋盘外框**+背包；内部复用 `GameControlPanel` 等底层组件 |

**`light-single` 原则**

- 模板只负责排版与 `LightSingleGameBoardFrame` 等容器；**不**调用 API/store/engine，**不** import 具体游戏。
- `LightSingleGameBoardFrame` 在对局区 slot 上承载 `GamePauseOverlay`（`paused` / `resume` 由业务页传入）；暂停状态与计时由游戏 Page 维护，通用组件只展示并 `emit('resume')`。
- 浏览器标签页隐藏时的自动暂停由 `usePageVisibilityPause` 统一监听；**返回可见不自动继续**，恢复仅经左侧按钮或暂停遮罩。
- 左侧信息/配置/操作由 `LightSingleGameSidePanel` → `GameControlPanel`（`controls/`）展示；业务页计算 `infoStats` / `fields` / `actions`，模板只转发事件。
- 商城 / 排行榜 / 背包仍由页面通过 slot 注入 `panels/` 下 `GameShopPanel`、`GameRankingPanel`、`GameInventoryPanel`。
- `viewTemplate: 'light-single'` 仅写在 `GAME_REGISTRY`，**不**写入 `GAME_SEED_CONFIG` / `game-seed.json`。
- 已接入 `light-single` 的示例：`minesweeper`、`match3`、`2048`、`sudoku`（左侧 `GameControlPanel`，右侧 `GameMatchStatsPanel` + `LightSingleGameBoardFrame`）。
- 五子棋、飞行棋、Canvas 重游戏等可继续自定义页面或沿用 `GamePlayLayout`，**不强制**使用 `light-single`。

页面模板 ≠ 平台通用组件：`components/game/` 是**底层组件层**（展示 + emit）；`game-templates/` 是**模板层**（排版与 slot 容器）。

详见 [new-game-guide.md §3.1](new-game-guide.md#31-轻量单人可选模板-light-single)。

### 2.7 `components/game/` 分包

```
src/components/game/
├── layout/      GamePlayLayout — 左右分栏骨架
├── panels/      商城、排行榜、背包、结算弹窗、暂停遮罩、配置/HUD 外壳（可含 store/service）
├── stats/       对局统计展示（纯展示，无 gameCode 分支）
├── controls/    游戏信息、配置项、操作按钮（纯展示，无 API/store）
└── index.js     统一聚合导出入口（对外 import 优先从此文件）
```

**import 约定**

- 业务页面、页面模板、跨游戏代码：**优先** `import { GameShopPanel, GAME_ACTION_TYPE, ... } from '@/components/game/index.js'`（或 `@/components/game`、等价相对路径）。
- 也可按需 **明确分包路径**（如 `components/game/stats/GameMatchStatsPanel.vue`）。
- **禁止**在 `src/components/game/` 根目录放置带 `<template>` 的 `.vue` 实现；组件实现须位于 `layout/`、`panels/`、`stats/`、`controls/` 之一，并由 `index.js` 导出。

| 子目录 | 职责 | 典型组件 |
|--------|------|----------|
| `controls/` | 标题/描述/状态、配置 fields、操作 actions；**业务页**算 `visible`/`disabled`/`value`/`options`，组件只 `emit` | `GameControlPanel`、`GameActionBar`、`gameControlEnums.js` |
| `stats/` | 当前对局数据卡片网格；**业务页**传 `stats[]`（含 `GAME_STAT_TONE`），组件内组合 `GameStatGrid` + `GameStatCard` | `GameMatchStatsPanel`、`GameHudStats` |
| `panels/` | 平台业务能力 UI（商城购买、排行榜请求等）；纯展示暂停遮罩 | `GameShopPanel`、`GameRankingPanel`、`GamePauseOverlay` |
| `layout/` | 无业务、仅 slots | `GamePlayLayout` |

**样式枚举**（`controls/gameControlEnums.js`）：`GAME_ACTION_TYPE`、`GAME_ACTION_SIZE`、`GAME_CONTROL_TYPE`、`GAME_STAT_TONE`。业务页传枚举值驱动样式；`extraClass` 仅作附加扩展样式，**不应**作为主要风格手段。暂停遮罩「继续游戏」使用 `GAME_ACTION_TYPE.RESUME`（`game-action-btn--resume`）。

**`GameControlPanel`**：`props` — `title`、`subtitle`、`description`、`statusText`、`infoStats`、`fields`、`actions`；`emit` — `field-change`、`action`。不判断 `gameCode`，不调 API/store。

**`GameMatchStatsPanel`**：`props` — `stats`、`quotas`、`message`、`themeSeed`、`columns`、`compact`；内部复用 `GameHudStats` / `GameStatGrid` / `GameStatCard` / `GameStatQuotaBar`，禁止写具体游戏分支。

### 2.8 统一游戏设置（Game Settings）

平台通过 **`constants/gameSettingDefinitions.js`**（`GAME_SETTING_DEFINITIONS`）注册各游戏可配置项；**顶部栏设置面板**（`GameHubPage` → `gameSettingService`）是平台级统一入口，展示**全部**已注册游戏设置，**不**依赖当前选中的 `gameCode`。

| 原则 | 说明 |
|------|------|
| 配置驱动 | 新增开关/选项须先在 `GAME_SETTING_DEFINITIONS` 登记 `gameCode`、`gameName`、`settings[]`（`key`、`label`、`type`、`defaultValue` 等） |
| 隔离维度 | 持久化与内存态按 **`gameCode` + `settingKey`** 隔离：每个 `gameCode` 对应一行 `setting` 对象，键为 `settingKey`，值为 `settingValue` |
| 页面只读 | 游戏页通过 **`userService.readGameSettingBoolean`**（或游戏内 `*Service` 薄封装）读取；**不**在 Page 维护独立 localStorage 或并行配置结构 |
| 写入链路 | 变更经 **Service → Repository → 本地缓存 → 同步队列 → 后端**，见下文数据流 |
| 公共组件 | `components/game/`、`game-templates/` **禁止** `if (gameCode === 'xxx')` 等游戏特判 |

**顶栏展示**

- `gameSettingService.buildHubGameSettingGroups()` 遍历 `GAME_SETTING_DEFINITIONS`，从 `userStore` 的 `gameSettings[gameCode][settingKey]` 取已保存值，无则 `defaultValue`。
- `setHubGameSettingSwitch(gameCode, key, value)` → `userService.updateGameSetting(gameCode, { [key]: value })`。

**游戏页读取**

- 游戏内 `*PageSettings.js` 仅通过 `findGameSettingDefinition(gameCode, key)` 引用与顶栏同源的 label/description；读写走 `*Service` → `userService`（示例：扫雷 `highlightAroundCells`、数独 `filterUnavailableNumbers`）。
- 游戏页**不**在左侧 `GameControlPanel` 重复展示已在顶栏注册的开关。

**设置同步数据流**

```
Page / GameHubPage（用户改开关）
  → gameSettingService / userService（或 games/*Service 薄封装）
    → userRepository.patchGameSettingForCurrentUser → persistAllLocal
    → userService.queueSettingsSync({ gameCode })
      → userRepository.buildGameSettingPendingEvent
      → syncRepository.appendPendingEvent（eventType: user_game_setting_update）
      → syncService.flushPendingIfOnline
        → POST /sync/cloud-save
```

云端快照 / 启动上下文中的 `userGameSettings[]` 经 `userRepository.applyGameSettingToLocal` 合并进 `userStore.gameSettings`。

**禁止**

| 禁止 | 原因 |
|------|------|
| 页面直接 `fetch` 游戏设置接口 | 走 `userService` + `userRepository` |
| 页面直接 `localStorage` 写游戏偏好 | 与 `userStore` / `persistAllLocal` 双轨 |
| Store 内调 API 或拼同步 payload | Store 只存快照 |
| 公共组件按 `gameCode` 分支展示设置 | 顶栏统一展示，游戏页只消费 |
| 各游戏自建独立设置存储结构 | 与 `gameCode` 下 `setting` 对象冲突 |

接口与事件字段见 [api.md §4.5–4.6、§2.3](api.md#45-获取用户游戏设置)；接入步骤见 [new-game-guide.md §9](new-game-guide.md#9-新增游戏设置)。

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
| `online` | 在线用户、在线房间、临时缓存、对局暂存等运行期临时态业务；当前提供在线用户状态与在线用户列表 |
| `admin_config` | 种子导入（运维）；**唯一业务种子源码**在前端 `GAME_SEED_CONFIG`，可用 `npm run export:seed` 生成 JSON |
| `system` | 系统 KV 配置 |

### 3.3 平台运行期基础能力

| 层 | 位置 | 职责边界 |
|------|------|------|
| Redis 工具层 | `app/core/redis/` | 封装字符串、JSON、Hash、Set、Sorted Set、scan、expire 等缓存数据结构操作；业务代码通过 `RedisClient` 与 `RedisKeys` 使用 Redis |
| WebSocket 实时通道层 | `app/core/websocket/` | 维护 `/ws/game-hub/realtime` 单一平台通道，负责连接管理、按 `serviceId` 发送、广播、消息分发、`online.ping` / `online.pong` |
| Online 业务模块 | `app/modules/online/` | 管理运行期在线用户状态与列表，在线状态只写 Redis，不写数据库 |

Redis 不承载业务规则，WebSocket 不承载在线用户判定；在线用户列表以 Redis TTL 为准，WebSocket 断开不直接等同于离线。

`/ws/game-hub/realtime` 建连时校验 `serviceId` 对应的用户存在且可用，`serviceId` 缺失、无效或用户不可用时以 close code `1008` 拒绝；前端将 `1008` 视为身份/权限失败，不自动重连。普通网络异常使用指数退避重连，手动关闭与本地模式切换不重连。连接管理器只保存已校验用户连接。应用启动时会执行 Redis ping 检查并记录 host、port、db；Redis 不可用只记录错误，不阻断服务启动。

顶部栏在线用户入口属于平台在线能力展示，不放入具体游戏页或对局信息面板。在线模式下，在线人数 badge 由顶部栏组件通过 `onlineService` 主动加载并定时刷新，不依赖弹窗打开；本地模式下停止刷新并不请求在线用户接口。前端仅展示昵称与基于 `onlineAt` 计算的在线时长，不展示 `username`、`serviceId` 或其它账号类字段。

### 3.4 数据库初始化与业务种子

- 应用启动时 `init_db()` 仅负责注册 ORM 元数据并 `create_all` **建表**，**不**写入游戏定义、难度、道具、排行榜规则等业务行。
- 业务数据须通过 `POST /admin/config/import-game-seed` 导入；请求体须与前端 `game-hub/src/constants/gameSeedConfig.js` 中 `GAME_SEED_CONFIG` 导出的 JSON **字段级一致**（含 `games[].propRules[].sortNo` 等必填项；后端 schema `extra=forbid`，缺字段或多余字段均会校验失败），开发/CI 可在 `game-hub` 目录执行 `npm run export:seed` 生成 `dist/game-seed.json` 再导入。
- Docker 镜像构建阶段已执行 `export:seed`，运行时可通过静态路径 **`/game-seed.json`** 拉取同源 JSON 并 POST 至上述接口（详见 [docker-guide.md](docker-guide.md)）。

### 3.5 API 前缀

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

### 4.6 统一游戏设置

```
顶栏 / 游戏页改设置
  → userService.updateGameSetting(gameCode, patch)
  → userRepository.patchGameSettingForCurrentUser + persistAllLocal
  → queueSettingsSync → pendingEvents（user_game_setting_update）
  → flushPendingIfOnline → POST /sync/cloud-save
  ← userGameSettings[] 写入快照 → applyGameSettingToLocal
```

在线时也可经 `GET/PUT /users/{userId}/games/{gameCode}/setting` 读写整包 `setting` 对象；日常变更以云同步事件为主。逻辑键为 **`gameCode` + `settingKey`**，值类型支持布尔、数字、字符串及 JSON 对象（见 [api.md](api.md)）。

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
