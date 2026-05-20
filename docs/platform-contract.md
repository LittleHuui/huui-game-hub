# 平台统一契约（Platform Contract）

> **状态：已冻结**  
> 本文档为前后端、本地存储、云同步之间的**唯一规范来源**。  
> 实现细节与接口清单见 [`game-hub-end/docs/api.md`](../game-hub-end/docs/api.md)；若与本文冲突，**以本文为准**。

---

## 1. 适用范围

| 层级 | 说明 |
|---|---|
| HTTP API | 请求 Path / Query / Body、响应 `data` |
| 云同步 | `POST /sync/cloud-save` 的 `pendingEvents[].payload` 及返回快照 |
| 本地持久化 | IndexedDB / localStorage 中的业务 JSON |
| 管理端 seed / import | 游戏、难度、道具规则等初始化数据 |

**不在本文范围：** ORM 列名、Python 模型属性、数据库 snake_case 列——仅作为服务端内部实现，不得穿透到对外 JSON。

---

## 2. 命名：仅 camelCase

### 2.1 API

- 所有对外 JSON 字段**必须**使用 **camelCase**（如 `userId`、`gameCode`、`clientId`、`pageNum`）。
- **禁止**在请求或响应中出现 snake_case（如 `game_code`、`duration_ms`、`prop_uses_json`）。
- **禁止**双写或别名兼容（如同时接受 `difficulty` 与 `difficultyCode`）。

### 2.2 云同步 payload

- `pendingEvents[].payload` 及其嵌套对象**只接受 camelCase**。
- 提交 snake_case 视为**参数错误**，不做静默转换。
- 事件信封字段（`clientId`、`eventType`、`createdAt`、`updatedAt`）同样为 camelCase。

### 2.3 与 api.md 的差异说明

[`api.md`](../game-hub-end/docs/api.md) 中「部分 Body 同时接受 snake_case」「payload 建议统一 camelCase」等表述**已作废**。联调与实现须按本章执行。

---

## 3. 历史对局（Match Record）统一字段

以下字段为**对局记录在 API、同步、本地存储中的完整业务面**。不得增删别名，不得用其它键表达同一语义。

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| `gameCode` | string | 是 | 游戏编码，如 `minesweeper`、`match3` |
| `mode` | string | 是 | 玩法模式，如 `single`、`timed`、`endless` |
| `difficultyCode` | string \| null | 否 | 难度编码；无难度玩法为 `null` |
| `result` | string | 是 | 对局结果，如 `win`、`lose`、`quit` |
| `score` | number | 是 | 得分，默认 `0` |
| `durationMs` | number \| null | 否 | 对局时长，**毫秒**；未统计可为 `null` |
| `propUses` | array | 是 | 局内道具使用明细，见 §5；无使用为 `[]` |
| `payload` | object | 是 | 游戏扩展数据，见 §6；无扩展为 `{}` |

### 3.1 实体与幂等字段（API / 同步信封）

对局在持久化与接口响应中**额外**携带公共实体字段（不替代上表业务字段）：

- `serverId`、`clientId`、`userId`、`deviceId`
- `createdAt`、`updatedAt`、`deletedAt`、`syncedAt`（Unix **毫秒**时间戳）

同步时：`pendingEvents[]` 元素为 `{ clientId, eventType: "match_record", createdAt, updatedAt, payload }`，其中 **`payload` 对象须包含 §3 表格中的业务字段**（及必要的 `userId` / `deviceId`，若实现要求在 payload 内携带）。

### 3.2 查询与过滤

历史列表 Query 参数仅使用：`gameCode`、`mode`、`result`、`difficultyCode`、`pageNum`、`pageSize`。

### 3.3 已废弃字段（不得再出现）

| 废弃 | 替代 |
|---|---|
| `time`（秒） | `durationMs` |
| `difficulty` | `difficultyCode` |
| `game_code` 及任意 snake_case | 对应 camelCase |
| `propUsesJson` | `propUses`（数组） |
| `payloadJson` | `payload`（对象） |

---

## 4. 用时：`durationMs` 唯一

- **API、同步 payload、本地存储**统一使用 `durationMs`（整数，毫秒）。
- **禁止**使用 `time`、`timeSec`、`duration_sec` 等以**秒**为单位的字段。
- 展示层（UI 文案「用时 1:23」）由前端自行格式化，不得写回存储。

---

## 5. `propUses`：恒为数组

### 5.1 类型约束

- `propUses` **永远是 JSON 数组** `[]`，元素为 **object**。
- **禁止**以下形态及任何多态兼容：
  - `propUsesJson` 字符串
  - JSON 序列化后再传输的 string
  - 以 propCode 为键的 object / map
  - `null`（无使用时必须为 `[]`）

### 5.2 数组元素（推荐形态）

元素字段因游戏而异，但须为 camelCase 的 plain object。常见字段示例：

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | string | 道具类型或 `propCode` |
| `propCode` | string | 可选，与商城 `propCode` 对齐 |
| `label` | string | 展示用名称 |
| `timerSec` | number | 可选，使用时刻的游戏内计时（秒），仅展示辅助 |
| `createdAt` | number | 可选，使用时刻（毫秒） |

新增游戏可扩展元素字段，但**不得**改变 `propUses` 顶层类型（仍为 array）。

---

## 6. `payload`：恒为对象

- `payload` **永远是 JSON 对象** `{}`。
- **禁止** `payloadJson` 字符串、`null`、数组或标量。
- 游戏特有统计（棋盘尺寸、关卡 id、连击数等）只放在 `payload` 内，键名 camelCase。

---

## 7. 商城与道具排序：`sortNo`

- 游戏目录、难度档位、道具规则（`propRules`）的排序字段统一为 **`sortNo`**（number，升序）。
- 列表接口按 `sortNo` 升序返回；seed / import 时按配置数组顺序写入 `sortNo`。
- **禁止**使用 `sort`、`order`、`sort_order` 等其它键名表达排序。

---

## 8. 不兼容策略

自本文冻结生效起，**不提供**对以下数据的读取、迁移或自动修复：

| 类别 | 示例 |
|---|---|
| 旧 localStorage 键与结构 | 含 `time` 秒字段、`difficulty` 别名、非 camelCase 键 |
| 旧数据库行 | `prop_uses_json` 存非数组、`payload_json` 存非对象、缺 `duration_ms` |
| 旧 sync / API payload | snake_case、`propUsesJson`、`payloadJson`、object 型 `propUses` |
| 旧前端 mapper 兼容分支 | `game_code` 回退、`durationMs` ↔ `time` 互转 |

**处理方式：** 清库、清空本地缓存后，按 seed 重新导入（见 §9）。

---

## 9. 数据重置与 seed

- **允许且推荐**在契约切换时：**清空业务库**并执行 seed / import，恢复游戏、道具、难度等基线数据。
- 用户生成数据（对局、背包、流水等）可一并清除；客户端同步队列应丢弃旧结构事件。
- 不要求编写从旧 schema 到新 schema 的在线迁移脚本；测试环境同样适用「清库 + seed」。

---

## 10. 云同步事件速查

`eventType: "match_record"` 时，`payload` **至少**包含：

```json
{
  "gameCode": "minesweeper",
  "mode": "single",
  "difficultyCode": "easy",
  "result": "win",
  "score": 100,
  "durationMs": 125000,
  "propUses": [
    { "type": "flag", "label": "标记", "timerSec": 42, "createdAt": 1730000000000 }
  ],
  "payload": {}
}
```

`eventType: "score_record"` 的 `payload` 沿用同一套时间与难度命名（`durationMs`、`difficultyCode`），`propUses` 若不存在则省略或置 `[]`（以实现为准，但不得引入 §3.3 废弃字段）。

---

## 11. 验收清单

实现或联调完成后，逐项确认：

- [ ] 任意 API 响应 `data` 中无 snake_case 键
- [ ] `POST /sync/cloud-save` 拒绝 snake_case payload（或返回明确参数错误）
- [ ] 历史对局读写仅含 §3 八个业务字段 + 实体字段
- [ ] 全链路无 `time` / `timeSec` 存储字段
- [ ] `propUses` 恒为 `[]` 或 object 数组，无 `propUsesJson`
- [ ] `payload` 恒为 `{}` 或嵌套 object，无 `payloadJson`
- [ ] 道具/游戏列表按 `sortNo` 排序
- [ ] 旧 localStorage / 旧 DB 数据未做兼容读取

---

## 12. 修订记录

| 日期 | 说明 |
|---|---|
| 2026-05-20 | 初版冻结：camelCase、durationMs、propUses 数组、payload 对象、sortNo、不兼容旧数据 |
