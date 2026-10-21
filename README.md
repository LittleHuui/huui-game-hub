# huui-game-hub

huui-game-hub 是一个多游戏平台，包含 Vue 前端、FastAPI 后端、Redis 驱动的在线房间运行时和统一的策略回合制游戏框架。

## 当前游戏

| 游戏 | gameCode | 类型 | 状态 |
| --- | --- | --- | --- |
| 扫雷突围 | `minesweeper` | 轻量单人 | 已接入 |
| 幻彩碰撞 | `match3` | 轻量单人 | 已接入 |
| 2048 | `2048` | 轻量单人 | 已接入 |
| 数独 | `sudoku` | 轻量单人 | 已接入 |
| UNO | `uno` | 在线策略回合制 | 已接入 |
| 五子棋 | `gomoku` | 在线策略回合制 | 已接入 |
| 斗地主 | `doudizhu` | 在线策略回合制 | 已接入 |

## 核心结构

- 前端：`game-hub/`，Vue 3 + Pinia + Vue Router + Vite。
- 后端：`game-hub-end/`，FastAPI + SQLAlchemy + Redis + WebSocket。
- 文档：`docs/`。
- 部署：`Dockerfile`、`compose.yaml`、`docker/`。

在线策略回合制游戏统一经过 `room` + `strategy_turn` + `game_impls/{gameCode}`：

- `ENUMERATED` 和 `COMPOSED` 是平级交互模式，只在解析为 `ResolvedGameAction` 之前不同。
- `ResolvedGameAction` 是唯一执行入口。
- `RuntimeSnapshot` 是对局状态唯一事实源。
- `RoomGameCommit` 是运行时快照、事件、版本和幂等结果的原子提交边界。
- `PostTurn Outbox` 负责托管动作、自动推进、结算、Finalize 和失败重试。
- 受保护 HTTP 接口使用 Access Token；唯一 WebSocket 通道使用由 HTTP 认证签发的 Redis 单次 Realtime Ticket。

## 本地开发

### 后端

需要真实 Python 3.8.11 环境和 Redis。

启动前配置 `AUTH_JWT_SECRET`、`REDIS_HOST`、`REDIS_PORT` 与对应 `REDIS_PASSWORD`。认证密钥不能为空；Redis 必须可达且密码匹配。不要把真实密钥写入仓库。Docker 的依赖配置见 [部署指南](docs/docker-guide.md)。

```powershell
cd game-hub-end
python3.8 -m venv .venv
.\.venv\Scripts\Activate.ps1
python3.8 -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 前端

```powershell
cd game-hub
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`。

### 健康检查

- `GET /api/game-hub/health/live` 只确认进程可以响应，返回 `status: "ok"` 与 `serverTime`，不探测外部依赖。
- `GET /api/game-hub/health/ready` 检查数据库、Redis、房间后台协调器和已冻结的游戏模块注册表。全部就绪时返回 HTTP 200；任一依赖未就绪时返回 HTTP 503，并在统一响应的 `detail` 中返回各组件状态。
- 前端通过 `readinessCheck` 调用 `/health/ready` 判断远端是否可用。请求超时为 4 秒；本地数据模式只允许此依赖就绪探测请求，不发送远端业务请求。

## 构建

后端：

```powershell
cd game-hub-end
python3.8 -m compileall app
```

前端：

```powershell
cd game-hub
npm run lint
npm run build
```

工程：

```powershell
git diff --check
```

## 文档

- [架构说明](docs/architecture.md)
- [API 文档](docs/api.md)
- [WebSocket 与认证接入](docs/websocket-auth-integration.md)
- [新游戏接入指南](docs/new-game-guide.md)
- [五子棋规则与动作边界](docs/gomoku-rules.md)
- [斗地主规则与结算边界](docs/doudizhu-rules.md)
- [Docker 指南](docs/docker-guide.md)
