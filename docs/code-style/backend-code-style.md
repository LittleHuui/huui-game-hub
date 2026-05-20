# 后端代码规范

本文档为 Game Hub 后端项目的统一开发规范。后续所有后端代码生成、评审与提交前，**必须先阅读并遵守本文档**。

---

## 目录

1. [项目技术栈](#1-项目技术栈)
2. [Python 版本规范](#2-python-版本规范)
3. [目录与分层规范](#3-目录与分层规范)
4. [各层职责](#4-各层职责)
5. [返回结构规范](#5-返回结构规范)
6. [字段命名规范](#6-字段命名规范)
7. [时间字段规范](#7-时间字段规范)
8. [ID 规范](#8-id-规范)
9. [同步规范](#9-同步规范)
10. [异常规范](#10-异常规范)
11. [JSON 字段规范](#11-json-字段规范)
12. [模块依赖规范](#12-模块依赖规范)
13. [接口文档规范](#13-接口文档规范)
14. [代码生成与提交要求](#14-代码生成与提交要求)

---

## 1. 项目技术栈

| 组件 | 说明 |
|------|------|
| **Python** | 3.8.11（运行时与语法均以该版本为上限） |
| **FastAPI** | Web 框架，负责路由、依赖注入、请求校验 |
| **SQLAlchemy** | ORM，负责数据库访问 |
| **SQLite** | 默认持久化存储 |
| **Pydantic** | 请求/响应模型与 JSON 字段承接 |

---

## 2. Python 版本规范

### 2.1 基本要求

- 所有代码**必须兼容 Python 3.8.11**。
- 禁止使用 Python 3.9+、3.10+ 专属语法与标准库特性。
- 类型注解统一使用 `typing` 模块写法，不使用内置泛型简写。

### 2.2 禁止写法

| 禁止 | 应使用 |
|------|--------|
| `list[str]` | `typing.List[str]` |
| `dict[str, Any]` | `typing.Dict[str, Any]` |
| `str \| None` | `typing.Optional[str]` 或 `typing.Union[str, None]` |
| `match` / `case` | `if` / `elif` / `else` |
| `list()` 作为类型（3.9+ 简写） | `typing.List` |
| `dict()` 作为类型（3.9+ 简写） | `typing.Dict` |

### 2.3 推荐写法示例

```python
from typing import Any, Dict, List, Optional, Union

def find_users(
    user_ids: List[int],
    nickname: Optional[str] = None,
) -> Dict[str, Any]:
  ...
```

---

## 3. 目录与分层规范

### 3.1 项目结构概览

```
app/
├── main.py              # FastAPI 应用入口
├── api/                 # 路由聚合
├── common/              # 公共响应、异常、枚举等
├── core/                # 配置、数据库、日志等基础设施
└── modules/             # 业务模块
    └── {module_name}/
        ├── api.py
        ├── schemas.py
        ├── models.py
        ├── repository.py
        ├── entity_service.py
        ├── module_service.py
        └── deps.py
```

### 3.2 业务模块文件约定

每个业务模块**尽量**包含以下文件（可按模块复杂度酌情增减，但不得破坏分层边界）：

| 文件 | 说明 |
|------|------|
| `api.py` | HTTP 路由与入参出参声明 |
| `schemas.py` | Pydantic 请求/响应模型 |
| `models.py` | SQLAlchemy ORM 模型 |
| `repository.py` | 数据库查询与持久化 |
| `entity_service.py` | 单实体 CRUD 与基础校验 |
| `module_service.py` | 模块级业务编排 |
| `deps.py` | FastAPI 依赖注入定义 |

---

## 4. 各层职责

### 4.1 api 层

- 只负责 HTTP 入参、出参、依赖注入。
- 调用 `module_service`，不直接访问 `repository` 或 ORM。
- 不编写 SQL，不包含复杂业务逻辑。

### 4.2 module_service 层

- 负责模块内业务编排（多实体协作、事务边界、跨实体流程）。
- **不直接写 SQL**，通过 `entity_service` 或 `repository` 访问数据。

### 4.3 entity_service 层

- 负责**单实体**的 CRUD 与基础校验。
- 可调用同模块的 `repository`，不承载跨模块编排。

### 4.4 repository 层

- 负责 SQLAlchemy 查询、插入、更新、删除。
- 只处理数据访问，不包含业务规则判断。

### 4.5 models 层

- 只定义 ORM 模型（表结构、字段、关系）。
- 禁止混入 Pydantic、业务逻辑或 HTTP 相关代码。

### 4.6 schemas 层

- 只定义 Pydantic 入参、出参模型。
- 禁止混入 ORM 查询或业务编排逻辑。

### 4.7 deps 层

- 只定义 FastAPI `Depends` 相关依赖（如 Service 实例获取）。
- 禁止编写业务逻辑。

### 4.8 调用方向

```
api → module_service → entity_service → repository → models
         ↓
      schemas（入参/出参转换，不参与持久化）
```

---

## 5. 返回结构规范

### 5.1 统一响应外壳

- 所有 HTTP JSON 接口统一返回 `ApiResponse[T]`。
- 成功时统一使用 `success(data)`（定义于 `app.common.response`）。
- 失败时统一抛出 `BizException`，由全局异常处理器转换为 `ApiResponse` 失败结构。

### 5.2 禁止做法

- **不允许**在接口中直接 `return {"code": 0, ...}` 等裸 `dict`。
- **不允许**直接返回 SQLAlchemy `Model` 实例给前端。
- **不允许**使用 `JSONResponse` 手动拼装业务返回体。
- **不允许**在 `api` 层捕获业务异常后自行构造非统一格式的响应。

### 5.3 推荐写法

```python
from app.common.response import ApiResponse, success
from app.modules.user.schemas import UserResponse

@router.get("/users/{user_id}", response_model=ApiResponse[UserResponse])
def get_user(user_id: int, service: UserModuleService = Depends(get_user_module_service)):
    data = service.get_user(user_id)
    return success(data)
```

---

## 6. 字段命名规范

| 层级 | 命名风格 | 示例 |
|------|----------|------|
| 数据库字段 | snake_case | `user_id`, `created_at` |
| Python ORM 字段 | snake_case | `user_id`, `created_at` |
| 接口入参 / 出参（JSON） | camelCase | `userId`, `createdAt` |
| Pydantic Response | 必须输出 camelCase | 使用 `alias` 或统一配置 |

### 6.1 JSON 字段出参

- 数据库中存储为 TEXT 的 JSON，**出参必须反序列化为对象**（`dict` / `list` / 嵌套 Pydantic 模型）。
- **禁止**在接口响应中直接返回 JSON 字符串。

---

## 7. 时间字段规范

- 所有业务时间字段使用 **Unix 毫秒时间戳**（`int` 类型）。
- **禁止**在业务字段中存储展示用时间字符串。
- **禁止**使用 `yyyy-MM-dd HH:mm:ss` 等形式作为业务持久化字段。
- 时区转换、格式化展示由**前端**负责。

| 场景 | 规范 |
|------|------|
| 创建时间 | `createdAt: int`（毫秒） |
| 更新时间 | `updatedAt: int`（毫秒） |
| 业务事件发生时间 | `eventTime: int`（毫秒） |

---

## 8. ID 规范

| 字段 | 说明 |
|------|------|
| `serverId` | 服务端主键，由数据库或服务端生成，全局唯一 |
| `clientId` | 客户端幂等 ID，由客户端生成，用于去重 |

### 8.1 使用原则

- `clientId` **不能替代** `serverId` 作为服务端主键或外键引用。
- 服务端内部关联、查询、持久化一律以 `serverId`（或对应 ORM 主键）为准。
- 新增型事件（如购买、使用道具、提交成绩）必须按 **`userId` + `clientId`** 做幂等处理，避免重复写入。

---

## 9. 同步规范

### 9.1 数据分类与合并策略

| 数据类型 | 合并策略 | 说明 |
|----------|----------|------|
| 状态类数据 | 按 `updatedAt` 合并 | 取时间戳较新的一方覆盖 |
| 事件类数据 | 按 `clientId` 幂等追加 | 已存在则跳过，不重复落库 |
| 派生数据 | 不直接同步 | 根据事件重算后对外提供 |

### 9.2 派生数据重算规则

| 派生数据 | 重算来源 |
|----------|----------|
| 钱包余额 | `wallet_ledger` 流水重算 |
| 背包数量 | 购买记录 + 使用记录重算 |
| 排行榜 | `score_record` 查询计算 |

### 9.3 原则

- 客户端上传的是**事实事件**与**状态快照**，服务端负责幂等与派生计算。
- 禁止将派生结果当作权威源直接覆盖写入而不校验底层事件。

---

## 10. 异常规范

### 10.1 业务异常

- 业务错误统一使用 `BizException`（`app.common.exceptions`）。
- 错误码统一使用 `ErrorCode` / `ErrorCodeItem`（`app.common.error_code`）。
- **禁止**使用 `HTTPException` 表达业务错误（如「用户不存在」「余额不足」）。

### 10.2 错误响应

- 由全局异常处理器将 `BizException` 转换为 `ApiResponse` 失败结构。
- **禁止**向前端返回 `traceback`、堆栈信息或内部调试细节。

### 10.3 推荐写法

```python
from app.common.exceptions import BizException
from app.common.error_code import ErrorCode

raise BizException(ErrorCode.USER_NOT_FOUND)
raise BizException(ErrorCode.PARAM_ERROR, message="gameCode 不能为空")
```

---

## 11. JSON 字段规范

### 11.1 存储

- 数据库中使用 **TEXT** 类型存储 JSON 字符串。

### 11.2 代码承接

- 必须使用 **Pydantic JSON 承接类**，或明确的 `typing.Dict[str, Any]` / `typing.List[Any]`。
- **入库前**：将 Python 对象序列化为 JSON 字符串写入 TEXT 字段。
- **出库后**：将 TEXT 反序列化为 Python 对象，再映射到 Pydantic 响应模型。

### 11.3 禁止做法

- 禁止在接口层直接返回数据库中的 JSON 字符串。
- 禁止在业务逻辑中传递未校验的裸 JSON 字符串作为「结构化数据」。

---

## 12. 模块依赖规范

各模块保持**单一职责**，`module_service` 之间避免循环依赖。

| 模块 | 职责 | 边界 |
|------|------|------|
| `sync` | 云同步编排：合并 pendingEvents、生成快照 | 不实现排行榜 SQL；HTTP 路由挂在 `boot` |
| `boot` | 健康检查、启动上下文、`POST /sync/cloud-save` | 不直接写业务表 |
| `wallet` | 钱包余额与流水 | 余额由流水重算，不直接 patch balance 跳过流水 |
| `inventory` | 背包数量、使用记录查询 | 数量由购买+使用事件重算 |
| `purchase` | 购买扣款与写购买记录 | 不内嵌排行榜逻辑 |
| `prop` | 道具定义与游戏规则 | 不含对局结算 |
| `match` | 对局记录 CRUD / 查询 | 不计算排行榜 |
| `score` | 成绩实体、排行榜规则解析 | 供 `ranking` 调用 |
| `ranking` | 排行榜 HTTP 与查询编排 | 只读 `score_record`，排序规则来自 `game_definition.config` |

### 12.1 依赖原则

- 跨模块调用应通过明确的 Service 接口，避免 `module_service` 互相 import 形成环。
- 公共能力放入 `app.common` 或 `app.core`，不复制粘贴到其他模块。
- 需要复用查询逻辑时，优先下沉到 `repository` 或抽取共享工具，而非跨模块直接操作对方 ORM。

### 12.2 SQLite / SQLAlchemy

- 默认库：`DATABASE_URL`（本地 `./game_hub.db`，Docker `/app/data/game_hub.db`）。
- ORM 字段 snake_case；**出参**经 Pydantic 转为 camelCase。
- JSON 业务字段（`prop_uses_json`、`payload_json` 等）入库为 TEXT，出库反序列化为 `list` / `dict`。
- 事务边界放在 `module_service`；`repository` 不提交跨模块事务。

### 12.3 同步事件（event）

- `eventType` + `clientId` 幂等；`payload` 仅 camelCase。
- `match_record` 的 `propUses` 必须为数组，`payload` 必须为对象。
- 不支持的事件类型返回 `SYNC_EVENT_TYPE_UNSUPPORTED`（60001）。

---

## 13. 接口文档规范

- **新增或修改接口后，必须同步更新** 项目根目录 [`docs/api.md`](../api.md)。
- 文档须写清楚：
  - 请求路径
  - HTTP 方法
  - 请求入参（含 Query / Path / Body）
  - 响应出参
  - 字段说明（含类型、是否必填、示例）
- 文档中的字段命名与接口 JSON 保持一致（camelCase）。

---

## 14. 代码生成与提交要求

1. **阅读规范**：后续所有后端代码生成前，必须先阅读本文档（`docs/code-style/backend-code-style.md`）。
2. **符合规范**：不符合本规范的代码不得提交。
3. **编译检查**：修改 Python 业务代码后，必须执行：

   ```bash
   python -m compileall app
   ```

   确保无语法错误且兼容 Python 3.8.11。
4. **文档同步**：涉及接口变更时，同步更新 [`docs/api.md`](../api.md)。
5. **不改前端**：后端任务默认不修改前端代码，除非任务明确要求。

---

## 附录：快速检查清单

提交前自检：

- [ ] 未使用 Python 3.9+ / 3.10+ 语法
- [ ] 类型注解使用 `typing.List` / `Dict` / `Optional` / `Union`
- [ ] 接口返回 `ApiResponse[T]`，成功用 `success(data)`
- [ ] 业务异常使用 `BizException` + `ErrorCode`
- [ ] 出参字段为 camelCase，时间为毫秒 `int`
- [ ] JSON 字段已反序列化，非字符串直出
- [ ] 分层清晰，api 不直连 repository
- [ ] 已更新 [`docs/api.md`](../api.md)（如有接口变更）
- [ ] 已执行 `python -m compileall app`
