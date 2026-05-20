# 新游戏接入指南

目标：**按模板在 `games/` 下新增模块，不修改平台公共组件的业务分支**。

参考已接入游戏：`minesweeper`、`match3`。

---

## 1. 接入清单

### 1.1 前端

| 步骤 | 位置 | 说明 |
|------|------|------|
| 1 | `src/games/your-game/` | 创建游戏目录 |
| 2 | `constants/gameRegistry.js` | 注册 `code`、`modes`、`capabilities` |
| 3 | `constants/gameSeedConfig.js` | 种子：difficulties、propRules、items 等 |
| 4 | `router/index.js` | 路由指向 `YourGamePage.vue` |
| 5 | `YourGamePage.vue` | 使用 `GamePlayLayout` + 平台 `Game*Panel` |
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
    ├── YourGameHud.vue       # 分数、时间、状态（slot 填入 GameHudPanel）
    ├── YourGameBattlePanel.vue  # 难度/模式选择（slot 填入 GameConfigPanel）
    └── YourGameBoard.vue     # 棋盘交互
```

### 文件职责

| 文件 | 职责 |
|------|------|
| `YourGamePage.vue` | 组装 `GamePlayLayout`；调用 service；播放动画；**不** fetch / localStorage |
| `yourGameEngine.js` | 规则与 `animationSteps`；**不** Vue、DOM、网络 |
| `yourGameConfig.js` | `resolveXxx(config)` 合并服务端与 `GAME_SEED_CONFIG` |
| `YourGameHud.vue` | 展示本局统计 |
| `YourGameBattlePanel.vue` | 难度、模式切换 UI |
| `useYourGameSession.js`（可选） | 棋盘/动画相关 `ref`/`computed`；结算仍由 Page 调用 `session.settleWin` 等 |

---

## 3. GamePlayLayout 用法

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

1. 种子 / 服务端：`propRules`（`propCode`、`price`、`maxUsePerMatch`、`effectType`、`rule`）  
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
| 扩展 `GAME_REGISTRY`、`GAME_SEED_CONFIG` | 常量 |
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
| 复制 800 行旧 Page 只改名 | 用 Layout + 小组件 |
| 平台层 import 具体游戏 Page | 仅路由动态引用 |

---

## 10. 验收自检

- [ ] `npm run build` 通过  
- [ ] 离线可玩（`repositoryMode: local`）  
- [ ] 在线：购买、背包、排行榜、对局同步正常  
- [ ] 对局 JSON 含 `durationMs`、`propUses[]`、`payload{}`，字段均为 camelCase（见 [api.md](api.md)）  
- [ ] 未修改平台组件的游戏特判  

更多分层细节见 [code-style/frontend-code-style.md](code-style/frontend-code-style.md) 与 [architecture.md](architecture.md)。
