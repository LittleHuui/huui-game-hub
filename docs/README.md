# 项目文档

本目录是 huui-game-hub 的正式文档来源。

| 文件 | 内容 |
| --- | --- |
| [architecture.md](architecture.md) | 当前架构、模块边界、运行时提交、Outbox、认证边界 |
| [api.md](api.md) | HTTP API、动作协议、WebSocket 和认证摘要 |
| [websocket-auth-integration.md](websocket-auth-integration.md) | WebSocket 与认证接入、连接生命周期 |
| [new-game-guide.md](new-game-guide.md) | 新游戏接入步骤和禁止事项 |
| [gomoku-rules.md](gomoku-rules.md) | 五子棋规则、配置与动作边界 |
| [doudizhu-rules.md](doudizhu-rules.md) | 斗地主规则、倍率、癞子和结算边界 |
| [docker-guide.md](docker-guide.md) | Docker 构建与部署 |
| [code-style/frontend-code-style.md](code-style/frontend-code-style.md) | 前端分层规范 |
| [code-style/backend-code-style.md](code-style/backend-code-style.md) | 后端分层规范 |

维护约定：

1. 接口变更同步更新 [api.md](api.md)。
2. 架构、任务、运行时或认证边界变更同步更新 [architecture.md](architecture.md)。
3. 新游戏接入方式变更同步更新 [new-game-guide.md](new-game-guide.md)。
4. 斗地主规则或结算变化同步更新 [doudizhu-rules.md](doudizhu-rules.md)。
5. 对外 JSON 使用 camelCase。
