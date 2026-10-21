# 新游戏接入指南

目标：新增游戏时只扩展游戏目录、种子和注册入口，不在公共层加入游戏特判。

## 前端接入

1. 在 `game-hub/src/games/{gameCode}/` 新增游戏目录。
2. 导出 `gameModule.js`，声明 `gameCode`、路由、能力、配置处理器和页面 loader。
3. 在 `src/games/gameModuleRegistry.js` 聚合根注册该模块。
4. 平台业务种子写入 `src/constants/gameSeedConfig.js`。
5. 用户可配置项写入 `src/constants/gameSettingDefinitions.js`，页面通过 service 读取，不直接操作 `localStorage`。
6. 页面不得直接 `fetch`；必须走 service / repository / api 层。
7. Store 只保存状态快照，不调 API。
8. 公共组件、模板和公共 service 不写 `gameCode === 'xxx'` 特判。
9. 在线游戏如需固定房间字段顺序，在 gameModule 声明 `roomConfigFieldOrder`；公共表单只读取 schema.displayOrder，不列举游戏私有字段。

前端注册入口是各游戏 `gameModule.js` 与 `games/gameModuleRegistry.js`。

## 后端接入

轻量单人游戏通常只需要平台种子和前端实现。在线策略回合制游戏需要新增：

| 位置 | 职责 |
| --- | --- |
| `app/modules/game_seed/{gameCode}_seed.py` | 规则种子、房间配置 schema、牌/棋子定义 |
| `app/modules/game_impls/{gameCode}/` | 具体规则实现 |
| `app/game_runtime.py` | 注册 `GameModule` |

`StrategyTurnGameModule` 至少提供：

- `GameLifecycleEngine`：开局、动作应用、阶段推进、终局指令。
- `GameStateProjector`：只投影公共/私有游戏状态、阶段与当前玩家，不生成 actionOffers。
- `interactionBindings`：每个 actionType 显式提供 `ActionInteractionBinding`，声明 `ENUMERATED` / `COMPOSED` 和对应 OfferProvider/Resolver。平台 `ActionInteractionGateway` 统一路由，`GameViewService` 组合状态投影与查看者 actionOffers。

按需提供：

- `CandidateScorer` / selector / fallback：托管和 AI。
- preview provider：只读动作预览。
- hint / suggestion provider：只读候选提示。

在线规则种子加入 `online_game_seed_registry` 的启动期内置集合；重复 gameCode 拒绝，注册映射只读，查询返回独立深副本。游戏自动候选、提示和解析应共用本游戏合法动作目录，不得穿透目录私有成员或维护跨请求可变候选缓存。

## 动作模型

每个 `actionType` 必须明确交互模式：

- `ENUMERATED`：服务端列出 actionId，客户端选择提交。
- `COMPOSED`：客户端按 capability 构造 selection，服务端解析校验。

两者最终都必须解析成 `ResolvedGameAction`。Lifecycle 只执行 `ResolvedGameAction`，不能直接执行客户端 payload。

`requestId` 属于房间命令顶层，不属于 `ActionSubmission`、不属于 `ResolvedGameAction`。客户端重试必须复用同一个 `requestId` 和请求正文。

## Runtime 和提交边界

游戏实现只读写 `RuntimeSnapshot` 语义，不直接操作 Redis key。房间提交由 `RoomGameCommit` 负责：

- 版本检查。
- requestId 幂等。
- 快照写入。
- 事件追加。
- 响应缓存。
- PostTurn Outbox 入队。

不要新增绕过提交边界的状态写入器或大而全的 Room 服务。

## 自动推进和托管

非玩家阶段使用 `RoomAutoAdvanceTask`，例如发牌展示、叫抢地主展示、结算展示和 Finalize。

玩家回合使用 `ManagedTurnTask`，例如 AI、真人托管、超时自动操作。

两者并列，不要用托管任务模拟阶段展示。

## 终局接入

在线游戏终局应输出理论零和结算和 `TerminalDirective`。平台负责钱包实际扣加、余额不足补差、系统补差、GameView 推送和 Finalize。结算失败达到上限也必须收敛回 waiting。

## 前端策略回合页面

页面消费：

- `roomQueryService`：房间查询与版本守卫；`roomService`：创建、成员和配置命令。
- `roomGameService`：开局、对局视图、动作/预览/提示与上下文接纳；`roomRealtimeService`：房间订阅、Presence 和邀请。
- `strategyTurnGameViewService`：权威视图、WebSocket 增量、断层恢复。
- `action-interaction` adapter：把 UI 交互转成 `ActionSubmission`。

页面不直接请求 `/rooms`、不直接请求 `/rule-definition`，不直接读写认证 Token。

页面在路由/模式变化或卸载时取消所属异步上下文；await 后先检查代次，再回写、发下一条命令或导航。重拉与动画取消均须结束调用方等待 Promise。

当前五子棋正式合同为 15×15，悔棋请求默认 30 秒、允许 10–120 秒；早期 10 秒说明不作为当前默认。UNO `FIRST_FINISH` 表示“首位真人完成结束”，AI 首位出完不触发该模式终局。

## 斗地主参考

斗地主可作为复杂牌类参考：叫地主/抢地主、明牌、加倍、癞子、`PLAY_CARDS` 的 `COMPOSED` 交互、候选提示、阶段展示、结算和 Finalize。完整规则见 [doudizhu-rules.md](doudizhu-rules.md)。以当前 `game_impls/doudizhu/` 模块为参考。

## 自检

- `game_impls` 不 import `room`。
- `strategy_turn` 不 import 具体游戏。
- `room` 不 import 具体游戏。
- `core/websocket` 不 import Room/User 业务实现。
- Repository 不 import Store。
- Store 不调 API。
- Page 不直接 `fetch` / `localStorage`。
- 公共层不写 `gameCode` 特判。
- 不新增 `StableFirstFallbackPolicy`、`GameView.legalActions`、`lastActionEvents` 等不符合当前模型的符号或字段。
