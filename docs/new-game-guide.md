# 新游戏接入指南

目标：**按模板在 `games/` 下新增模块，不修改平台公共组件的业务分支**。

参考已接入游戏：`minesweeper`、`match3`、`2048`（均已接入 `light-single` 页面模板与底层 `controls` / `stats` 组件）。

---

## 1. 接入清单

### 1.1 前端

| 步骤 | 位置 | 说明 |
|------|------|------|
| 1 | `src/games/your-game/` | 创建游戏目录 |
| 2 | `constants/gameRegistry.js` | 注册 `code`、`modes`、`capabilities` |
| 3 | `constants/gameSeedConfig.js` | 种子：difficulties、propRules、items 等 |
| 4 | `router/index.js` | 路由指向 `YourGamePage.vue` |
| 5 | `YourGamePage.vue` | 轻量单人优先 `LightSingleGameLayout`；其它结构用 `GamePlayLayout` + 平台 `Game*Panel` |
| 6 | `yourGameConfig.js` | 解析/合并配置 |
| 7 | `yourGameEngine.js` | 纯算法 |
| 8 | `components/YourGameHud.vue` 等 | HUD、棋盘、弹窗 |
| 9 | `gameLifecycleService.activateGame` | `onMounted` 与模式/难度变化后按需调用（`mode`、`difficultyCode`、`includeInventory`）；排行榜仅由布局中的 `GameRankingPanel` 负责展示与请求（见第 4 节） |
| 10 | `createGameSession`（`gameSessionService.js`） | `sessionId`、结算、钱包/背包流水、对局与成绩入队、同步刷新 |
| 11 | 可选 `useYourGameSession.js` | 仅封装本游戏 UI/动画状态；**不得**虚构 `startMatch`/`settleMatch` 等模块级 API |

### 1.2 后端

| 步骤 | 说明 |
|------|------|
| 1 | 在 `constants/gameSeedConfig.js` 的 `GAME_SEED_CONFIG` 中增加 `games[]` 项（`gameCode`、`config`、`difficulties`、`propRules`） |
| 2 | `props[]` 中增加本游戏道具定义 |
| 3 | `config.ranking.modes` 为每个上榜 `mode` 配置 `primaryMetric`、`orderDirection`、`tieBreakers`（服务端强校验） |
| 4 | 在 `game-hub` 目录执行 `npm run export:seed`，生成与 `GAME_SEED_CONFIG` 一致的 `dist/game-seed.json`（可选，便于 curl 导入） |
| 5 | `POST /admin/config/import-game-seed` 导入（运维/开发环境；新库必须执行） |
| 6 | 同步 payload：`eventType: "match_record"` 的字段符合 [api.md §1.9](api.md#19-对局记录业务字段match_record) |

无需为单个游戏新增后端 module；配置驱动。

---

## 2. 推荐目录结构

```
src/games/your-game/
├── YourGamePage.vue          # 路由入口：布局、编排、动画
├── yourGameConfig.js         # 从种子/服务端解析 rows、道具、奖励等
├── yourGameEngine.js         # 纯函数：棋盘逻辑、animationSteps
├── yourGame.css              # 可选：scoped 样式补充
├── composables/
│   └── useYourGameSession.js # 可选：仅本游戏 UI/动画状态
└── components/
    ├── YourGameBoard.vue     # 棋盘交互（棋盘旁可放 chainHint 等专用提示）
```

### 文件职责

| 文件 | 职责 |
|------|------|
| `YourGamePage.vue` | 组装 `LightSingleGameLayout`；计算 `controlFields` / `actionItems` / `matchStats` / `matchQuotas`；调用 service；播放动画；**不** fetch / localStorage |
| `yourGameEngine.js` | 规则与 `animationSteps`；**不** Vue、DOM、网络 |
| `yourGameConfig.js` | `resolveXxx(config)` 合并服务端与 `GAME_SEED_CONFIG` |
| `useYourGameSession.js`（可选） | 棋盘/动画相关 `ref`/`computed`；结算仍由 Page 调用 `session.settleWin` 等 |

---

## 3. 游戏页布局

### 3.1 轻量单人可选模板 `light-single`

**适用**：扫雷、消消乐、2048、数独、记忆翻牌等简单单人游戏（棋盘/HUD 不复杂）。

**不适用**：五子棋在线对战、飞行棋多人在线、飞机大战、PixiJS/Canvas 重渲染、需要非常规页面结构的游戏。

**目录**：`src/game-templates/light-single/`

| 组件 | 职责 |
|------|------|
| `LightSingleGameLayout` | 左右分栏；props/slots/`@action`（模板层，不含业务） |
| `LightSingleGameSidePanel` | 左侧容器；内部使用 `GameControlPanel`（含 `GameActionBar` 操作区，`components/game/controls/`） |
| `LightSingleGameBoardFrame` | 右侧棋盘**外层视觉容器**（slot 放入具体棋盘；可承载 `GamePauseOverlay`） |
| `GamePauseOverlay` | `components/game/panels/` — 对局区暂停遮罩（纯展示，`emit('resume')`） |

**底层组件（模板内复用，页面也可直接用）**

| 组件 | 目录 | 职责 |
|------|------|------|
| `GameControlPanel` | `controls/` | 游戏信息 + 配置 fields + 操作 actions；只展示与 emit |
| `GameMatchStatsPanel` | `stats/` | 对局统计区；传入 `stats`/`quotas` 数组即可 |
| `GameShopPanel` 等 | `panels/` | 商城 / 榜 / 背包（与 `GamePlayLayout` 相同） |

**统一 import**：从 `@/components/game`（或 `src/components/game/index.js`）引入组件与枚举：

```js
import {
  GameShopPanel,
  GameRankingPanel,
  GameInventoryPanel,
  GameResultModal,
  GameMatchStatsPanel,
  GAME_ACTION_TYPE,
  GAME_ACTION_SIZE,
  GAME_CONTROL_TYPE,
  GAME_STAT_TONE
} from '../../components/game/index.js';
```

**Registry（仅前端，不进 seed）**：

```js
// constants/gameRegistry.js
yourGame: {
  code: 'your_game',
  viewTemplate: 'light-single', // 可选；未配置则页面自选布局
  // ...
}
```

**为何不进 seed**：seed 是业务数据（难度、道具、排行榜规则）；页面模板是前端渲染策略，与后端无关。

**为何不是平台强制规范**：命名刻意使用 `light-single` / `LightSingleGame*`，避免 `GameTemplate`、`Universal*` 等暗示「所有游戏必须用」。特殊游戏可完全自定义 `YourGamePage.vue`。

**布局结构**：

```
左侧：游戏信息 + actionItems + GameShopPanel + GameRankingPanel
右侧：对局信息(match-stats) + LightSingleGameBoardFrame(board) + GameInventoryPanel
```

**轻量单人推荐组合**：`LightSingleGameLayout` + 左侧 `GameControlPanel`（经模板 `controlFields` / `actionItems`）+ 右侧 `GameMatchStatsPanel`（`match-stats` slot）。业务页负责把本局状态适配为 `fields` / `actions` / `stats` / `quotas`，底层组件不写 `gameCode` 分支。

**接入示例（扫雷 / 2048 / match3 参考 `MinesweeperPage.vue`、`Game2048Page.vue`、`Match3Page.vue`）**：

```vue
<template>
  <LightSingleGameLayout
    :game-title="registry.name"
    :game-subtitle="registry.subName"
    :game-description="'经典模式 · 标准难度'"
    :game-status-text="statusText"
    :control-fields="controlFields"
    :action-items="actionItems"
    :game-code="gameCode"
    :mode="mode"
    :difficulty-code="difficultyCode"
    board-title="对局信息"
    board-frame-title="对局区域"
    board-subtitle="操作提示文案"
    @field-change="onControlFieldChange"
    @action="onLayoutAction"
  >
    <template #shop>
      <GameShopPanel :game-code="gameCode" :session-id="matchSessionId" />
    </template>
    <template #ranking>
      <GameRankingPanel :game-code="gameCode" :mode="mode" :difficulty-code="difficultyCode" />
    </template>
    <template #match-stats>
      <GameMatchStatsPanel :stats="matchStats" :quotas="matchQuotas" :message="hudMessage" theme-seed="your_game" />
    </template>
    <template #board>
      <YourGameBoard @action="onBoard" />
    </template>
    <template #inventory>
      <GameInventoryPanel :game-code="gameCode" @use-prop="onUseProp" />
    </template>
  </LightSingleGameLayout>
</template>
```

**`controlFields` 与 `@field-change`**：模式、难度等由 Page 计算 `controlFields`（`type` 用 `GAME_CONTROL_TYPE`），经 `LightSingleGameLayout` → `GameControlPanel` 渲染；`@field-change` 在 Page 的 `handleControlChange` 内更新（如 match3 模式 radio、扫雷难度 `select`）。

扫雷示例：`controlFields` 仅一项难度下拉；`actionItems` 按对局状态展示 `pause` / `resume` / `restart` / `playAgain` / `safeStart` / `end`（**不**使用 `pauseOrResume` 混合 key）；积分规则说明放在 `#game-info-extra` slot，不占平台组件特判。

**`actionItems` 与 `@action`**：Page 用 computed 组装 `actionItems`（`GAME_ACTION_TYPE` / `GAME_ACTION_SIZE`），含 `key` / `label` / `type` / `size` / `visible` / `disabled`；模板只 `emit('action', key)`，业务在 Page 的 `handleControlAction` 内分支处理。

**轻量单人操作按钮（2048 / match3 / 扫雷 已统一）**

| 对局状态 | 展示按钮 |
|----------|----------|
| `idle` 未开始 | 无开始/暂停/继续/结束/重新开始（**首次有效棋盘操作**自动开局并计时） |
| `playing` 进行中 | `pause` 暂停、`restart` 重新开始、`end` 结束对局 |
| 已暂停（`playing` + `isPaused`） | `resume` 继续、`restart`、`end`（**不**显示 `pause`） |
| `ended` 已结束 | `playAgain` 再来一局（`PRIMARY`） |
| `settling` 结算中（如 2048） | 保留上一态可见按钮，全部 `disabled` |

- **不要**在 idle 放「开始游戏」：刷新后用户直接操作棋盘更自然。
- **ended** 用「再来一局」而非「开始游戏」/「重新开始」。
- 暂停/继续使用独立 key 与 `GAME_ACTION_TYPE.PAUSE` / `RESUME`（蓝紫 / 青绿），**不要**用 `WARNING`。
- 进行中「重新开始」用 `SECONDARY`；「结束对局」用 `DANGER`。
- 扫雷 `safeStart` 仍按原规则（通常 idle / ended 且未用过安全开局时展示），不受 idle 无开始按钮影响。

**暂停遮罩（推荐）**

- 业务页维护 `const isPaused = ref(false)`，实现 `pauseGame()` / `resumeGame()`；暂停期间停止计时（interval 内判断 `!isPaused` 或暂停时 `stopTimer`），`durationMs` 不含暂停时长。
- `LightSingleGameLayout` 传入 `:paused="isPaused"`、`@resume="resumeGame"`，由 `LightSingleGameBoardFrame` 在棋盘 slot 上叠加 `GamePauseOverlay`。
- `GamePauseOverlay` 只负责展示与 `emit('resume')`；不写 `gameCode` 分支、不调 API/store、不改 `gameStatus`。
- 恢复途径：左侧「继续游戏」按钮（`resume`）或点击遮罩空白/继续按钮；暂停时禁止棋盘操作与道具，**允许**主动结束对局（`end`）。

**浏览器切页自动暂停（推荐）**

- 使用 `src/composables/usePageVisibilityPause.js`：`document.hidden === true` 时按 `shouldPause()` 决定是否调用业务页传入的 `pause()`（通常为 `pauseGame()`）。
- Composable **仅**监听隐藏并触发暂停，**不**在标签页重新可见时调用 `resume`；**不**改 `gameStatus`、**不**处理计时、**不** import 具体游戏。
- 继续对局只能由用户主动点击左侧「继续游戏」或棋盘 `GamePauseOverlay`（`@resume` → `resumeGame()`）。
- 业务页负责：`isPaused`、`pauseGame` / `resumeGame`、计时 interval 内判断 `!isPaused`（或暂停时 `stopTimer`）。
- `shouldPause` 示例：对局 `playing` 且未暂停；match3 等还需排除动画/结算中（`canPauseGame`），避免切页时强行打断棋盘动画。

```js
import { usePageVisibilityPause } from '../../composables/usePageVisibilityPause.js';

usePageVisibilityPause({
  shouldPause: () => gameStatus.value === 'playing' && !isPaused.value,
  pause: pauseGame
});
```

**对局数据 `match-stats`**：在 slot 内使用 `GameMatchStatsPanel`；Page 传入 `matchStats`（含 `GAME_STAT_TONE`）与 `matchQuotas`。勿在平台 `GameMatchStatsPanel` 内写游戏分支；游戏专用 HUD 仅保留棋盘旁提示等非通用 UI。

**数据适配**：`controlFields`、`actionItems`、`matchStats`、`matchQuotas`、`gameStatusText` 均由 Page 从本局 `ref`/`computed` 映射；**模板层与 `controls/`/`stats/` 组件均不写游戏特判**。

**slots**：`left-extra`、`game-info-extra`、`shop`、`ranking`、`match-stats`、`board`、`inventory`、`right-extra`。

**对局外框**：`LightSingleGameBoardFrame` 与上下 `game-card` 统一圆角/边框/背景，解决棋盘区与 HUD、背包视觉割裂；内部棋盘样式仍由游戏 CSS 控制。`props`：`paused`、`pauseTitle`、`pauseDescription`、`pauseActionText`（后三项可省略，使用 `GamePauseOverlay` 默认文案）；`emit`：`resume`。

```vue
<LightSingleGameLayout
  :paused="isPaused"
  @resume="resumeGame"
  ...
>
```

**新游戏建议**：轻量单人优先 `light-single`；模式切换/复活/复杂配置留在 `game-info-extra` 或继续用 `GamePlayLayout`。

---

### 3.2 GamePlayLayout 用法

```vue
<template>
  <GamePlayLayout>
    <template #config>
      <GameConfigPanel>
        <YourGameBattlePanel v-model:difficulty="difficultyCode" v-model:mode="mode" />
      </GameConfigPanel>
    </template>
    <template #shop>
      <GameShopPanel :game-code="gameCode" :session-id="matchSessionId" @purchased="onPurchased" />
    </template>
    <template #ranking>
      <GameRankingPanel
        :game-code="gameCode"
        :mode="mode"
        :difficulty-code="difficultyCode"
        value-metric="score"
        :subtitle="rankingSubtitle"
      />
    </template>
    <template #hud>
      <GameHudPanel>
        <YourGameHud :stats="hudStats" />
      </GameHudPanel>
    </template>
    <template #board>
      <YourGameBoard @action="onBoardAction" />
    </template>
    <template #inventory>
      <GameInventoryPanel
        :game-code="gameCode"
        :usable-props="usableProps"
        @use-prop="onUseProp"
      />
    </template>
  </GamePlayLayout>
</template>
```

- `GameRankingPanel` 的 `value-metric` 为 `'score'` 或 `'durationMs'`（扫雷等按用时展示用后者）。
- 样式：`import '@/assets/game-layout.css'`。

---

## 4. 排行榜接入

1. `GAME_REGISTRY` 中 `capabilities.leaderboard: true`  
2. 后端 `config.ranking.modes[yourMode]` 配置 `primaryMetric`、`orderDirection`、`tieBreakers`（见 [api.md §11.1](api.md#111-查询排行榜)）  
3. **游戏页只维护** `mode`、`difficultyCode`（及常量 `gameCode`），通过模板把三者传入布局中的 **`GameRankingPanel`**。该组件在挂载与 props 变化时自行完成排行榜 HTTP 请求与 store 写入；游戏页 **不要** 在生命周期或难度切换里再直调 ranking 层 API。  
4. 进入游戏页时在 `onMounted` 调用 `activateGame` 加载配置 / 商城 / 背包（与当前 `match3`、`minesweeper` 一致），示例：

```js
import { activateGame } from '@/services/gameLifecycleService.js';

await activateGame(gameCode, {
  mode,
  difficultyCode,
  includeInventory: true
});
```

5. **切换玩法 `mode` 后**：再次 `activateGame(...)`（传入新 `mode`），与 `match3` 的 `changeMode` 一致；榜单随 `GameRankingPanel` 的 `mode` prop 更新。  
6. **仅切换难度**：更新 `difficultyCode` 即可；`GameRankingPanel` 会随 props 刷新当前难度榜。  
7. **禁止** 一次请求所有难度或所有游戏的榜。

> 胜利结算后，`session.settleWin` 会通过 `syncService.refreshRemoteAfterSettle({ includeRanking: true })` 在结算链路中刷新远端榜数据，属于 **session/sync 编排**；侧栏展示仍以 `GameRankingPanel` 的 props 为准。

---

## 5. 道具接入

1. 种子 / 服务端：`propRules`（`propCode`、`sortNo`、`price`、`maxUsePerMatch`、`effectType`、`rule` 等；`sortNo` 必填并写入 `game_prop_rule.sort_no`）  
2. `GameShopPanel` + `purchaseService.buyProp` 负责购买  
3. `GameInventoryPanel` 只展示数量；`@use-prop` 在 Page 中处理；局内使用通过 `session.trackPropUsage` / `session.recordInventoryUse` 记入本局与背包流水  
4. 局内明细收集为数组，结算时作为 `propUses` 传入 `session.settleWin` / `settleFail` / `settleEnd`，随 `match_record` 入队同步  

---

## 6. Session 与结算（`createGameSession`）

平台提供工厂函数 **`createGameSession`**，返回本游戏页内复用的 **`session` 对象**（不存在 `gameSessionService.startMatch` / `settleMatch` 等模块级函数）。

```js
import { createGameSession } from '@/services/gameSessionService.js';

const session = createGameSession({ gameCode: 'your_game' });
```

### 6.1 开局与 `sessionId`

- 对局开始时：`matchSessionId.value = session.newMatchSessionId()`（与 `match3`、`minesweeper` 一致）。  
- 局内道具使用：`session.trackPropUsage(currentMatchPropUses, { propCode, label, timerSec, sessionId })`，同时写入背包使用流水。

### 6.2 结算（内部会 `appendMatchRecord`、`flushPendingIfOnline`、`refreshRemoteAfterSettle`）

| 方法 | 场景 | 排行榜 |
|------|------|--------|
| `await session.settleWin({ score, rewardScore?, difficultyCode, durationMs, propUses, sessionId, mode, matchPayload?, scorePayload? })` | 胜利并上成绩榜 | 结算链 `refreshRemoteAfterSettle` 可能刷新远端榜；非游戏页生命周期内拉榜 |
| `await session.settleFail({ score, difficultyCode, durationMs, propUses, sessionId, mode })` | 失败 | 不刷新榜 |
| `await session.settleEnd({ score, difficultyCode, durationMs, propUses, sessionId, mode, payload? })` | 主动结束等 | 不刷新榜 |

- `difficultyCode`：当前实现下写入对局为**必填**非空字符串；无难度概念的游戏请使用种子中的默认难度编码。  
- `durationMs`：毫秒。  
- `propUses`：数组，无使用传 `[]`。  
- 对局 `result` 与上表对应为 **`win` / `fail` / `end`**（与现有前端及同步 payload 一致）。

### 6.3 其它

- `session.ledgerGain` / `session.ledgerCost`、`session.persistLocal` 按需使用。  
- `session.setAutoRevive` 仅扫雷使用；新游戏若无该设置可忽略。

---

## 7. Mode / Difficulty 接入

| 概念 | 前端 | 后端 |
|------|------|------|
| `mode` | `GAME_REGISTRY.modes`、用户可选 | `match_record.mode`、排行榜 Query、`ranking.modes[mode]` |
| `difficultyCode` | `gameSeedConfig` / `GET .../config` 的 `difficulties[]` | 对局与榜过滤；写入对局时与前端 `createGameSession` 校验一致 |

切换难度：更新选中值 → 由 `GameRankingPanel` 随 props 自动拉榜 → 按需重载本游戏 config。

---

## 8. 允许修改的范围

| 允许 | 位置 |
|------|------|
| 新增 `src/games/your-game/**` | 游戏专用 |
| 扩展 `GAME_REGISTRY`（含可选 `viewTemplate`）、`GAME_SEED_CONFIG` | 常量 |
| 注册路由 | `router/index.js` |
| 种子 import Body | 运维调用 admin API |
| 游戏内 composable / css | 游戏目录 |

---

## 9. 禁止事项

| 禁止 | 原因 |
|------|------|
| 在 `GameShopPanel` / `GameRankingPanel` 等写 `if (gameCode === 'xxx')` | 平台组件保持通用 |
| 在 `game-hub/src/services` 写死某游戏算法 | 算法归 Engine |
| Page 内 `fetch` / `localStorage` | 走 repository + service |
| Store 内调 API | Store 只存状态 |
| Engine 操作 DOM / 定时器驱动规则 | 动画在 Page |
| 复制其它游戏 Page 达数百行仅改名 | 用 `light-single` 或 `GamePlayLayout` + 小组件 |
| 把 `viewTemplate` 写入 seed | 页面模板仅 `GAME_REGISTRY` |
| 平台层 import 具体游戏 Page | 仅路由动态引用 |

---

## 10. 验收自检

- [ ] `npm run build` 通过  
- [ ] 离线可玩（`repositoryMode: local`）  
- [ ] 在线：购买、背包、排行榜、对局同步正常  
- [ ] 对局 JSON 含 `durationMs`、`propUses[]`、`payload{}`，字段均为 camelCase（见 [api.md](api.md)）  
- [ ] 未修改平台组件的游戏特判  

更多分层细节见 [code-style/frontend-code-style.md](code-style/frontend-code-style.md) 与 [architecture.md](architecture.md)。
