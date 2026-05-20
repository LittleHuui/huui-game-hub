# Game Hub 后端接口文档

> 基于当前代码自动生成，供前端联调使用。  
> 所有接口路径均以 `baseUrl` 为前缀；业务成功时 `code = 0`。

---

## 1. 基础说明

### 1.1 baseUrl

| 项 | 值 |
|---|---|
| 默认值 | `/api/game-hub` |
| 完整示例 | `http://{host}:{port}/api/game-hub` |

可通过环境变量 `API_PREFIX` 覆盖（默认见 `app/core/config.py`）。

### 1.2 统一响应结构

所有 JSON 接口（含业务失败）HTTP 状态码均为 **200**，通过 body 内 `code` / `success` 区分结果。

**成功示例：**

```json
{
  "code": 0,
  "message": "success",
  "success": true,
  "timestamp": 1730000000000,
  "data": {}
}
```

**失败示例：**

```json
{
  "code": 10002,
  "message": "参数错误",
  "success": false,
  "timestamp": 1730000000000,
  "data": null,
  "detail": null
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| code | number | `0` 成功；非 `0` 为业务错误码 |
| message | string | 人类可读提示 |
| success | boolean | 是否成功 |
| timestamp | number | 响应生成时刻，Unix **毫秒**时间戳 |
| data | object \| array \| null | 成功时为业务数据；失败时为 `null` |
| detail | any | 可选，失败时的附加信息（成功响应通常省略） |

### 1.3 时间字段说明

- 文档与接口中的 `createdAt`、`updatedAt`、`deletedAt`、`serverTime`、`clientTime`、`syncedAt`、`lastLoginAt` 等均为 **Unix 毫秒时间戳**（`int`）。
- 接口**不返回**展示用时间字符串（如 `2024-01-01 12:00:00`）。

### 1.4 clientId 说明

- **含义**：客户端生成的幂等 ID，用于创建记录、同步事件、购买等场景的去重。
- **规则**：同一用户下，相同业务表的 `clientId` 不可重复创建（已存在则按幂等逻辑处理或报错，视接口而定）。
- **建议**：使用 UUID 或「设备 ID + 业务序号」等稳定唯一串。
- **响应**：继承 `BaseEntityResponse` 的实体在响应中带 `clientId`（部分汇总类字段可能为 `null`）。

### 1.5 serverId 说明

- **含义**：服务端主键，数据库实体唯一标识。
- **格式**：`{prefix}_{32位十六进制}`，例如 `user_a1b2c3d4e5f6...`、`match_record_...`。
- **用途**：路径参数中的 `userId`、`matchId` 等，通常即对应实体的 `serverId`。
- **响应**：凡持久化实体响应均包含 `serverId`。

### 1.6 公共实体字段（BaseEntityResponse）

以下字段出现在多数「实体」类 `data` 结构中：

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 服务端主键 |
| clientId | string \| null | 客户端幂等 ID |
| createdAt | number | 创建时间（毫秒） |
| updatedAt | number | 更新时间（毫秒） |
| deletedAt | number \| null | 软删除时间（毫秒），未删除为 `null` |

### 1.7 分页结构（PageResponse）

分页接口的 `data` 为：

| 字段 | 类型 | 说明 |
|---|---|---|
| pageNum | number | 当前页码，从 1 开始 |
| pageSize | number | 每页条数 |
| total | number | 符合条件的总记录数 |
| items | array | 当前页数据列表 |

### 1.8 参数命名规范

- **Path / Query / Body** 对外统一使用 **camelCase**（如 `userId`、`gameCode`、`clientId`、`pageNum`）。
- 为兼容旧客户端，部分 Body 字段同时接受 snake_case（如 `client_id`），以各接口 schema 为准。
- 响应 `data` 内字段一律为 camelCase；ORM 内部仍使用 snake_case，不在接口层暴露。

### 1.9 错误码说明

| code | 名称 | 默认 message |
|---:|---|---|
| 0 | SUCCESS | success（仅成功响应） |
| 10001 | COMMON_ERROR | 通用错误 |
| 10002 | PARAM_ERROR | 参数错误 |
| 10003 | SYSTEM_ERROR | 系统错误 |
| 20001 | USER_NOT_FOUND | 用户不存在 |
| 20002 | USERNAME_ALREADY_EXISTS | 用户名已存在 |
| 20003 | USER_DISABLED | 用户已禁用 |
| 30001 | GAME_NOT_FOUND | 游戏不存在 |
| 30002 | GAME_DISABLED | 游戏已禁用 |
| 30003 | GAME_PROP_NOT_FOUND | 游戏道具不存在 |
| 40001 | WALLET_NOT_FOUND | 钱包不存在 |
| 40002 | BALANCE_NOT_ENOUGH | 积分余额不足 |
| 50001 | PURCHASE_ALREADY_EXISTS | 购买记录已存在 |
| 60001 | SYNC_EVENT_TYPE_UNSUPPORTED | 不支持的同步事件类型 |
| 60002 | SYNC_DATA_INVALID | 同步数据无效 |
| 70001 | MATCH_NOT_FOUND | 对局不存在 |
| 80001 | RANKING_QUERY_ERROR | 排行榜查询失败 |

---

## 2. 启动模块

### 2.1 健康检查

| 项 | 值 |
|---|---|
| 接口名称 | 健康检查 |
| 请求方法 | `GET` |
| 请求路径 | `/health` |

**Query 参数：** 无  

**Path 参数：** 无  

**Body 参数：** 无  

**返回 data：**

| 字段 | 类型 | 说明 |
|---|---|---|
| status | string | 服务状态，如 `ok` |
| serverTime | number | 服务端当前时间（毫秒） |

**注意事项：**

- 可用于探活与校时。

---

### 2.2 获取启动上下文

| 项 | 值 |
|---|---|
| 接口名称 | 获取启动上下文 |
| 请求方法 | `POST` |
| 请求路径 | `/boot/context` |

**Query 参数：** 无  

**Path 参数：** 无  

**Body 参数（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| userId | string | 否 | 已登录用户的服务端 ID；未传则仅返回公共数据 |
| deviceId | string | 是 | 客户端设备 ID |
| clientTime | number | 是 | 客户端当前时间（毫秒） |

**返回 data：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverTime | number | 服务端时间（毫秒） |
| userExists | boolean | `userId` 是否对应有效用户 |
| user | object \| null | 用户摘要，见下表 |
| systemSetting | object \| null | 用户系统设置 |
| games | array | 已启用游戏摘要列表 |

`user`（UserSummaryResponse）：

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 用户 ID |
| clientId | string \| null | 客户端 ID |
| username | string | 用户名 |
| nickname | string | 昵称 |
| avatar | string \| null | 头像 URL |
| status | string | 账号状态 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

`systemSetting`（UserSystemSettingResponse）：见 [3.6 获取用户系统设置](#36-获取用户系统设置) 的 `data` 结构。

`games[]`（GameSummaryResponse）：

| 字段 | 类型 | 说明 |
|---|---|---|
| gameCode | string | 游戏编码 |
| gameName | string | 游戏名称 |
| gameSubName | string \| null | 副标题 |
| supportOnline | boolean | 是否支持联机 |
| enabled | boolean | 是否启用 |
| sortNo | number | 排序号 |

**注意事项：**

- 启动页拉取用户、系统设置与游戏列表时使用。
- `userId` 为空或无效时 `userExists = false`，`user` / `systemSetting` 可能为 `null`。

---

### 2.3 云存档同步

| 项 | 值 |
|---|---|
| 接口名称 | 云存档同步 |
| 请求方法 | `POST` |
| 请求路径 | `/sync/cloud-save` |

**Query 参数：** 无  

**Path 参数：** 无  

**Body 参数（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| userId | string | 是 | 用户服务端 ID |
| deviceId | string | 是 | 设备 ID |
| clientSnapshotVersion | number | 否 | 客户端快照版本号 |
| clientTime | number | 是 | 客户端时间（毫秒） |
| pendingEvents | array | 否 | 待上行同步事件，默认 `[]` |

`pendingEvents[]` 元素（PendingSyncEventRequest）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| clientId | string | 是 | 事件幂等 ID |
| eventType | string | 是 | 事件类型，见下表 |
| createdAt | number | 是 | 事件创建时间（毫秒） |
| updatedAt | number | 是 | 事件更新时间（毫秒） |
| payload | object | 否 | 事件载荷，字段因类型而异 |

**当前支持的 eventType：**

| eventType | 说明 |
|---|---|
| user_update | 用户资料更新 |
| user_system_setting_update | 系统设置更新 |
| user_game_setting_update | 游戏设置更新 |
| wallet_ledger | 钱包流水 |
| prop_purchase | 道具购买 |
| prop_usage | 道具使用 |
| match_record | 对局记录 |
| score_record | 成绩记录 |

> `match_action` 在类型定义中存在，但**当前同步处理器未实现**，提交会失败（见文末「暂未开放接口」）。

**返回 data：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverTime | number | 服务端时间（毫秒） |
| cloudSnapshotVersion | number | 云端快照版本 |
| syncResult | object | 同步统计 |
| user | object | 用户摘要 |
| systemSetting | object | 系统设置 |
| wallet | object | 钱包快照 |
| inventory | array | 背包列表 |
| userGameSettings | array | 各游戏设置 |
| walletLedgers | array | 钱包流水（本次同步相关） |
| purchaseRecords | array | 购买记录 |
| propUsageRecords | array | 道具使用记录 |
| matchRecords | array | 对局记录 |
| scoreRecords | array | 成绩记录 |

`syncResult`：

| 字段 | 类型 | 说明 |
|---|---|---|
| receivedCount | number | 收到事件数 |
| successCount | number | 成功处理数 |
| duplicateCount | number | 重复跳过数 |
| failCount | number | 失败数 |

子结构字段与对应查询接口一致（`wallet`、`inventory`、`matchRecords` 等），均含公共实体字段及业务字段。

**注意事项：**

- 客户端离线期间的变更应打包为 `pendingEvents` 批量上报。
- `payload` 内字段同时支持 camelCase 与 snake_case（如 `gameCode` / `game_code`），建议统一使用 **camelCase**。
- 同步失败时可能返回 `60001`、`60002` 等错误码。

---

## 3. 认证模块

### 3.1 用户名登录

| 项 | 值 |
|---|---|
| 接口名称 | 用户名登录 |
| 请求方法 | `POST` |
| 请求路径 | `/auth/login` |

**Query 参数：** 无  

**Path 参数：** 无  

**Body 参数（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| username | string | 是 | 登录用户名；服务端会去除首尾空格 |
| deviceId | string | 是 | 前端设备 ID，用于绑定或刷新设备 |

**返回 data（LoginResponse）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| user | UserAccountResponse | 用户账号信息 |
| systemSetting | UserSystemSettingResponse | 用户系统设置（不存在则创建默认） |
| wallet | UserWalletResponse | 用户钱包快照（不存在则创建空钱包） |
| inventory | UserPropBagResponse[] | 用户背包道具列表 |

**user（UserAccountResponse）字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 用户 ID |
| clientId | string | 客户端幂等 ID |
| username | string | 用户名 |
| nickname | string | 昵称 |
| avatar | string \| null | 头像 |
| status | string | 状态，正常为 `normal` |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳（毫秒） |

**systemSetting（UserSystemSettingResponse）字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 系统设置 ID |
| clientId | string | 幂等 ID |
| userId | string | 用户 ID |
| setting | object | 系统偏好 JSON 对象 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳（毫秒） |

**wallet（UserWalletResponse）字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 钱包 ID |
| clientId | string \| null | 幂等 ID |
| userId | string | 用户 ID |
| balance | number | 可用积分余额 |
| totalEarned | number | 累计获得积分 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳（毫秒） |

**inventory[]（UserPropBagResponse）元素字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 背包行 ID |
| clientId | string \| null | 幂等 ID |
| userId | string | 用户 ID |
| gameCode | string | 游戏编码 |
| propCode | string | 道具编码 |
| quantity | number | 持有数量 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳（毫秒） |

**注意事项：**

- 当前版本不做密码校验与 Token 签发，仅按 `username` 识别用户。
- 登录成功后会按 `userId + deviceId` 绑定或更新设备，并刷新 `lastLoginAt`。
- 用户不存在返回 `20001`（USER_NOT_FOUND）。
- 用户状态非 `normal` 返回 `20003`（USER_DISABLED）。
- 不修改现有 `POST /users/` 创建用户接口；新用户需先创建账号再登录。

---

## 4. 用户模块

> **路径参数**：用户域路径已统一为 `{userId}`、`{gameCode}`（如 `/users/{userId}/games/{gameCode}/setting`）。  
> **请求体**：统一使用 **camelCase**（如 `clientId`）；为兼容旧客户端，创建用户等接口同时接受 `client_id`。

### 4.1 创建用户

| 项 | 值 |
|---|---|
| 接口名称 | 创建用户 |
| 请求方法 | `POST` |
| 请求路径 | `/users/` |

**Query 参数：** 无  

**Path 参数：** 无  

**Body 参数（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| clientId | string | 是 | 创建幂等 ID |
| username | string | 是 | 全局唯一用户名 |
| nickname | string | 是 | 展示昵称 |
| avatar | string | 否 | 头像 URL |

**返回 data（UserAccountResponse）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 用户 ID |
| clientId | string | 客户端幂等 ID |
| username | string | 用户名 |
| nickname | string | 昵称 |
| avatar | string \| null | 头像 |
| status | string | 状态 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

**注意事项：**

- 用户名重复返回 `20002`。
- 请求体请使用 camelCase（`clientId`、`nickname` 等）。

---

### 4.2 查询用户详情

| 项 | 值 |
|---|---|
| 接口名称 | 查询用户详情 |
| 请求方法 | `GET` |
| 请求路径 | `/users/{userId}` |

**Query 参数：** 无  

**Path 参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| userId | string | 用户 `serverId` |

**Body 参数：** 无  

**返回 data：**

| 字段 | 类型 | 说明 |
|---|---|---|
| user | object | 用户账号，结构同 [3.1](#31-创建用户) 的 `data` |
| devices | array | 设备列表 |

`devices[]`（UserDeviceResponse）：

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId / clientId | string | 实体 ID |
| userId | string | 用户 ID |
| deviceId | string | 设备 ID |
| deviceName | string \| null | 设备名称 |
| deviceType | string \| null | 设备类型 |
| lastLoginAt | number \| null | 最后登录时间（毫秒） |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

**注意事项：**

- 用户不存在返回 `20001`。
- 设备列表随用户详情一并返回，无单独「设备列表」接口。

---

### 4.3 更新用户昵称

| 项 | 值 |
|---|---|
| 接口名称 | 更新用户昵称 |
| 请求方法 | `PUT` |
| 请求路径 | `/users/{userId}/nickname` |

**Path 参数：** `userId` — 用户 `serverId`  

**Body 参数（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| nickname | string | 是 | 新昵称 |

**返回 data：** 同 [3.1](#31-创建用户) 用户账号结构。

**注意事项：** 仅更新昵称，不改用户名。

---

### 4.4 绑定或更新用户设备

| 项 | 值 |
|---|---|
| 接口名称 | 绑定或更新用户设备 |
| 请求方法 | `POST` |
| 请求路径 | `/users/{userId}/devices` |

**Path 参数：** `userId` — 用户 `serverId`  

**Body 参数（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| clientId | string | 是 | 该设备记录的幂等 ID |
| deviceId | string | 是 | 前端本地设备 ID |
| deviceName | string | 否 | 设备展示名 |
| deviceType | string | 否 | 设备类型 |

**返回 data：** 单条 `UserDeviceResponse`，结构见 [3.2](#32-查询用户详情)。

**注意事项：**

- 同一 `deviceId` 重复提交会更新设备信息。
- 实现层字段名为 snake_case。

---

### 4.5 获取用户游戏设置

| 项 | 值 |
|---|---|
| 接口名称 | 获取用户游戏设置 |
| 请求方法 | `GET` |
| 请求路径 | `/users/{userId}/games/{gameCode}/setting` |

**Path 参数：**

| 参数 | 说明 |
|---|---|
| userId | 用户 `serverId` |
| gameCode | 游戏编码 |

**Body 参数：** 无  

**返回 data（UserGameSettingResponse）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId / clientId | string | 实体 ID |
| userId | string | 用户 ID |
| gameCode | string | 游戏编码 |
| setting | object | 游戏个性化 JSON，无数据时可能为 `{}` |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

**注意事项：** 若不存在会自动创建默认设置后返回。

---

### 4.6 写入用户游戏设置

| 项 | 值 |
|---|---|
| 接口名称 | 写入用户游戏设置 |
| 请求方法 | `PUT` |
| 请求路径 | `/users/{userId}/games/{gameCode}/setting` |

**Path 参数：** 同 [3.5](#35-获取用户游戏设置)  

**Body 参数（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| setting | object | 否 | 完整覆盖的游戏设置 JSON |

**返回 data：** 同 [3.5](#35-获取用户游戏设置)。

**注意事项：** 全量覆盖 `setting`，非增量合并。

---

### 4.7 获取用户系统设置

| 项 | 值 |
|---|---|
| 接口名称 | 获取用户系统设置 |
| 请求方法 | `GET` |
| 请求路径 | `/users/{userId}/system-setting` |

**Path 参数：** `userId`  

**Body 参数：** 无  

**返回 data（UserSystemSettingResponse）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId / clientId | string | 实体 ID |
| userId | string | 用户 ID |
| setting | object | 系统偏好，见下表 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

`setting` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| dataMode | string | `auto` \| `local` \| `remote` |
| theme | string | `dark` \| `light` \| `auto` |
| autoSync | boolean | 是否自动同步 |
| language | string | 语言，如 `zh-CN` |
| enableSound | boolean | 音效开关 |
| enableAnimation | boolean | 动画开关 |

**注意事项：** 不存在时自动创建默认设置。

---

### 4.8 写入用户系统设置

| 项 | 值 |
|---|---|
| 接口名称 | 写入用户系统设置 |
| 请求方法 | `PUT` |
| 请求路径 | `/users/{userId}/system-setting` |

**Path 参数：** `userId`  

**Body 参数（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| setting | object | 是 | 完整系统设置，结构同 [3.7](#37-获取用户系统设置) 的 `setting` |

**返回 data：** 同 [3.7](#37-获取用户系统设置)。

**注意事项：** 全量覆盖；`setting` 不允许未知字段（`extra=forbid`）。

---

## 5. 游戏模块

### 5.1 游戏列表

| 项 | 值 |
|---|---|
| 接口名称 | 游戏列表 |
| 请求方法 | `GET` |
| 请求路径 | `/games` |

**Query / Path / Body：** 无  

**返回 data：** `GameSummaryResponse[]`

| 字段 | 类型 | 说明 |
|---|---|---|
| gameCode | string | 游戏编码 |
| gameName | string | 名称 |
| gameSubName | string \| null | 副标题 |
| supportOnline | boolean | 是否支持联机 |
| enabled | boolean | 是否启用 |
| sortNo | number | 排序 |

**注意事项：** 仅返回已启用游戏。

---

### 5.2 游戏配置详情

| 项 | 值 |
|---|---|
| 接口名称 | 游戏配置详情 |
| 请求方法 | `GET` |
| 请求路径 | `/games/{gameCode}/config` |

**Path 参数：**

| 参数 | 说明 |
|---|---|
| gameCode | 游戏编码 |

**返回 data（GameConfigResponse）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| game | object | 游戏摘要，同 [4.1](#41-游戏列表) 单项 |
| difficulties | array | 难度配置列表 |
| clientConfigs | array | 客户端适配配置 |
| props | array | 游戏道具规则列表 |

`difficulties[]`（GameDifficultyResponse）：

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId / clientId | string \| null | 实体 ID |
| gameCode | string | 游戏编码 |
| difficultyCode | string | 难度编码 |
| difficultyName | string | 难度名称 |
| config | object | 难度 JSON 配置 |
| enabled | boolean | 是否启用 |
| sortNo | number | 排序 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

`clientConfigs[]`（GameClientConfigResponse）：

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 实体 ID |
| gameCode | string | 游戏编码 |
| difficultyCode | string \| null | 关联难度，可为空 |
| clientType | string | 客户端类型 |
| config | object | 客户端 JSON 配置 |
| enabled | boolean | 是否启用 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

`props[]`（GamePropRuleResponse）：结构同 [5.3](#53-查询游戏可用道具规则)，含 `sortNo`，按 `sort_no` 升序返回。

**注意事项：**

- 游戏不存在或已禁用可能返回 `30001` / `30002`。
- 原 `GET /games/{gameCode}/client-config` 已下线，客户端配置统一由此接口返回。

---

### 5.3 查询游戏可用道具规则

| 项 | 值 |
|---|---|
| 接口名称 | 查询游戏可用道具规则 |
| 请求方法 | `GET` |
| 请求路径 | `/games/{gameCode}/props` |

**Path 参数：** `gameCode`  

**返回 data：** `GamePropRuleResponse[]`，见 [5.2](#52-查询游戏可用道具规则)。

**注意事项：** 仅返回该游戏下已启用的规则。

---

## 6. 道具模块

### 6.1 查询道具定义列表

| 项 | 值 |
|---|---|
| 接口名称 | 查询道具定义列表 |
| 请求方法 | `GET` |
| 请求路径 | `/props` |

**Query 参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| enabled | boolean | 否 | `true` / `false` 按启用状态过滤；省略则不过滤 |

**返回 data（PropDefinitionResponse[]）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 实体 ID |
| clientId | string \| null | 一般为 null |
| propCode | string | 道具编码 |
| propName | string | 道具名称 |
| description | string \| null | 描述 |
| icon | string \| null | 图标 |
| basePrice | number | 基础单价（积分） |
| enabled | boolean | 是否启用 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

---

### 6.2 查询游戏可用道具规则

| 项 | 值 |
|---|---|
| 接口名称 | 查询游戏可用道具规则 |
| 请求方法 | `GET` |
| 请求路径 | `/games/{gameCode}/props` |

（与 [4.3](#43-查询游戏可用道具规则) 为同一接口，此处列出便于按模块查阅。）

**返回 data（GamePropRuleResponse[]）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 规则 ID |
| gameCode | string | 游戏编码 |
| propCode | string | 道具编码 |
| propName | string \| null | 道具名称（关联定义） |
| sortNo | number | 排序号（按 seed/import 中 propRules 数组顺序写入） |
| price | number | 本游戏内售价 |
| maxUsePerMatch | number \| null | 单局最大使用次数 |
| triggerType | string \| null | 触发类型 |
| effectType | string \| null | 效果类型 |
| rule | object \| null | 扩展规则 JSON |
| enabled | boolean | 是否启用 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

---

## 7. 钱包模块

### 7.1 查询用户钱包

| 项 | 值 |
|---|---|
| 接口名称 | 查询用户钱包 |
| 请求方法 | `GET` |
| 请求路径 | `/users/{userId}/wallet` |

**Path 参数：** `userId` — 用户 `serverId`  

**返回 data（UserWalletResponse）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 钱包记录 ID |
| clientId | string \| null | 一般为 null |
| userId | string | 用户 ID |
| balance | number | 当前积分余额 |
| totalEarned | number | 累计获得积分 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

**注意事项：** 钱包不存在时会创建默认空钱包后返回。

---

### 7.2 查询用户钱包流水

| 项 | 值 |
|---|---|
| 接口名称 | 查询用户钱包流水 |
| 请求方法 | `GET` |
| 请求路径 | `/users/{userId}/wallet/ledgers` |

**Path 参数：** `userId`  

**Query 参数：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|:---:|---|---|
| pageNum | number | 否 | 1 | 页码，≥ 1 |
| pageSize | number | 否 | 20 | 每页条数，1–100 |

**返回 data：** 分页结构，`items` 为 `WalletLedgerResponse[]`：

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId / clientId | string | 流水 ID / 幂等 ID |
| userId | string | 用户 ID |
| deviceId | string \| null | 设备 ID |
| gameCode | string \| null | 关联游戏 |
| changeType | string | 变动类型 |
| reason | string | 原因 |
| amount | number | 变动金额（可正可负） |
| balanceAfter | number \| null | 变动后余额 |
| payload | object \| null | 扩展 JSON |
| syncedAt | number \| null | 同步时间（毫秒） |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

**注意事项：** 按 `createdAt` 降序；仅 `deletedAt` 为空的记录。

---

## 8. 背包模块

### 8.1 查询用户背包

| 项 | 值 |
|---|---|
| 接口名称 | 查询用户背包 |
| 请求方法 | `GET` |
| 请求路径 | `/users/{userId}/inventory` |

**Path 参数：** `userId`  

**Query 参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| gameCode | string | 否 | 按游戏过滤 |

**返回 data（UserPropBagResponse[]）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId | string | 背包行 ID |
| userId | string | 用户 ID |
| gameCode | string | 游戏编码 |
| propCode | string | 道具编码 |
| quantity | number | 数量 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

---

### 8.2 查询道具使用记录

| 项 | 值 |
|---|---|
| 接口名称 | 查询道具使用记录 |
| 请求方法 | `GET` |
| 请求路径 | `/users/{userId}/inventory/usage-records` |

**Path 参数：** `userId`  

**Query 参数：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|:---:|---|---|
| gameCode | string | 否 | — | 游戏编码 |
| propCode | string | 否 | — | 道具编码 |
| pageNum | number | 否 | 1 | 页码 |
| pageSize | number | 否 | 20 | 每页条数，最大 100 |

**返回 data：** 分页结构，`items` 为 `PropUsageRecordResponse[]`：

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId / clientId | string | 记录 ID |
| userId | string | 用户 ID |
| deviceId | string \| null | 设备 ID |
| gameCode | string | 游戏编码 |
| matchId | string \| null | 关联对局 ID |
| propCode | string | 道具编码 |
| quantity | number | 使用数量 |
| useReason | string \| null | 使用原因 |
| payload | object \| null | 扩展 JSON |
| syncedAt | number \| null | 同步时间 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

---

## 9. 购买模块

### 9.1 购买道具

| 项 | 值 |
|---|---|
| 接口名称 | 购买道具 |
| 请求方法 | `POST` |
| 请求路径 | `/purchases` |

**Body 参数（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| clientId | string | 是 | 购买记录幂等 ID |
| userId | string | 是 | 用户 ID |
| deviceId | string | 否 | 设备 ID |
| gameCode | string | 是 | 游戏编码 |
| propCode | string | 是 | 道具编码 |
| quantity | number | 是 | 购买数量，≥ 1 |
| createdAt | number | 是 | 客户端创建时间（毫秒） |
| updatedAt | number | 是 | 客户端更新时间（毫秒） |

**返回 data（PropPurchaseResultResponse）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| purchaseRecord | object | 购买记录 |
| wallet | object | 扣款后钱包，结构同 [6.1](#61-查询用户钱包) |
| inventoryItem | object | 对应背包行，结构同 [7.1](#71-查询用户背包) 单项 |

`purchaseRecord`（PropPurchaseRecordResponse）：

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId / clientId | string | 记录 ID |
| userId | string | 用户 ID |
| deviceId | string \| null | 设备 ID |
| gameCode | string | 游戏编码 |
| propCode | string | 道具编码 |
| quantity | number | 数量 |
| unitPrice | number | 单价 |
| totalPrice | number | 总价 |
| syncedAt | number \| null | 同步时间 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

**注意事项：**

- 服务端按游戏规则定价并扣减积分；余额不足返回 `40002`。
- 重复 `clientId` 可能返回 `50001`（幂等场景以实现为准）。
- 支持 camelCase 与 snake_case 字段名（`populate_by_name`）。

---

### 9.2 查询用户购买记录

| 项 | 值 |
|---|---|
| 接口名称 | 查询用户购买记录 |
| 请求方法 | `GET` |
| 请求路径 | `/users/{userId}/purchases` |

**Path 参数：** `userId`  

**Query 参数：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|:---:|---|---|
| gameCode | string | 否 | — | 游戏编码 |
| propCode | string | 否 | — | 道具编码 |
| pageNum | number | 否 | 1 | 页码 |
| pageSize | number | 否 | 20 | 每页条数，最大 100 |

**返回 data：** 分页结构，`items` 为 `PropPurchaseRecordResponse[]`，字段同 [8.1](#81-购买道具)。

---

## 10. 对局模块

### 10.1 查询用户历史对局

| 项 | 值 |
|---|---|
| 接口名称 | 查询用户历史对局 |
| 请求方法 | `GET` |
| 请求路径 | `/users/{userId}/matches` |

**Path 参数：** `userId`  

**Query 参数：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|:---:|---|---|
| gameCode | string | 否 | — | 游戏编码 |
| mode | string | 否 | — | 玩法模式 |
| result | string | 否 | — | 对局结果 |
| difficultyCode | string | 否 | — | 难度编码 |
| pageNum | number | 否 | 1 | 页码 |
| pageSize | number | 否 | 20 | 每页条数，最大 100 |

**返回 data：** 分页结构，`items` 为 `MatchRecordResponse[]`：

| 字段 | 类型 | 说明 |
|---|---|---|
| serverId / clientId | string | 对局 ID |
| userId | string | 用户 ID |
| deviceId | string \| null | 设备 ID |
| gameCode | string | 游戏编码 |
| mode | string | 玩法模式 |
| result | string | 结果 |
| difficultyCode | string \| null | 难度 |
| durationMs | number \| null | 对局时长（毫秒） |
| score | number | 得分 |
| propUses | object \| null | 局内道具使用 JSON |
| payload | object \| null | 扩展 JSON |
| syncedAt | number \| null | 同步时间 |
| createdAt / updatedAt / deletedAt | number \| null | 时间戳 |

---

### 10.2 查询单局对局详情

| 项 | 值 |
|---|---|
| 接口名称 | 查询单局对局详情 |
| 请求方法 | `GET` |
| 请求路径 | `/matches/{matchId}` |

**Path 参数：**

| 参数 | 说明 |
|---|---|
| matchId | 对局 `serverId`（`match_record.server_id`） |

**返回 data：** 单条 `MatchRecordResponse`，字段同 [9.1](#91-查询用户历史对局)。

**注意事项：** 不存在返回 `70001`。

---

## 11. 排行榜模块

### 11.1 查询排行榜

| 项 | 值 |
|---|---|
| 接口名称 | 查询排行榜 |
| 请求方法 | `GET` |
| 请求路径 | `/rankings` |

**Query 参数：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|:---:|---|---|
| gameCode | string | 是 | — | 游戏编码 |
| mode | string | 是 | — | 玩法模式 |
| difficultyCode | string | 否 | — | 难度编码 |
| limit | number | 否 | 10 | 返回条数，1–100 |

**返回 data（LeaderboardResponse）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| gameCode | string | 游戏编码 |
| mode | string | 玩法模式 |
| difficultyCode | string \| null | 难度编码 |
| items | array | 排行榜条目 |

`items[]`（LeaderboardEntry）：

| 字段 | 类型 | 说明 |
|---|---|---|
| rank | number | 名次，从 1 开始 |
| userId | string | 用户 ID |
| nickname | string | 昵称 |
| score | number | 分数 |
| durationMs | number \| null | 用时（毫秒） |
| createdAt | number | 记录创建时间（毫秒） |

**注意事项：**

- 基于 `score_record` 实时计算；排序规则来自 `game_definition.config_json` 中的 `ranking.modes[mode]`（见下文「排行榜规则配置」及 match3 import 示例）。
- 未配置 `ranking.modes[mode]` 时默认：`score` 降序、`createdAt` 升序。
- 规则含 `scoreRecord.payload` 内字段（如 `comboMax`、`moves`）时，先按 `score` 降序取候选池（默认 **1000** 条，可由 `ranking.candidateLimit` 覆盖），再在服务端按完整规则排序；`payload` 解析失败时 payload 指标按 0 处理。
- 示例：`GET /api/game-hub/rankings?gameCode=match3&mode=timed&difficultyCode=normal&limit=10`。
- 示例：`GET /api/game-hub/rankings?gameCode=match3&mode=endless&difficultyCode=normal&limit=10`。
- 查询异常可能返回 `80001`。

**排行榜规则配置（`game_definition.config.ranking`）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| enabled | boolean | 是否启用排行榜（展示层用） |
| candidateLimit | number | 含 payload 指标时的候选池上限，默认 1000 |
| modes | object | 键为 `mode`（如 `single`、`timed`、`endless`） |

`modes[mode]`：

| 字段 | 类型 | 说明 |
|---|---|---|
| primaryMetric | string | 主排序指标：`score`、`durationMs`、`createdAt` 或 `payload` 内 camelCase 字段 |
| orderDirection | string | `asc` 或 `desc` |
| tieBreakers | array | 次级指标：`{ metric, orderDirection }` |

兼容旧版 `sort: [{ field, direction }, ...]`（首项映射为 primaryMetric，其余为 tieBreakers）。

扫雷 `minesweeper` + `single` 示例：`durationMs` asc → `score` desc → `createdAt` asc（与 easy/medium/hard 难度无关，难度仅作 Query 过滤）。

---

## 附录 A：系统模块（已实现，管理用途）

以下接口已在 `app/modules/system/api.py` 注册，前端管理端可按需对接。

### A.1 列出系统配置

- **GET** `/system/configs`
- **data：** `{ items: SystemConfigResponse[] }`
- **SystemConfigResponse：** `serverId`, `configKey`, `configValue`, `description`, `enabled`（0/1）, `createdAt`, `updatedAt`, `deletedAt`

### A.2 创建或更新系统配置

- **PUT** `/system/configs/{configKey}`
- **Body：** `configValue`（可选）, `description`（可选）, `enabled`（可选，0 禁用 / 1 启用）
- **data：** 单条 `SystemConfigResponse`

---

## 附录 C：管理配置导入（开发/运维手动调用）

> **重要**：本接口仅供开发或运维在本地/管理环境**手动**导入统一游戏种子配置，用于对齐前端离线配置与后端初始化数据。  
> **禁止**在前端业务启动流程（如 `boot/context`、应用初始化）中自动调用。

### C.1 导入游戏种子配置

- **POST** `/admin/config/import-game-seed`
- **完整路径示例**：`POST /api/game-hub/admin/config/import-game-seed`
- **Body：**

```json
{
  "props": [],
  "games": []
}
```

#### props[]（平台道具定义）

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| propCode | string | 是 | 平台道具唯一编码 |
| propName | string | 是 | 道具名称 |
| description | string | 否 | 描述 |
| icon | string | 否 | 图标 |
| basePrice | number | 是 | 默认基础价格，`>= 0` |
| enabled | boolean | 是 | 是否启用 |

#### games[]（游戏定义）

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| gameCode | string | 是 | 游戏唯一编码 |
| gameName | string | 是 | 游戏名称 |
| gameSubName | string | 否 | 副标题 |
| supportOnline | boolean | 是 | 是否支持联机 |
| enabled | boolean | 是 | 是否启用 |
| sortNo | number | 是 | 排序号 |
| config | object | 是 | 扩展配置，写入 `game_definition.config_json`（如 display、featureFlags、ranking 等） |
| difficulties | array | 否 | 难度配置列表 |
| clientConfigs | array | 否 | 客户端布局配置列表 |
| propRules | array | 否 | 游戏道具规则列表 |

**difficulties[]**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| difficultyCode | string | 是 | 难度编码 |
| difficultyName | string | 是 | 难度名称 |
| enabled | boolean | 是 | 是否启用 |
| sortNo | number | 是 | 排序号 |
| config | object | 是 | 难度差异配置（如扫雷 rows/cols/mines 等） |

**clientConfigs[]**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| difficultyCode | string | 否 | 关联难度，空表示全局 |
| clientType | string | 是 | 如 `pc` / `mobile_portrait` / `mobile_landscape` |
| enabled | boolean | 是 | 是否启用 |
| config | object | 是 | 客户端布局与适配配置 |

**propRules[]**

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| propCode | string | 是 | 须存在于本次 `props` 或库内已有 `prop_definition` |
| price | number | 是 | 该游戏内售价，`>= 0` |
| （排序） | — | — | `sort_no` 由 `propRules` 数组下标自动生成（首项为 1），无需在 JSON 中传入 |
| maxUsePerMatch | number | 否 | 单局最大使用次数，`>= 0` |
| triggerType | string | 否 | 触发类型 |
| effectType | string | 否 | 效果类型 |
| enabled | boolean | 是 | 是否启用 |
| rule | object | 是 | 效果规则 JSON |

#### 处理规则摘要

- 对 `prop_definition`、`game_definition`、`game_difficulty`、`game_client_config`、`game_prop_rule` 执行 **upsert**（按各表唯一键）。
- **不删除**请求中未提及的旧配置；需禁用请传 `enabled: false`。
- 新增记录 `createdAt` / `updatedAt` 均为当前毫秒时间戳；更新记录保留原 `createdAt`。
- 请求内不允许重复：`propCode`、`gameCode`、同游戏下 `difficultyCode`、同游戏下 `difficultyCode+clientType`、同游戏下 `propCode`。
- 关键编码字段不得为空白：`gameCode`、`propCode`、`difficultyCode`、`clientType`。
- `price`、`basePrice` 必须 `>= 0`；`maxUsePerMatch` 如传入也必须 `>= 0`。
- `propRules[].propCode` 必须存在于本次 `props[]` 或库内已有 `prop_definition`。
- `propRules` 数组顺序决定 `game_prop_rule.sort_no`（首项为 1，依次递增）；查询接口按该字段升序返回，前端无需再排序。

#### match3 / Color Crush 示例

以下示例展示 match3 需要承接的 `prop_definition`、`game_definition`、`game_difficulty`、`game_client_config`、`game_prop_rule`。接口仅保存配置，不新增 match3 专属模块或表，也不实现三消玩法算法。

```json
{
  "props": [
    {
      "propCode": "match3_shuffle",
      "propName": "重排",
      "description": "重新排列棋盘",
      "icon": "",
      "basePrice": 800,
      "enabled": true
    },
    {
      "propCode": "match3_bomb",
      "propName": "炸弹",
      "description": "消除指定区域",
      "icon": "",
      "basePrice": 1200,
      "enabled": true
    }
  ],
  "games": [
    {
      "gameCode": "match3",
      "gameName": "Color Crush",
      "gameSubName": "Match 3",
      "supportOnline": false,
      "enabled": true,
      "sortNo": 20,
      "config": {
        "display": {
          "icon": "",
          "cover": ""
        },
        "featureFlags": {
          "leaderboard": true,
          "shop": true,
          "inventory": true,
          "offline": true,
          "onlineBattle": false
        },
        "ranking": {
          "enabled": true,
          "candidateLimit": 1000,
          "modes": {
            "timed": {
              "primaryMetric": "score",
              "orderDirection": "desc",
              "tieBreakers": [
                {"metric": "comboMax", "orderDirection": "desc"},
                {"metric": "durationMs", "orderDirection": "asc"},
                {"metric": "createdAt", "orderDirection": "asc"}
              ]
            },
            "endless": {
              "primaryMetric": "score",
              "orderDirection": "desc",
              "tieBreakers": [
                {"metric": "comboMax", "orderDirection": "desc"},
                {"metric": "moves", "orderDirection": "desc"},
                {"metric": "createdAt", "orderDirection": "asc"}
              ]
            }
          }
        }
      },
      "difficulties": [
        {
          "difficultyCode": "normal",
          "difficultyName": "普通",
          "enabled": true,
          "sortNo": 1,
          "config": {
            "rows": 9,
            "cols": 9,
            "itemTypes": 6,
            "allowInitialMatches": false,
            "requireAtLeastOneMove": true,
            "controlledRandom": {
              "enabled": true,
              "scoreStages": [
                {"minScore": 0, "friendliness": 0.35},
                {"minScore": 5000, "friendliness": 0.22},
                {"minScore": 15000, "friendliness": 0.12},
                {"minScore": 30000, "friendliness": 0.05}
              ]
            },
            "scoreRules": {
              "base": {
                "3": 30,
                "4": 60,
                "5": 100
              },
              "comboMultiplier": {
                "1": 1,
                "2": 1.5,
                "3": 2,
                "4": 3
              }
            },
            "modes": {
              "timed": {
                "timeLimitSec": 180
              },
              "endless": {
                "timeLimitSec": 0
              }
            },
            "items": [
              {"itemCode": "red", "color": "#ff4d4f", "icon": ""},
              {"itemCode": "blue", "color": "#409eff", "icon": ""},
              {"itemCode": "green", "color": "#67c23a", "icon": ""},
              {"itemCode": "yellow", "color": "#e6a23c", "icon": ""},
              {"itemCode": "purple", "color": "#9c27b0", "icon": ""},
              {"itemCode": "cyan", "color": "#00bcd4", "icon": ""}
            ]
          }
        }
      ],
      "clientConfigs": [
        {
          "difficultyCode": "normal",
          "clientType": "pc",
          "enabled": true,
          "config": {
            "cellSize": 44,
            "layoutMode": "grid",
            "animation": {
              "swapMs": 180,
              "removeMs": 220,
              "dropMs": 260,
              "chainDelayMs": 120
            }
          }
        }
      ],
      "propRules": [
        {
          "propCode": "match3_shuffle",
          "price": 800,
          "maxUsePerMatch": 3,
          "triggerType": "manual",
          "effectType": "shuffle_board",
          "enabled": true,
          "rule": {
            "keepItemCounts": true,
            "allowMatchesAfterShuffle": false,
            "requireAtLeastOneMove": true
          }
        },
        {
          "propCode": "match3_bomb",
          "price": 1200,
          "maxUsePerMatch": 3,
          "triggerType": "manual_select_cell",
          "effectType": "clear_area",
          "enabled": true,
          "rule": {
            "radius": 1,
            "shape": "square",
            "chainAfterUse": true
          }
        }
      ]
    }
  ]
}
```

#### 响应 data（ImportGameSeedResponse）

| 字段 | 类型 | 说明 |
|---|---|---|
| importedGames | number | 新增游戏数 |
| importedDifficulties | number | 新增难度数 |
| importedClientConfigs | number | 新增客户端配置数 |
| importedProps | number | 新增道具定义数 |
| importedPropRules | number | 新增道具规则数 |
| updatedGames | number | 更新游戏数 |
| updatedDifficulties | number | 更新难度数 |
| updatedClientConfigs | number | 更新客户端配置数 |
| updatedProps | number | 更新道具定义数 |
| updatedPropRules | number | 更新道具规则数 |

**成功示例：**

```json
{
  "code": 0,
  "message": "success",
  "success": true,
  "timestamp": 1730000000000,
  "data": {
    "importedGames": 1,
    "importedDifficulties": 3,
    "importedClientConfigs": 0,
    "importedProps": 2,
    "importedPropRules": 2,
    "updatedGames": 0,
    "updatedDifficulties": 0,
    "updatedClientConfigs": 0,
    "updatedProps": 0,
    "updatedPropRules": 0
  }
}
```

---

## 附录 B：暂未开放接口

以下能力在代码中有模型/服务层实现，但**未注册 HTTP 路由**或**同步未启用**，请勿按正式接口对接。

| 说明 | 备注 |
|---|---|
| 对局操作回放 `match_action` | `match/api.py` 注释：回放接口暂不开放；云同步 `eventType=match_action` 当前无处理器，会校验失败 |
| `GET /games/{gameCode}/client-config` | 已下线，请使用 `GET /games/{gameCode}/config` |
| `POST /sync/cloud-save`（sync 子路由） | 云存档仅由启动模块 `POST /sync/cloud-save` 暴露；`sync/api.py` 无 HTTP 注册 |
| 对局操作批量上报 / 按对局查询操作序列 | `MatchModuleService` 有 `batch_create_match_actions`、`list_match_actions`，无对应 REST |

---

## 接口清单索引（正式开放）

| # | 方法 | 路径 |
|---:|---|---|
| 1 | GET | `/health` |
| 2 | POST | `/boot/context` |
| 3 | POST | `/sync/cloud-save` |
| 4 | POST | `/auth/login` |
| 5 | POST | `/users/` |
| 6 | GET | `/users/{userId}` |
| 7 | PUT | `/users/{userId}/nickname` |
| 8 | POST | `/users/{userId}/devices` |
| 9 | GET | `/users/{userId}/games/{gameCode}/setting` |
| 10 | PUT | `/users/{userId}/games/{gameCode}/setting` |
| 11 | GET | `/users/{userId}/system-setting` |
| 12 | PUT | `/users/{userId}/system-setting` |
| 13 | GET | `/games` |
| 14 | GET | `/games/{gameCode}/config` |
| 15 | GET | `/games/{gameCode}/props` |
| 16 | GET | `/props` |
| 17 | GET | `/users/{userId}/wallet` |
| 18 | GET | `/users/{userId}/wallet/ledgers` |
| 19 | GET | `/users/{userId}/inventory` |
| 20 | GET | `/users/{userId}/inventory/usage-records` |
| 21 | POST | `/purchases` |
| 22 | GET | `/users/{userId}/purchases` |
| 23 | GET | `/users/{userId}/matches` |
| 24 | GET | `/matches/{matchId}` |
| 25 | GET | `/rankings` |

**正式开放接口数量：25**（不含附录 A 系统模块 2 个）。
