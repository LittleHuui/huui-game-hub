# 项目文档

本目录为 **huui-game-hub** 唯一正式文档来源。子项目内不再维护重复的 `docs/`。

## 文档列表

| 文件 | 读者 | 内容 |
|------|------|------|
| [architecture.md](architecture.md) | 开发者、Cursor | 分层架构、模块边界、数据流 |
| [api.md](api.md) | 开发者、Cursor | REST API：请求/响应、字段、错误码 |
| [new-game-guide.md](new-game-guide.md) | 游戏接入开发者 | 前后端接入步骤、模板、允许/禁止项 |
| [docker-guide.md](docker-guide.md) | 运维、开发者 | Windows/Linux 构建与部署 |
| [code-style/frontend-code-style.md](code-style/frontend-code-style.md) | 前端、Cursor | 分层职责与禁止项 |
| [code-style/backend-code-style.md](code-style/backend-code-style.md) | 后端、Cursor | modules 分层与 API 规范 |

## 维护约定

1. 接口变更 → 更新 [api.md](api.md)
2. 架构或数据流变更 → 更新 [architecture.md](architecture.md)
3. 新游戏接入约定变更 → 更新 [new-game-guide.md](new-game-guide.md)
4. Docker/部署变更 → 更新 [docker-guide.md](docker-guide.md) 与根目录 `Dockerfile` / `compose.yaml`
5. 对外 JSON **仅 camelCase**

## Cursor 默认引用

- 前端：`docs/code-style/frontend-code-style.md`；游戏页另见 `docs/new-game-guide.md`
- 后端：`docs/code-style/backend-code-style.md` + `docs/api.md`
- 部署：`docs/docker-guide.md`
