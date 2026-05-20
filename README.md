# huui-game-hub

多游戏聚合平台：统一账号、背包、商城、排行榜与云同步；各游戏以独立模块接入，不侵入平台层。

## 当前游戏

| 游戏 | gameCode | 状态 |
|------|----------|------|
| 雷区突围 | `minesweeper` | 已接入 |
| 幻彩碰撞 | `match3` | 已接入 |
| 贪吃蛇 / 俄罗斯方块 | `snake` / `tetris` | 占位，未接入 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3、Pinia、Vue Router、Vite |
| 后端 | FastAPI、SQLAlchemy、Pydantic |
| 数据库 | SQLite |
| 部署 | Docker、nginx、supervisord |

## 项目结构

```
huui-game-hub/
├── game-hub/          # 前端 SPA
├── game-hub-end/      # 后端 API
├── docker/            # nginx、supervisord、entrypoint
├── docs/              # 项目文档（入口见 docs/README.md）
├── Dockerfile
└── compose.yaml
```

## 本地开发（非 Docker）

### 后端

```powershell
cd game-hub-end
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动后 `init_db()` 只会**建表**。首次或清空数据库后，需导入业务种子（与前端 `GAME_SEED_CONFIG` 一致），例如在 `game-hub` 已执行 `npm run export:seed` 的前提下：

```powershell
curl.exe -sS -X POST http://127.0.0.1:8000/api/game-hub/admin/config/import-game-seed `
  -H "Content-Type: application/json" `
  --data-binary @..\game-hub\dist\game-seed.json
```

### 前端

```powershell
cd game-hub
copy .env.example .env.development
npm install
npm run export:seed
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`。前端默认请求 `http://127.0.0.1:8000/api/game-hub/...`。`npm run export:seed` 会根据 `src/constants/gameSeedConfig.js` 生成 `dist/game-seed.json`，供后端 `import-game-seed` 使用。

### 测试

```powershell
cd game-hub-end
pytest
```

## Docker 启动

详见 [docs/docker-guide.md](docs/docker-guide.md)。

```powershell
# 项目根目录
mkdir data
docker compose build
docker compose up -d
```

镜像启动后数据库仅有表结构，**须**按 [docs/docker-guide.md](docs/docker-guide.md) 导入 `game-seed.json`（同源 `GAME_SEED_CONFIG`）后，大厅与商城等才可用。

访问 `http://127.0.0.1/`（API 经 nginx 反代至 `/api/game-hub/`）。

## 文档导航

| 文档 | 说明 |
|------|------|
| [docs/README.md](docs/README.md) | 文档索引 |
| [docs/architecture.md](docs/architecture.md) | 前后端架构与数据流 |
| [docs/api.md](docs/api.md) | HTTP API（camelCase） |
| [docs/new-game-guide.md](docs/new-game-guide.md) | 新游戏接入步骤与模板 |
| [docs/docker-guide.md](docs/docker-guide.md) | Docker 构建与部署教程 |
| [docs/code-style/frontend-code-style.md](docs/code-style/frontend-code-style.md) | 前端规范 |
| [docs/code-style/backend-code-style.md](docs/code-style/backend-code-style.md) | 后端规范 |

新游戏开发请从 [docs/new-game-guide.md](docs/new-game-guide.md) 开始。
