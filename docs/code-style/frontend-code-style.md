# Game Hub 前端代码规范

> **面向对象**：Cursor / AI 代码生成、人类 Code Review。  
> **默认效力**：除非用户 prompt 明确例外，所有前端改动 **必须** 遵循本文档。  
> **技术栈**：Vue 3 + Pinia + Vue Router + Vite（纯 JavaScript，无 TypeScript）。  
> **新游戏接入**：见 [`docs/new-game-guide.md`](../new-game-guide.md)，本文不重复接入步骤。

---

## 目录

1. [项目架构总览](#1-项目架构总览)
2. [目录结构规范](#2-目录结构规范)
3. [分层职责规范](#3-分层职责规范)
4. [Vue 页面规范](#4-vue-页面规范)
5. [Vue 组件规范](#5-vue-组件规范)
6. [Composable 规范](#6-composable-规范)
7. [游戏算法规范](#7-游戏算法规范)
8. [Repository 规范](#8-repository-规范)
9. [Service 规范](#9-service-规范)
10. [Store 规范](#10-store-规范)
11. [API 调用规范](#11-api-调用规范)
12. [本地缓存规范](#12-本地缓存规范)
13. [同步与离线规范](#13-同步与离线规范)
14. [排行榜规范](#14-排行榜规范)
15. [道具与商城规范](#15-道具与商城规范)
16. [对局记录规范](#16-对局记录规范)
17. [动画规范](#17-动画规范)
18. [配置化规范](#18-配置化规范)
19. [文件体积规范](#19-文件体积规范)
20. [命名规范](#20-命名规范)
21. [禁止事项](#21-禁止事项)
22. [Cursor 执行规则](#22-cursor-执行规则)
23. [游戏页面统一布局规范](#23-游戏页面统一布局规范)
24. [游戏公共组件规范](#24-游戏公共组件规范)
25. [游戏页面数据流规范](#25-游戏页面数据流规范)
26. [游戏页面禁止事项](#26-游戏页面禁止事项)

---

## 1. 项目架构总览

### 1.1 设计目标

| 目标 | 说明 |
|------|------|
| 分层清晰 | 页面 / 游戏页只编排 UI 与交互；业务在 Service；数据在 Repository |
| 可离线 | Repository 屏蔽 local / remote / sync，页面不感知在线状态 |
| 可配置 | 棋盘尺寸、元素、道具、奖励等均来自 `GAME_SEED_CONFIG` 或服务端 game config |
| 可扩展 | 新游戏按 `src/games/{gameCode}/` 模板接入，禁止为单游戏污染平台层 |
| AI 友好 | 允许/禁止清单明确，减少 prompt 重复描述 |

### 1.2 依赖方向（单向，禁止反向）

```
pages/、games/*Page.vue
    ↓ 调用
services/、games/*Service.js（游戏内编排，可选）
    ↓ 调用
repositories/
    ↓ 调用
api/、localRepository、syncRepository
```

```
stores/  ← 仅被 pages / services 读写，不调用下层
```

```
games/*Engine.js  ← 纯算法，被 Page / Service 调用，不依赖 Vue / DOM / 网络
```

### 1.3 数据模式

| `repositoryMode` | 行为摘要 |
|------------------|----------|
| `local` | 纯本地；`networkMode` 视为 offline；**不**主动拉远端排行榜 |
| `auto` | 探测远端可用性；可用则 online，否则 offline；允许同步 |
| `remote` | 强制走远端（需 healthCheck 通过） |

相关实现参考：`dataModeService.js`、`remoteGate.js`（`canFetchRemote()`）。

---

## 2. 目录结构规范

### 2.1 根目录

```
game-hub/
├── src/
│   ├── api/                      # HTTP 封装
│   ├── assets/                   # 全局样式、静态资源
│   ├── components/               # 跨游戏通用 UI
│   ├── constants/                # 注册表、种子配置、注入 key
│   ├── games/                    # 各游戏独立模块
│   ├── mappers/                  # API/DTO → 领域对象映射
│   ├── pages/                    # 路由级平台页面（非具体游戏）
│   ├── repositories/             # 数据访问与本地持久化
│   ├── router/
│   ├── services/                 # 平台级业务编排
│   ├── stores/                   # Pinia 状态
│   └── utils/                    # 无业务语义的纯工具
├── index.html
├── vite.config.js
└── package.json
```

### 2.2 `src/pages/` — 平台页面

| 允许 | 禁止 |
|------|------|
| 游戏大厅、不可用页等平台级编排 | 具体游戏棋盘算法 |
| 调用 `bootService`、`gameCatalogService` 等 | 直接 `fetch` / `localStorage` |
| 路由跳转、全局布局 | 写死某一游戏的业务规则 |

现有示例：`GameHubPage.vue`、`GameUnavailablePage.vue`。

### 2.3 `src/games/{gameCode}/` — 游戏模块

每个已接入游戏 **至少** 包含：

```
src/games/{gameCode}/
├── {Game}Page.vue           # 游戏主页面（路由入口）
├── {game}Engine.js          # 纯算法（消消乐、路径等；扫雷可拆 types + 算法模块）
├── {game}Config.js          # 本游戏默认/解析配置（从种子或服务端合并）
├── components/              # 仅本游戏使用的 UI 子组件
├── composables/             # 可选：可复用的 Vue 组合逻辑
├── {game}Service.js         # 可选：仅当游戏有独立编排且不宜放平台 service 时
└── README.md                # 可选：游戏说明
```

### 2.4 其他目录职责速查

| 目录 | 职责 |
|------|------|
| `api/` | 仅 HTTP；见 [§11](#11-api-调用规范) |
| `mappers/` | 字段归一、类型转换；无业务流程 |
| `repositories/` | save / get / query / merge；见 [§8](#8-repository-规范) |
| `services/` | 编排、toast、同步时机；见 [§9](#9-service-规范) |
| `stores/` | 可响应 UI 的状态快照；见 [§10](#10-store-规范) |
| `constants/` | `GAME_REGISTRY`、`GAME_SEED_CONFIG`、`injectionKeys` |
| `utils/` | `idService`、`timeService`、`debounce` 等无领域语义工具 |

### 2.5 禁止的目录操作

- **禁止** 未经需求将 `games/` 下文件移到 `components/` 或反之（游戏专用 vs 平台通用边界）。
- **禁止** 在 `api/` 下新建「业务用」子目录堆砌逻辑。
- **禁止** 在 `stores/` 下按游戏再套一层深层目录（用 `gameCode` 字段区分即可，如 `rankingStore`）。

---

## 3. 分层职责规范

### 3.1 页面层（`pages/`、`games/*Page.vue`）

**职责**

1. 页面编排与布局。
2. 用户交互（点击、拖拽、键盘）。
3. **动画播放**（解释 Engine 返回的 `animationSteps`）。
4. 调用 **Service**（平台或游戏内）。
5. 读写 **Store** 用于展示（通过 service 刷新后的结果）。

**允许**

- `import` Engine，传入 config/state，接收新 state + `animationSteps`。
- 调用 `gameLifecycleService.activateGame`、`createGameSession`（`gameSessionService.js`）等。
- 使用 `composables/` 抽取 UI 状态机（动画队列、选格模式等）。

**禁止**

| # | 禁止项 |
|---|--------|
| 1 | 直接 `fetch` / 调用 `api/*` |
| 2 | 直接 `localStorage` / `readJson` / `LS_KEYS` |
| 3 | 直接 `import` 并操作 `syncRepository` 的 pending 队列 |
| 4 | 在页面内 `flushPendingIfOnline`、`sync()` |
| 5 | 复杂棋盘算法（> 少量展示用计算） |
| 6 | 业务规则：计价、同步合并、排行榜筛选策略 |

### 3.2 Service 层（`services/`、`games/*Service.js`）

**职责**

1. 业务流程编排（开局 → 进行 → 结算 → 刷新榜单/背包）。
2. 聚合多个 Repository。
3. 控制 **toast**、**loading**、**BootSyncMask** 等用户反馈时机。
4. 决定 **何时同步**（调用 `syncService`，而非页面）。
5. 按 `canFetchRemote()` / `repositoryMode` 裁剪远端调用。

**允许**

- 读写 Store（作为编排结果落地）。
- 调用多个 Service（注意避免循环依赖）。
- 调用 Engine **仅做**「一步规则校验」的薄封装（复杂链式仍应在 Engine）。

**禁止**

| # | 禁止项 |
|---|--------|
| 1 | 操作 DOM、`document`、`querySelector` |
| 2 | 大型棋盘生成/消除/路径算法（应下沉 Engine） |
| 3 | 在 Service 内直接 `localStorage.setItem`（走 Repository） |
| 4 | 在 Service 内写 HTTP URL 拼接（走 api + repository） |

### 3.3 Repository 层（`repositories/`）

**职责**

1. **屏蔽数据来源**：远端 API、本地 cache、sync cache 对上层一致。
2. 提供 **`save` / `get` / `query` / `merge`** 语义化方法。
3. 本地键名集中在 `localRepository.LS_KEYS` 或专用 repo。
4. 使用 `mappers/` 做结构转换。

**允许**

- 读写在离线时可降级为仅本地。
- `merge` 冲突策略（版本号、时间戳）放在 Repository。

**禁止**

| # | 禁止项 |
|---|--------|
| 1 | 业务规则（例如「胜利奖励 = 配置 × 连击」应在 Service + config） |
| 2 | `toast`、路由跳转 |
| 3 | 操作 DOM |
| 4 | 依赖 Vue 组件或 Pinia（除只读常量外，repo 应尽量无 store） |

### 3.4 Store 层（`stores/`）

**职责**

1. **只存状态**（及简单的 setter / 派生 getter）。
2. 为 UI 提供响应式快照：用户、钱包、排行榜缓存、待同步事件列表等。

**禁止**

| # | 禁止项 |
|---|--------|
| 1 | 请求 API |
| 2 | 直接 `localStorage` |
| 3 | 业务流程（if 开局 then 拉榜） |
| 4 | 同步逻辑、`buildSyncPayload` |
| 5 | 复杂棋盘计算 |

### 3.5 API 层（`api/`）

**职责**

1. 封装 HTTP：method、path、query、body。
2. 统一走 `request.js`（错误、baseURL、headers）。

**禁止**：业务逻辑、local cache、toast、store。

---

## 4. Vue 页面规范

### 4.1 文件命名

- 平台页：`XxxPage.vue`（如 `GameHubPage.vue`）。
- 游戏页：`{Game}Page.vue`（如 `MinesweeperPage.vue`、`Match3Page.vue`）。

### 4.2 结构建议

```vue
<script setup>
// 1. vue / vue-router / pinia
// 2. 平台 services、stores
// 3. 本游戏 engine、config、components
// 4. composables

// ref / computed / watch
// 生命周期：onMounted → activateGame / initBoard
// 事件处理：薄 handler → service 或 engine
</script>

<template>
  <!-- 布局 + 子组件；避免巨型 template -->
</template>

<style scoped>
/* 优先 scoped；游戏大量样式可 games/{code}/*.css 并在 Page import */
</style>
```

### 4.3 生命周期

| 时机 | 应做 | 不应做 |
|------|------|--------|
| `onMounted` | `activateGame(gameCode, { mode, difficultyCode, includeInventory })`（与 `match3` / `minesweeper` 一致） | 在 `{Game}Page` 生命周期内直调 ranking API 或 `rankingService`；一次拉取全部 difficulty 的榜 |
| `onUnmounted` | 取消动画 RAF、解绑监听 | — |
| 难度切换 | 更新 `difficultyCode`；由 `GameRankingPanel` 随 props 拉当前难度榜 | `fetchAllLeaderboards` |

### 4.4 与 Router

- 游戏路由在 `router/index.js` 注册，component 指向 `games/{gameCode}/{Game}Page.vue`。
- 未启用游戏走 `GameUnavailablePage`，不在游戏页内 hack 404。

---

## 5. Vue 组件规范

### 5.1 分类与命名

| 类型 | 命名 | 位置 |
|------|------|------|
| 弹窗 | `XxxModal.vue` | `components/` 或 `games/.../components/` |
| 面板 | `XxxPanel.vue` | 同上 |
| 棋盘/核心盘 | `XxxBoard.vue` | 优先游戏目录 |
| HUD | `XxxHud.vue` | 游戏目录 |

### 5.2 职责边界

**允许**

- Props 下发展示数据、config 片段。
- Emits 上报 `select-cell`、`submit` 等意图事件。
- 展示型 `computed`（格式化时间、高亮合法格）。

**禁止**

- 组件内调用 Repository / API。
- 组件内发起同步、写 pendingEvents。
- 单组件同时承担：**UI + 动画时间轴 + 业务编排 + 同步**（应拆分）。

### 5.3 Props / Emits

- 使用 **camelCase** 的 prop 名；template 中 kebab-case 自动映射。
- 事件名使用 **kebab-case**：`@cell-click`、`@use-prop`。
- 避免「上帝 prop」：超过 8 个 props 考虑合并为 `context` 对象或拆组件。

### 5.4 样式

- 默认 `<style scoped>`。
- 复用平台样式：`src/assets/app.css`。
- 复用游戏目录或 `assets/` 下**带游戏前缀**的样式文件，**禁止** 未加前缀的全局选择器污染其它页面。

---

## 6. Composable 规范

### 6.1 何时提取

- 同一游戏内 **2+** 组件共享的动画队列、选格模式、计时器。
- Page 超过 **400 行** 时，优先抽 composable 而非继续堆 Page。

### 6.2 命名与位置

- 文件：`useXxx.js` 或 `useXxxLogic.js`，放在 `games/{gameCode}/composables/`。
- 导出：`export function useMatch3Animation() { ... }`

### 6.3 允许 / 禁止

| 允许 | 禁止 |
|------|------|
| `ref` / `computed` / `watch` 管理 UI 状态 | 在 composable 内 `fetch` |
| 封装 `playAnimationSteps` 队列 | 直接写 `localStorage` |
| 调用 Engine 做**预览**下一步 | 调用 `syncService.sync` |

---

## 7. 游戏算法规范

### 7.1 Engine 文件（`xxxEngine.js`）

**必须是纯函数模块**（可有模块级 `let nextId` 计数器，但不得依赖 Vue 实例）。

**只负责**

- 棋盘初始化、洗牌、填充。
- 碰撞、消除、下落、路径、死局检测。
- 分数增量、连击计数（**数值**）。
- AI 决策（若需要）。
- 返回 **`animationSteps`** 描述「发生了什么」，不执行动画。

**禁止**

| # | 禁止项 |
|---|--------|
| 1 | `import` from `vue` |
| 2 | `document` / `window` DOM 操作 |
| 3 | `localStorage` / `sessionStorage` |
| 4 | Pinia store |
| 5 | HTTP / `fetch` |
| 6 | `setTimeout` / `setInterval` / `requestAnimationFrame` |
| 7 | 在 Engine 内 `console` 刷屏（调试用完即删） |

### 7.2 输入输出约定

```js
/**
 * @param {object[][]} board
 * @param {{ row: number; col: number }} pos
 * @param {object} config  // 来自 match3Config / 服务端合并结果
 * @returns {{
 *   board: object[][];
 *   animationSteps: object[];
 *   scoreDelta?: number;
 *   deadBoard?: boolean;
 * }}
 */
export function applySwap(board, pos, config) { ... }
```

### 7.3 `animationSteps` 形状（参考 match3）

| type | 含义 | cells 内容 |
|------|------|------------|
| `remove` | 消除 | `{ id, row?, col? }[]` |
| `drop` | 下落 | 带 from/to 或 row/col |
| `spawn` | 新生成 | 新 cell |
| `swap` | 交换（含无效回弹） | 两个格 |
| `shuffle` | 洗牌 | 全盘 id |
| `bomb` | 道具爆炸范围 | 被清除格 |
| `combo` | 连击展示 | `{ combo: number }` |

Engine **只产出** 上述结构；**不** 含 CSS class 名或毫秒时长（时长由 Page/composable 决定）。

### 7.4 游戏内 Service（`minesweeperService.js`）

- 扫雷等 **无** 独立 `Engine.js` 时，算法文件仍须保持 **无 Vue、无 DOM**。
- 若算法膨胀，应拆出 `minesweeperEngine.js`，与 `minesweeperTypes.js` 共存。

---

## 8. Repository 规范

### 8.1 文件命名

- `xxxRepository.js`，默认 **named export** 函数集合。
- 聚合类数据源可用 `export const xxxRepository = { ... }`（如 `remoteRepository`）。

### 8.2 方法命名

| 语义 | 示例 |
|------|------|
| 读取 | `getXxx`、`readXxx`、`fetchXxx`（fetch 仅当内含远端+映射） |
| 写入 | `saveXxx`、`writeXxx`、`appendXxx` |
| 查询列表 | `queryXxx`、`listXxx` |
| 合并 | `mergeXxx`、`applyCloudSnapshot` |

### 8.3 本地键

- **统一** 在 `localRepository.LS_KEYS` 注册键名；禁止在业务文件散落字符串 key。键名变更时仅在 Repository 层集中调整读写路径。

### 8.4 与 remote / local 分工

| 模块 | 职责 |
|------|------|
| `localRepository` | 原子 read/write JSON |
| `localPersistRepository` | 批量持久化内存态 |
| `remoteRepository` | 调用 `gameHubApi` |
| `syncRepository` | pending 队列、snapshot 版本、payload 构建 |
| `historyRepository` | 对局记录读写 + refresh |
| `rankingRepository` | 排行榜 fetch + mapper |
| `inventoryRepository` / `purchaseRepository` / `walletRepository` | 各领域数据 |

### 8.5 允许 / 禁止

| 允许 | 禁止 |
|------|------|
| try/catch 后返回空数组/默认值 | toast |
| 调用 mapper | 在 repo 内判断「是否胜利发奖」 |
| 根据 `canFetchRemote` 在 **上层 service** 决定；repo 可提供 `fetchLocalOnly` 变体 | Page 直接 import `syncRepository.clearSyncedPending` |

---

## 9. Service 规范

### 9.1 文件命名

- `xxxService.js`；平台级放 `services/`，游戏特有放 `games/{gameCode}/`。

### 9.2 平台 Service 一览（扩展时对齐）

| Service | 职责 |
|---------|------|
| `bootService` | 应用启动、登录态恢复 |
| `gameCatalogService` | 游戏列表、可用性 |
| `gameConfigService` | 加载/合并游戏配置 |
| `gameLifecycleService` | `activateGame` 统一入口 |
| `gameSessionService` | `createGameSession`：对局会话、结算、对局/成绩入队 |
| `syncService` | 云同步、`flushPendingIfOnline`、`refreshRemoteAfterSettle` |
| `dataModeService` | local/auto/remote 切换 |
| `rankingService` | 由 `GameRankingPanel` 与结算链路中的 `syncService.refreshRemoteAfterSettle` 调用；**`{Game}Page` 不直调** |
| `shopService` / `purchaseService` / `inventoryService` / `walletService` | 商城与资产 |
| `toastService` | 全局 toast |
| `remoteGate` | `canFetchRemote()` |

### 9.3 同步相关（仅 Service 调用）

```js
// 允许在 gameSessionService / syncService 内
await flushPendingIfOnline();
await refreshRemoteAfterSettle({ includeRanking: true, gameCode, difficultyCode, mode });
```

### 9.4 允许 / 禁止

| 允许 | 禁止 |
|------|------|
| `toastService.push(...)` | DOM 操作 |
| 多 repo 编排 | 300+ 行不拆分（应拆子函数或子 service） |
| `hasGameCapability(gameCode, 'leaderboard')` 守卫 | 写死 `if (gameCode === 'minesweeper')` 扩散到全平台（应收敛到 registry + lifecycle） |

---

## 10. Store 规范

### 10.1 命名

- 文件：`useXxxStore.js`
- `defineStore('xxx', { state, getters, actions })`
- actions **仅** 做同步赋值：`setXxx`、`clear`、`append`

### 10.2 现有 Store 参考

| Store | 存什么 |
|-------|--------|
| `platformStore` | 当前游戏、难度、networkMode |
| `settingStore` | repositoryMode 等设置 |
| `userStore` | 当前用户展示态 |
| `rankingStore` | 按 gameCode + difficulty 缓存的榜 |
| `inventoryStore` / `shopStore` / `walletStore` | 资产与商城 |
| `historyStore` | **含** `pendingEvents` 列表（由 service/repo 写入，页面只读展示） |
| `toastStore` | 全局消息 |

### 10.3 允许 / 禁止

| 允许 | 禁止 |
|------|------|
| `ranking.setDifficultyItems(gameCode, difficultyCode, items, mode)` | 在 store action 里 `await fetch(...)` |
| 从 service 批量 `patch` 状态 | 在 store 内 `localStorage` |

---

## 11. API 调用规范

### 11.1 唯一入口

- 所有 HTTP 经 `api/request.js` + `api/gameHubApi.js`（或按域拆分 `xxxApi.js`）。
- Repository 调用 API，**不** Service 直接拼 URL（除非已有项目惯例的 thin remoteRepository 封装）。

### 11.2 允许 / 禁止

| 允许 | 禁止 |
|------|------|
| REST 路径常量集中 | 在 api 内读写 cache |
| 返回原始 JSON | 在 api 内 `useRankingStore()` |

---

## 12. 本地缓存规范

### 12.1 读写权限

| 层级 | localStorage |
|------|----------------|
| Repository | ✅ 唯一允许直接读写 |
| Service | ❌ 通过 repo |
| Store | ❌ |
| Page | ❌ |

### 12.2 缓存内容

- 认证、用户、设置、钱包/背包流水、对局记录、分数记录、pending 事件、云 snapshot、设备 ID。
- 游戏 **运行时棋盘状态** 优先内存 + Store；持久化走对局结算 / session 流程，不随意整盘写 LS。

### 12.3 存储版本

- `settingStore.storageVersion` 升级时在 **boot** 或专用 service 中集中处理，不散落在各页面。

---

## 13. 同步与离线规范

### 13.1 职责矩阵

|  Concern | 负责层 |
|---------|--------|
| pending 事件入队 | Repository（`syncRepository` / history 相关） |
| 何时 flush | Service（`syncService.flushPendingIfOnline`） |
| 当前待同步条数展示 | Store `historyStore.pendingEvents` |
| 页面按钮「同步」 | 只触发 `syncService` 方法 |

### 13.2 模式行为

| 模式 | 排行榜 | 云同步 |
|------|--------|--------|
| `local` | 不主动请求远端 | 不 flush |
| `auto` / `remote` 且 online | `GameRankingPanel` / 结算编排可拉榜 | 允许 |

### 13.3 允许 / 禁止

| 允许 | 禁止 |
|------|------|
| 结算后 `refreshRemoteAfterSettle` | Page 读 `LS_KEYS.PENDING_EVENTS` 并手动 splice |
| 离线游玩、队列待传 | 页面 `onMounted` 无条件 `sync()` |

---

## 14. 排行榜规范

### 14.1 查询维度（必须齐全）

每次请求 **必须** 指定：

- `gameCode`
- `mode`（如 `single`、`timed`、`endless`）
- `difficultyCode`（若游戏有难度）

参考：`rankingRepository.fetchLeaderboardDifficulty`；游戏页展示路径为 `GameRankingPanel`（内部经 `rankingService` 完成 HTTP 与 store 写入）。

### 14.2 允许 / 禁止

| 允许 | 禁止 |
|------|------|
| 用户切换难度后由 `GameRankingPanel` 随 props 拉该难度榜 | 一次 API 拉取所有游戏排行榜 |
| `hasGameCapability(gameCode, 'leaderboard')` 为 false 时直接 return | 大厅初始化拉取所有 mode 全部 difficulty |
| local 模式下跳过远端榜 | 未进入游戏页就预拉全部榜 |

### 14.3 Store 缓存键

- 使用 `gameCode + difficultyCode + mode` 作为缓存维度，避免互相覆盖。

---

## 15. 道具与商城规范

### 15.1 配置来源

- 平台道具定义：`GAME_SEED_CONFIG.props`
- 每游戏 `propRules`：`GAME_SEED_CONFIG.games[].propRules` 或服务端 `gameConfig`
- 价格、每局上限、`triggerType`、`effectType` **不得** 在 Page 硬编码

### 15.2 流程

```
Page 触发使用意图
  → shopService / purchaseService / inventoryService
    → purchaseRepository / inventoryRepository
      → remote 或 local
```

### 15.3 允许 / 禁止

| 允许 | 禁止 |
|------|------|
| `propMapper` 统一结构 | 页面 `if (propCode === 'hint_card')` 写效果逻辑（应在 config + engine/service） |
| 购买前 `walletService` 校验余额 | 组件内直接改背包数组并写 LS |

---

## 16. 对局记录规范

### 16.1 写入时机

- **开局 / 结算** 由游戏页通过 **`createGameSession` 返回的 `session`** 编排（实现位于 `gameSessionService.js`）。
- 产生 `pendingEvents` 时由 Repository 入队，Service 在合适时机同步。

### 16.2 字段

- 必须含 `gameCode`、`mode`、`difficultyCode`（若有）、`score`、`result`、`startedAt` / `endedAt` 等（见 `matchMapper`）。

### 16.3 允许 / 禁止

| 允许 | 禁止 |
|------|------|
| `historyRepository.refreshMatches(serverId, gameCode)` | 页面直接 `writeMatchRecords` |
| 结算后刷新历史列表 | 每条操作都 sync 一次（应批量/防抖） |

---

## 17. 动画规范

### 17.1 分工

| 层 | 职责 |
|----|------|
| Engine | 产出 `animationSteps` |
| Page / composable | `playAnimationSteps(steps)`：映射为 CSS class、transform、过渡时间 |
| Board 组件 | 根据 step 类型播放格子级动画 |

### 17.2 实现要点

- 使用 `async/await` 或 Promise 链 **串行** 播放步骤，避免并发冲突。
- 时长、缓动函数放在 **一处**（Page 或 `useXxxAnimation.js`）。
- 无效交换：Engine 返回 `swap` + 回弹步骤；Page 负责播放两次。

### 17.3 允许 / 禁止

| 允许 | 禁止 |
|------|------|
| `requestAnimationFrame` 在 Page/composable | Engine 内 `setTimeout` 驱动逻辑 |
| CSS `transition` / `animation` | 多个组件各自 `setTimeout` 硬编码 300ms 且无统一队列 |
| 跳过动画的用户设置（加速） | Engine 内改 DOM class |

---

## 18. 配置化规范

### 18.1 统一来源（优先级从高到低）

1. 服务端 game config（在线且加载成功）
2. `GAME_SEED_CONFIG`（`src/constants/gameSeedConfig.js`）
3. 游戏本地 `{game}Config.js` 的默认值解析

### 18.2 禁止硬编码（页面 / 组件）

| 禁止硬编码项 | 应来自 |
|--------------|--------|
| `rows` / `cols` / `mines` | difficulty.config |
| `itemTypes` / 元素列表 | `config.items[]` |
| `propRules` | 种子或服务端 |
| `rewardRate` / `winReward` | difficulty 或 mode config |
| 排行榜 limit、mode | 常量或 registry |

### 18.3 元素配置形状

```js
{
  itemCode: 'ruby',
  color: '#e74c3c',   // 允许
  icon: '💎'          // 允许为空字符串；后续可换图片 URL
}
```

| 允许 | 禁止 |
|------|------|
| 根据 `item.icon` 显示 emoji 或 `<img :src="item.icon">` | 页面写死「六种纯色块」且无 itemCode |
| `match3Config.resolveItems(config)` | 在 template 写 `background: red` 对应类型 0 |

---

## 19. 文件体积规范

| 类型 | 建议行数 | 超限处理 |
|------|----------|----------|
| Vue 单文件 | ≤ 400 | 拆子组件 + composable |
| Engine | ≤ 600 | 按阶段拆文件（collapse、match、props） |
| Service | ≤ 300 | 拆子函数或领域 service |
| Repository | ≤ 250 | 按实体拆 repo |
| 单组件职责 | — | 不得同时管 UI + 动画 + 业务 + 同步 |

---

## 20. 命名规范

### 20.1 文件

| 类型 | 模式 | 示例 |
|------|------|------|
| 页面 | `XxxPage.vue` | `Match3Page.vue` |
| 弹窗 | `XxxModal.vue` | `MinesweeperResultModal.vue` |
| 面板 | `XxxPanel.vue` | `Match3BattlePanel.vue` |
| Repository | `xxxRepository.js` | `rankingRepository.js` |
| Service | `xxxService.js` | `gameSessionService.js` |
| Store | `useXxxStore.js` | `useRankingStore.js` |
| Engine | `xxxEngine.js` | `match3Engine.js` |
| Config | `xxxConfig.js` | `minesweeperConfig.js` |
| Mapper | `xxxMapper.js` | `rankingMapper.js` |
| Composable | `useXxx.js` | `useMatch3Animation.js` |

### 20.2 符号

| 种类 | 风格 |
|------|------|
| 变量、函数 | camelCase |
| 组件名（SFC name） | PascalCase |
| 常量对象 | UPPER_SNAKE 或 PascalCase 导出（与现有 `GAME_SEED_CONFIG` 一致） |
| gameCode / difficultyCode | 稳定业务编码字符串（如 `'minesweeper'`、`'easy'`），与种子/路由/目录约定一致；**非** JSON 中的 snake_case 字段名 |
| Pinia store id | camelCase：`'ranking'` |

### 20.3 游戏代码

- `gameCode` 与目录名一致：`match3` → `src/games/match3/`。
- 禁止 `MineSweeper`、`match_3` 混用。

---

## 21. 禁止事项

### 21.1 跨层与数据

1. 页面直接 `fetch`。
2. 页面直接 `localStorage`。
3. 页面直接操作 sync queue（`pendingEvents` 的增删改）。
4. Store 调 API。
5. Repository `toast`。
6. API 写 store 或 cache。

### 21.2 游戏与算法

7. Engine 操作 DOM。
8. Engine 请求接口。
9. Engine 使用 Vue 响应式。
10. 页面写复杂棋盘算法。
11. 写死 `minesweeper` 特判扩散到全平台（应收敛 registry/lifecycle）。
12. 多处重复拷贝同一份 `GAME_SEED_CONFIG` 片段。
13. 新游戏复制旧游戏大量代码不抽公共（应抽 `gameLifecycleService`、通用 Panel）。

### 21.3 动画与性能

14. 大量 `setTimeout` 分散在多个组件且无统一队列。
15. 未进入游戏就拉排行榜。
16. 一次请求所有排行榜 / 所有 difficulty。

### 21.4 配置

17. 页面硬编码 rows、itemTypes、propRules、rewardRate。
18. 元素 UI 与 itemCode 脱钩的「纯色块」。

### 21.5 Cursor / 协作

19. 无关大规模 rename 或目录移动。
20. 「顺手」格式化整个仓库或无关文件。

---

## 22. Cursor 执行规则

### 22.1 默认遵循

后续所有前端 Cursor 任务 **默认** 以本文档为准：

`docs/code-style/frontend-code-style.md`

除非用户 prompt 写明例外（例如「本次允许 Page 临时 fetch」）。

### 22.2 修改代码时

| 规则 | 说明 |
|------|------|
| 最小修改 | 只改完成任务所需的文件与行 |
| 禁止无关重构 | 不顺手改命名、不顺手「优化」邻文件 |
| 禁止大规模 rename | 除非任务明确要求 |
| 禁止随意移动目录 | 避免破坏 import 与路由 |
| 确认职责边界 | 改前判断：该逻辑属于哪一层？ |
| 禁止跨层调用 | Page → Repository、Store → API 等 |
| 禁止单游戏污染平台 | 特判应收敛到 registry / config |

### 22.3 生成顺序建议

1. 读 `GAME_REGISTRY` + `GAME_SEED_CONFIG` + 现有同类游戏。
2. 先 Engine / Config（纯逻辑）。
3. 再 Repository / Service（若涉及持久化或榜）。
4. 最后 Page / 组件 / 动画。

### 22.4 注释与文档

- 公共函数使用 JSDoc：`@param`、`@returns`。
- 非显而易见的业务规则（如 sync 版本合并）才写注释。
- **不** 为遵守本规范而重复注释「禁止 fetch」类废话。

### 22.5 完成后自检

- [ ] 是否违反 [§21](#21-禁止事项) 任一条？
- [ ] Vue / Engine / Service 行数是否超限？
- [ ] 配置是否来自种子或服务端？
- [ ] 排行榜是否带齐 `gameCode + mode + difficultyCode`？
- [ ] 动画是否仅在 Page/composable？

---

## 23. 游戏页面统一布局规范

### 23.1 强制结构

所有游戏主页面 **必须** 使用 `GamePlayLayout`（`src/components/game/GamePlayLayout.vue`），左右分栏：

| 左侧 `game-layout__side` | 右侧 `game-layout__main` |
|--------------------------|---------------------------|
| `GameConfigPanel` — 难度 / 模式 / 开局配置 | `GameHudPanel` — 当前对局信息（分数、时间、步数、状态、局内道具配额） |
| `GameShopPanel` — 道具商城 | `game-board-area` — 棋盘 / 对战区 |
| `GameRankingPanel` — 排行榜 | `GameInventoryPanel` — 背包 |

结构示意：

```
GamePlayLayout
  left:
    GameConfigPanel
    GameShopPanel
    GameRankingPanel
  right:
    GameHudPanel
    GameBoardArea（slot: board）
    GameInventoryPanel
```

### 23.2 样式

统一使用 `src/assets/game-layout.css` 中的 class：

- `game-layout`、`game-layout__side`、`game-layout__main`
- `game-card`、`game-card__title`、`game-card__body`
- `game-empty`

**禁止** 各游戏单独实现与 `GamePlayLayout` 左右分栏不一致的独立大厅布局。

### 23.3 页面职责

游戏 `{Game}Page.vue` **只负责**：

- 游戏编排（开局、结算、模式切换）
- 动画播放与棋盘交互
- 调用 `service`（`createGameSession`、`purchaseService` 等）；**不在 `{Game}Page` 直调** `rankingService`

**不允许** 在页面内：直接 `fetch`、直接 `localStorage`、直接操作 sync 队列、自行拼接商城商品列表。

---

## 24. 游戏公共组件规范

目录：`src/components/game/`

| 组件 | 职责 |
|------|------|
| `GamePlayLayout.vue` | 仅布局与 slots；不 import 具体游戏；不调 service |
| `GameConfigPanel.vue` | 配置区外壳；具体内容由 slot 注入 |
| `GameShopPanel.vue` | 统一商城 UI；商品来自 `shopStore`（由 `shopService` 根据 `propRules` + 定义合并写入） |
| `GameRankingPanel.vue` | 统一排行榜 UI；仅当前 `gameCode + mode + difficultyCode` |
| `GameHudPanel.vue` | HUD 外壳；统计与状态由 slot / 子组件注入 |
| `GameInventoryPanel.vue` | 背包展示；数量来自 `inventoryStore` 流水聚合；使用 emit `use-prop` |

### 24.1 GameShopPanel

- **props**：`gameCode`、`disabled`、`sessionId`（可选）
- **事件**：`purchased`
- **购买**：`purchaseService.buyProp`
- **无** `minesweeper` / `match3` 分支

### 24.2 GameInventoryPanel

- **props**：`gameCode`、`usableProps`、`readonly`、`activeProp`、`disabledProps`、`useLabels`
- **事件**：`use-prop`
- **数量**：`inventoryStore` + `aggregateQuantitiesByGame`（`src/utils/inventoryQuantity.js`）
- 道具效果由页面或游戏 service 处理

### 24.3 GameRankingPanel

- **props**：`gameCode`、`mode`、`difficultyCode`、`limit`、`subtitle`
- **刷新**：仅在本组件内：`onMounted` / `watch` props 时拉取当前维度榜。**`GameRankingPanel` 是游戏页内排行榜 HTTP 的唯一入口**；游戏页不要在生命周期里重复请求。
- **展示**：`rankingStore.listForDifficulty`
- 离线不请求；无 `leaderboard` capability 时显示「暂无排行榜」

### 24.4 游戏内组件边界

- 商城 / 排行榜 / 背包 UI **使用** 平台 `GameShopPanel`、`GameRankingPanel`、`GameInventoryPanel`。  
- 游戏专用展示放在 `games/{gameCode}/components/`，**不得** 复制上述平台组件另起一套同名职责。

---

## 25. 游戏页面数据流规范

```
商城：GAME_SEED_CONFIG / 服务端 propRules
        → shopService.loadGameShop
        → shopStore
        → GameShopPanel
        → purchaseService

背包：inventoryStore（流水）
        → GameInventoryPanel（只读展示）
        → Page @use-prop → `session`（`createGameSession`）/ 游戏逻辑

排行榜：`GameRankingPanel`（props 驱动）
        → rankingService（仅组件内）
        → rankingStore
        → GameRankingPanel

游戏逻辑：Page → service → repository → api / local cache
```

---

## 26. 游戏页面禁止事项

1. 每个游戏各写一套商城 / 背包 / 排行榜 UI。
2. 公共组件内 `if (gameCode === 'minesweeper')` 等游戏特判。
3. 页面初始化时一次加载**所有**难度排行榜。
4. 页面直接拼商品列表或写死 propCode。
5. 页面直接 `inventoryStore` 写入或改流水。
6. 页面直接请求 ranking / shop API。
7. `GameShopPanel` 直接请求 API 或操作 `localStorage`。
8. `GamePlayLayout` import 具体游戏或调用 service。

---

## 附录 A：推荐 import 顺序

```js
// 1. vue / vue-router / pinia
// 2. @/stores
// 3. @/services
// 4. @/repositories  — 仅 service 层
// 5. @/games/.../engine、config
// 6. @/components
// 7. @/utils、@/constants
```

## 附录 B：与后端边界

- 前端 **不** 实现权威计分与防作弊；以服务端结算为准（在线模式）。
- 前端 Repository 负责乐观 UI 与离线队列，服务端负责最终一致性。

## 附录 C：文档维护

- 架构变更时 **同步更新** 本文档对应章节。
- 新增平台 Service / Store 时更新 §9、§10 一览表。

---

*文档版本：2.0 · 路径 `docs/code-style/frontend-code-style.md`*
