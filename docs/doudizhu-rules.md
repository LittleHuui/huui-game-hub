# 斗地主规则与结算契约

斗地主是三人在线策略回合制游戏，包含一名地主和两名农民。房间满三席后开始，席位可由真人或受控 AI 占用。

## 房间配置与固定规则

用户可配置项只有：

| Key | 含义 |
| --- | --- |
| `enableLaizi` | 发牌前从 3 至 2 的 13 种普通点数中等概率确定癞子，并启用癞子牌型识别与癞子炸弹。 |
| `allowSingleAttachment` | 控制三带一和飞机带单是否允许单牌附件。 |

固定规则为一副 54 张牌、每人 17 张、3 张底牌、随机叫地主起始顺序、叫地主、抢地主、明牌、加倍、春天/反春天、炸弹、王炸以及完整结算。底分为 `1`；抢地主、明牌、加倍、炸弹、王炸、春天和反春天使用种子定义的倍率。

## 阶段与动作

癞子玩法先确定并公开癞子点数，再洗牌发牌；普通玩法直接发牌。发牌后依次进入明牌、叫地主、抢地主、地主确认、加倍、出牌、结算和结束。癞子展示、发牌、地主确认与结算展示通过 `RoomAutoAdvanceTask` 推进；它们不模拟玩家操作。

癞子点数与手牌、底牌的随机分配相互独立，不从底牌选取，也不排除底牌恰好含同点数牌。大小王不能成为癞子。癞子展示阶段手牌与底牌尚未生成，公开状态已有 `laiziRankCode`、`laiziRankValue` 和该点数四种花色的 `laiziCardCodes`；进入发牌阶段后，同点数的四张牌统一标记 `isLaizi`。三人均不叫地主时，重新确定癞子后再发牌。

`PLAY_CARDS` 是 `COMPOSED` 动作：客户端提交 `cardInstanceIds`，服务端识别牌型、校验手牌归属和压制关系，再归一化为 `ResolvedGameAction`。以下动作是 `ENUMERATED`：

```text
SHOW_CARDS, SKIP_SHOW_CARDS,
CALL_LANDLORD, PASS_CALL,
ROB_LANDLORD, PASS_ROB,
DOUBLE, PASS_DOUBLE,
PASS
```

提示和自动候选只提供候选或推荐。`POST /rooms/{roomId}/actions` 在每次提交时重新进行权威解析和合法性校验。

## 自动决策、托管与恢复

AI、在线托管、离线 shell 和回合超时都进入同一条 `AUTOMATED_DECISION` 链路。平台根据当前回合成员创建 `ManagedTurnTask`，斗地主模块为全部可用 actionType 提供候选；候选在同一集合中评分和选择，必要时由斗地主私有 FallbackPolicy 从已验证候选中选择。选中的 `ActionSubmission` 会再次经过交互网关 Resolve，再进入 Runtime 和 Lifecycle。

自动候选与用户提示彼此独立。`PLAY_CARDS` 的自动候选使用斗地主内部搜索预算；提示使用独立的稳定顺序和 cursor。提示接口只返回 `selection`、`summary` 和 `nextCursor`，不公开候选评分、归一化动作或内部 actionId。前端使用提示 selection 填充手牌选择，再通过 Preview 和正式提交确认。

在线托管仅代表真人席位仍在线且由系统代打；shell 仅在 Presence 确认离线后形成。shell 玩家可通过 rejoin 恢复席位和手动操作。托管任务在房间锁内重新读取快照、当前行动者和成员控制状态，已取消托管、已恢复席位或已变化的回合不会执行排队任务。

## 理论结算

令 `B` 为底分，`G` 为全局倍率，`L` 为地主个人倍率，`F` 为某位农民个人倍率。地主与该农民的一对一结算额为：

```text
pairAmount = B × G × L × F
```

地主阵营获胜时，该农民 `scoreDelta = -pairAmount`，地主获得两个农民结算额之和；农民阵营获胜时符号相反。所有玩家的理论 `scoreDelta` 之和始终为零。

全局倍率由抢地主、炸弹、王炸、春天和反春天累乘。叫地主的倍率记录为 `1`；个人倍率由明牌和加倍阶段累乘。

## 平台钱包结算

规则层只生成理论零和结算，不写入钱包。平台结算层根据余额生成实际结果：

- 真人失败方最多扣至零，不产生负余额。
- 获胜方获得完整理论正向分数。
- AI 的 `actualDelta` 始终为 `0`，不生成真人钱包流水。
- `systemDelta > 0` 表示平台净支出，`systemDelta < 0` 表示平台净收入。
- 真人对 AI 的结算仍按真人余额规则扣加分，并以 `systemDelta` 表达平台对手方差额。

## 终局收敛

Lifecycle 产生终局指令和理论结算；Post-turn Outbox 依次驱动平台结算、终局 GameView 推送、Finalize 与派生索引清理。恢复流程从权威房间和 RuntimeSnapshot 重建缺失任务，结算不会重放玩家动作。
