# 架构说明

本文描述当前运行架构与模块边界。

## 总体边界

前端游戏目录导出 `gameModule.js`，由 `src/games/gameModuleRegistry.js` 聚合。公共组件、模板、Store、Repository 与 Page 不按 `gameCode` 编写具体游戏逻辑。

| 层 | 职责 |
| --- | --- |
| `app/core/auth` | Access Token 的 HTTP 认证与认证上下文。 |
| `app/modules/auth` | Realtime Ticket 签发与消费。 |
| `app/core/websocket` | 传输、连接管理、消息 envelope 和分发。 |
| `app/realtime` | WebSocket 认证适配与实时 Handler 组装。 |
| `app/modules/room` | 房间元数据、RuntimeSnapshot 读写、提交、Presence、任务、Outbox、结算与 Finalize。 |
| `app/modules/strategy_turn` | 通用策略回合运行时、交互解析、自动决策与 GameView 投影。 |
| `app/modules/game_impls/{gameCode}` | 游戏规则、Lifecycle、交互绑定、候选、评分与私有兜底。 |
| `app/modules/game_seed` | 在线规则种子与平台种子导出。 |

## 启动、同步与资产

`BootModuleService` 组合用户、设备、设置和游戏摘要；独立的 `HealthService` 负责探测。`CloudSaveService` 负责逐事件执行、批次审计与响应编排，`CloudSnapshotService` 负责派生资产重建与完整快照读取。请求/响应模型归属对应领域，云同步合同位于 `sync/cloud_save_schemas.py`。排名规则由 `RankingEntityService` 解释，成绩仓储只接收已确定的筛选、排序和候选上限。

同步保留 `receivedCount/successCount/duplicateCount/failCount` 合同。每条事件的事实、派生数据和幂等写入位于同一 SAVEPOINT；SQLite 在首个 SAVEPOINT 前确保真实外层 BEGIN，因此快照或请求后续失败仍整体回滚。前端按用户和发送时的完整事件内容确认：只有全批成功或重复时移除发送集合，部分失败整批保留幂等重试，期间新增或修改的事件不被清除。

新 pending 的 `ownerUserId` 仅为本地归属元数据，不发送到 API。历史事件仅在已有 ownerUserId 或 payload.userId 能证明归属时上传；无归属事件保留，不猜测归属。新离线购买把库存 gain 与购买 clientId 关联；无关联的存量 gain 不能自动推断已确认。`consumeFromBag=false` 的历史事实持久化和迁移尚未实现。

在线购买响应中的钱包余额摘要不能覆盖本地完整钱包事实。购买成功后按发起请求的用户拉取完整流水并合并；刷新失败保留已有事实，并区分购买成功与余额视图刷新失败，不能因此重复购买或伪造服务端流水身份。

钱包流水按用户和 clientId 合并，钱包余额从完整有效流水重建。钱包分页查询必须收齐并核对 total、页长和唯一 ID 后才替换当前用户的云端事实；原有首屏 20 条展示缓存单独保存，不作为持久化事实。异步资产响应捕获请求身份，不能写入 await 后的新用户桶。

## 策略回合执行链

`ENUMERATED` 和 `COMPOSED` 是平级输入模式。`ActionInteractionGateway` 将 `ActionSubmission` 解析成 `ResolvedGameAction`；Runtime 和 `GameLifecycleEngine` 只执行 `ResolvedGameAction`。

```text
ActionSubmission
-> ActionInteractionGateway
-> ResolvedGameAction
-> StrategyTurnRuntimeService
-> GameLifecycleEngine
-> RuntimeSnapshot / DomainEventDraft / TerminalDirective
```

每个 `gameCode + actionType` 必须注册明确的 `ActionInteractionBinding`。游戏模块的 Lifecycle、Interaction、Decision 三条规则链职责平级：Lifecycle 处理状态推进，Interaction 处理 Offer/Resolver，Decision 处理候选评分、选择和游戏私有兜底。

## RuntimeSnapshot、提交与 Outbox

`RuntimeSnapshot` 是对局事实源。GameView、ActionOffer、privateState 和事件展示数据均由快照投影或增量生成。

`RoomGameCommit` 是单次对局变更的原子边界，包含版本校验、RuntimeSnapshot、事件、requestId 幂等记录、响应缓存和 Post-turn Outbox；每条待处理 Outbox 与房间所属分片的 ready-room 索引在同一 Redis Lua 提交中写入。项目采用单体部署和单实例 Redis，不要求 Redis Cluster。房间 ID 稳定映射到固定数量的 hash-tag 逻辑分组，同一房间的 Runtime、版本、成员、Outbox 和 ready 索引使用同一分组；Worker 轮询全部分组。相同 `roomId + playerId + requestId` 以请求内容保证幂等或冲突判定。

Post-turn Outbox 在动作提交成功后异步执行托管动作、阶段自动推进、终局结算、GameView 推送、Finalize 和派生索引清理。领取以房间级分发租约原子转换一条记录状态并同步 ready-room 索引；同一房间同一时刻只由一个 Worker 分发，下一条记录在完成或租约到期恢复后继续处理。恢复流程用于基础设施故障或索引损坏，不参与正常调度，也不重放玩家动作。

托管任务与自动推进任务按 `roomId` 映射到同一固定 Redis 分片。每个任务类型在分片内使用 records Hash、due ZSet、processing ZSet 和房间维度 dedupe 键；入队、领取、重试、终态写入和租约恢复的 Lua 只访问同槽键。后台 Worker 轮询全部分片，房间执行锁确保同一房间的自动化任务串行执行。

`ManagedTurnTask` 用于 AI、托管、shell 与超时玩家回合；`RoomAutoAdvanceTask` 用于无玩家输入的阶段展示和推进。二者独立调度。

两类任务仓储通过 `TaskQueueRepository` 共享六组队列原语，各自声明键空间与去重身份。短重试耗尽后的恢复校验失败消耗同一 taskId 的 recoveryCount，并通过队列退避；达到上限保留 FAILED 和去重记录，不递归调用重试入口。损坏 JSON 或非对象任务移出调度索引，原始记录和去重身份保留供核查。

Outbox 的外层读取统一使用受保护 Lua 解析。损坏记录隔离为带原文的 `CORRUPT_RECORD/FAILED` 审计，同时清 due、比较释放自身 dispatch lease 并刷新 ready 索引；不会重放领域动作。坏房间领取失败不阻断其他房间。

结算由 `GameSettlementTransaction` 拥有数据库事务、settlementId 幂等、钱包与历史事实写入，`GameSettlementCommitService` 拥有 Runtime 元数据、CAS 和 Finalize Outbox；`GameSettlementService` 校验合同并按数据库 → Redis → 展示顺序编排。展示失败不撤销已经提交的结算。

Finalize 的后续清理携带最终 CAS 的 `terminalRoomVersion`，与开局共用房间锁；清理 Lua 原子核对当前房间仍为 waiting 且 roomVersion 相等，再删除 playing 索引。仍在等待房间内的真人非 shell 成员保留活跃占用；被移除成员和 shell 的派生索引仅在 owner 仍指向该房间时删除。新局或新房间版本使旧清理过期。无法证明代际的清理载荷进入失败审计。

## 房间成员归属

房间 meta 与成员 Hash 是成员事实，player-room 与 managed-shell 是派生归属索引。`room_membership_index_lua.py` 统一分类、归属变更和续期；`RoomRepository.get_active_membership` 为跨游戏当前房间查询、创建、加入、恢复席位和邀请中的同房检查提供同一事实读取。Lua 在同一次读取中核对玩家索引、房间 meta、成员和 roomVersion；索引在读取期间切换时有限重试。已失效索引仅比较归属后清理，损坏事实显式报错。未知或缺失的 gameCode 不会使真人非 shell 的真实占用失效，终局展示和结算中的 playing 房间仍受占用限制。

`RoomMutationCommit` 在单实例 Redis 中将创建、加入、恢复的成员写入与玩家占用认领原子提交，冲突不写入房间。它与 `RoomGameCommit` 共用成员索引变更逻辑：shell 转换、恢复和成员移除随事实一起提交，仅释放自身归属，不再由应用服务提前或事后补写索引。按游戏的房间列表索引与房间提交同步维护。列表中的成员清理与其他房间操作共用房间锁。启动重建由同一 Lua 分类输出候选，Python 只聚合候选和处理唯一性；已有有效 owner 保留，缺失且只有唯一候选时恢复，多个真实候选只记录歧义。请求链不扫描全部房间。

普通房间续期及 `RoomMutationCommit`、`RoomGameCommit`、`Finalize` 原子提交共用已有归属的续期逻辑，期限不超过房间 meta 与成员事实；续期不调用重建，不补缺失 owner，也不覆盖另一房间。`room_membership_index_bindings.py` 只负责显式 RedisKeys 绑定与成员集合预读；Lua 在写入前再次核对集合，新增未绑定成员或版本冲突时不写数据和 TTL。普通续期遇到预绑定变化有限重试。shell 仅在 playing 且 gameCode 非空时具有自己的 shell 索引，不作为 active 占用。共享游戏列表索引的 TTL 不因短期房间加入而缩短。

历史上多个真实房间同时保留同一真人且 owner 缺失时，重建仅记录歧义，不猜选房间或自动踢人。游戏模块已删除时，通用退出的成员变更可以提交，但 playing 房间后续投影或任务仍可能失败；客户端通过权威重查展示实际归属，不能据成员提交推断该游戏的托管或结算可用。

## 前端版本恢复

`strategyTurnGameViewService` 按版本顺序应用实时增量。当 `incomingVersion > highestAcceptedVersion + 1` 时，取消事件展示、丢弃旧展示任务并重新拉取权威 GameView。权威状态立即可交互，展示不锁住输入。连续缺口合并目标版本并共用在途请求，低于目标的完整快照可以应用，但不能提前宣布恢复完成。请求生命周期与展示生命周期独立；reset、切房和重试同时取消网络、timer 与等待 Promise，旧响应不能回写。

房间查询、成员命令、对局请求和实时订阅分别位于 `roomQueryService`、`roomService`、`roomGameService`、`roomRealtimeService`。页面使用可取消上下文管理查询、订阅和后续导航，房间版本与请求代次在写回边界校验。大厅/等待页的弹窗及命令各有实际流程模块，不保留旧服务转发别名。

跨游戏成员归属只保存为 `roomStore.activeRoom` 查询快照，`currentRoom` 仍是浏览或对局详情，不能推断成员资格。`roomQueryService` 是归属快照的唯一写入者，按用户、服务地址和数据模式隔离请求，取消被替代的查询；查询失败保留已知事实并记录错误。查询状态明确区分 `idle/loading/ready/error`，只有 `ready` 的空值表示已确认无归属，旧查询不能回退新状态。`roomService` 在创建、加入、恢复和退出开始时废止旧查询，结束后统一重查归属，命令成功或原异常不会被查询失败改写。大厅、全局邀请与恢复入口消费同一快照；composable 只管理确认、忙态、错误展示和导航，页面 reset 不清其他页面的共享事实。退出确认固定目标房间，弹窗关闭与次要按钮事件分开，只有明确的退出意图进入确认。

普通 GameView 查询、开局和动作响应也使用 GameView 所有者的上下文代次，reset 后不能由旧响应复活已清空房间。切房、离线和卸载同时取消重新加入、退出、托管、动作冲突恢复及终局导航；旧请求的 finally 只能释放自己持有的忙态。

## 单人游戏页面

`useXPage` 组合单局控制器、展示模型、输入/动画和私有结算构造器。控制器拥有单局状态、规则动作与道具/会话编排；展示模型不执行引擎或持久化，DOM 几何与异步动画在专门模块中。取消动画必须结束等待 Promise，并在每次 await 后核对对局代次。

数独生成唯一解并保留提示使用正确终盘的合同；givens 是目标下限，六次尝试共享 200000 搜索节点预算，耗尽时保留更多已知格。幻彩碰撞到时拒绝新输入，等待已接纳动作及其连锁结束后只结算一次。其他计分、道具及难度种子值保持原业务。远端部分难度按 difficultyCode 合并。

## HTTP 与 WebSocket 认证

登录签发 Access Token。受保护 HTTP API 在 `Authorization: Bearer <accessToken>` 中验证 Token 并生成 `AuthenticatedUser`。

浏览器 WebSocket 连接 `/ws/game-hub/realtime` 前，客户端使用 HTTP Bearer 调用 `/auth/realtime-ticket`。服务将短时有效的单次 Ticket 存入 Redis；WebSocket 通过 `?ticket=<ticket>` 原子消费该记录，并从记录构建 `AuthenticatedUser`。连接、重连和重试分别使用新的 Ticket。

`app/core/websocket` 不处理 Room、User 或游戏规则。实时消息和业务操作使用握手认证得到的用户上下文，不信任 payload、查询参数或自定义 Header 中的用户身份声明。

连接登记由带有效期的 Redis 单连接记录维护，每个 `serviceId` 只有一个当前连接记录。浏览器心跳刷新登记有效期；连接替换通过 Redis 原子登记与跨进程事件关闭被替换连接。定向推送和广播经 Redis 频道送达持有目标连接的进程，因此不依赖单个进程内存。

终局收敛同时校验对局版本和房间版本。Finalize 载荷损坏时优先从一致性 RuntimeSnapshot 重建；无法恢复的终局写入 `terminalRecovery` 审计数据，状态为 `MANUAL_COMPENSATION_REQUIRED`，保留结算标识、结算状态和结果标识供人工补偿核对，不执行重复结算或钱包写入。

## 存活与就绪检查

`GET /health/live` 是进程存活检查，只返回 `status: "ok"` 和 `serverTime`，不读取数据库或 Redis。`GET /health/ready` 是依赖就绪检查，验证数据库探测、Redis ping、房间后台协调器和已冻结的游戏模块注册表。

所有依赖就绪时，`/health/ready` 返回 HTTP 200 与统一成功响应；任一依赖不可用时，返回 HTTP 503、`SYSTEM_ERROR`，并在响应 `detail` 中返回 `status`、`serverTime` 和 `components`。前端启动和数据模式切换只通过 `/health/ready` 判定远端可用性。

数据库与 Redis readiness 探测并行，各限 3 秒；数据库线程创建并关闭自己的会话，超时后复用同一在途 future，避免重复堆积。Redis 连接/I/O 超时为 3/5 秒，启动 await 总期限为 30 秒，部分启动失败也释放已创建资源。同步数据库驱动永久阻塞无法由 asyncio 强制终止，探测超时不代表底层调用已经结束。
