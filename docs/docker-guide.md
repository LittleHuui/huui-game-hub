# Docker 部署教程

将 **huui-game-hub**（Vue 前端 + FastAPI 后端 + SQLite）打成单容器，经 **nginx:80** 对外提供页面，并将 `/api/` 反代到容器内 uvicorn。

```
浏览器
   │
   ▼
nginx :80  ── /        → 前端静态（/usr/share/nginx/html）
         └── /api/     → uvicorn :8000（FastAPI）
                              │
                              ▼
                         SQLite /app/data/game_hub.db
                              ▲
                         宿主机 ./data 卷
```

| 组件 | 说明 |
|------|------|
| Node 22 | 仅构建阶段 |
| Python 3.8 | 运行阶段 |
| nginx + supervisord | 同容器内管理两进程 |
| SQLite | 无需独立数据库容器 |

---

## 0. 前置安装

### Windows

1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（含 WSL2 后端）。
2. 打开 Docker Desktop，等待状态为 **Running**。
3. 在 PowerShell 验证：

```powershell
docker --version
docker compose version
```

### Linux（Ubuntu / Debian 示例）

```bash
# 安装 Docker Engine（官方文档：https://docs.docker.com/engine/install/）
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
# 重新登录后
docker --version
docker compose version
```

---

## 1. 本地 Docker 运行（Windows）

在**项目根目录** `huui-game-hub/` 执行。

### 1.1 准备数据目录

```powershell
cd F:\job\private_job\huui-game-hub
New-Item -ItemType Directory -Force -Path .\data
```

`data/` 用于持久化 SQLite，**不要删除**。

### 1.2 构建镜像

```powershell
docker compose build
```

首次构建会下载 Node/Python 基础镜像并执行 `npm run build` 与 `npm run export:seed`（镜像内生成 `game-seed.json`），约数分钟。

### 1.3 启动

```powershell
docker compose up -d
```

### 1.4 验证

```powershell
docker compose ps
docker compose logs -f huui-game-hub
```

浏览器访问：

- 前端：`http://127.0.0.1/`
- 健康检查：`http://127.0.0.1/api/game-hub/health`

PowerShell 探测 API：

```powershell
Invoke-RestMethod http://127.0.0.1/api/game-hub/health
```

### 1.4.1 导入游戏种子（首次 / 空库必须）

业务种子**唯一源码**为前端 `game-hub/src/constants/gameSeedConfig.js` 中的 `GAME_SEED_CONFIG`。镜像构建时已把同源 JSON 输出到静态目录根路径 **`/game-seed.json`**（与 `index.html` 同级）。

在容器已启动、健康检查通过后，从本机执行（使用 Windows 自带的 `curl.exe` 管道，避免手工复制 JSON）：

```powershell
# 合并导入（默认，推荐日常/首次灌库）
curl.exe -sS http://127.0.0.1/game-seed.json `
  | curl.exe -sS -X POST "http://127.0.0.1/api/game-hub/admin/config/import-game-seed?importMode=merge" `
  -H "Content-Type: application/json" `
  --data-binary @-

# 全量逻辑覆盖（种子与库对齐：软删 + 禁用多余项）
curl.exe -sS http://127.0.0.1/game-seed.json `
  | curl.exe -sS -X POST "http://127.0.0.1/api/game-hub/admin/config/import-game-seed?importMode=full&deleteMode=logical" `
  -H "Content-Type: application/json" `
  --data-binary @-

# 全量物理覆盖（仅开发/测试环境）
curl.exe -sS http://127.0.0.1/game-seed.json `
  | curl.exe -sS -X POST "http://127.0.0.1/api/game-hub/admin/config/import-game-seed?importMode=full&deleteMode=physical" `
  -H "Content-Type: application/json" `
  --data-binary @-
```

成功时响应体 `code` 为 `0`。之后大厅、商城、排行榜等依赖库内配置的能力才会正常。

| importMode | deleteMode | 行为摘要 |
|---|---|---|
| `merge`（默认） | 任意（不生效） | 仅 upsert 种子中的项，不删库内多余配置 |
| `full` | `logical`（默认） | upsert 后，对种子未提及项设置 `deletedAt` 且 `enabled=false` |
| `full` | `physical` | upsert 后物理删除种子未提及项（先子表后父表） |

本地非 Docker 开发：在 `game-hub` 目录执行 `npm run export:seed`，再对 `http://127.0.0.1:8000` 等后端地址 POST 同上接口，请求体可使用生成的 `game-hub/dist/game-seed.json` 文件（`curl --data-binary @game-hub/dist/game-seed.json`）。

### 1.5 停止 / 重启

```powershell
docker compose down
docker compose restart huui-game-hub
```

### 1.6 端口 80 被占用

编辑 `compose.yaml`，将端口改为例如 `8080:80`，访问 `http://127.0.0.1:8080/`。

---

## 2. 本地 Docker 运行（Linux）

```bash
cd /path/to/huui-game-hub
mkdir -p data
docker compose build
docker compose up -d
docker compose ps
curl -s http://127.0.0.1/api/game-hub/health
```

浏览器访问 `http://<服务器IP>/`（云主机需在安全组放行 80）。

与 Windows 相同，空库需在健康检查通过后导入种子（静态文件 `http://127.0.0.1/game-seed.json`）：

```bash
# 合并导入（默认）
curl -sS http://127.0.0.1/game-seed.json \
  | curl -sS -X POST 'http://127.0.0.1/api/game-hub/admin/config/import-game-seed?importMode=merge' \
    -H 'Content-Type: application/json' \
    --data-binary @-

# 全量逻辑覆盖
curl -sS http://127.0.0.1/game-seed.json \
  | curl -sS -X POST 'http://127.0.0.1/api/game-hub/admin/config/import-game-seed?importMode=full&deleteMode=logical' \
    -H 'Content-Type: application/json' \
    --data-binary @-
```

---

## 3. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:////app/data/game_hub.db` | 容器内 SQLite 路径（四个 `/`） |
| `VITE_API_BASE` | （构建时为空） | 生产前端使用同源 `/api`，由 nginx 反代 |

在 `compose.yaml` 的 `environment` 中可覆盖 `DATABASE_URL`。

首次启动时后端 `init_db()` **仅创建数据库表**，不会写入任何游戏 / 道具 / 难度等业务数据；**必须**通过 `POST /api/game-hub/admin/config/import-game-seed` 导入种子（见下文「导入游戏种子」）。无需预置 `.db` 文件。

---

## 4. 数据持久化与备份

| 位置 | 路径 |
|------|------|
| 容器内 | `/app/data/game_hub.db` |
| 宿主机 | `./data/game_hub.db`（相对 compose 所在目录） |

**备份（Linux）：**

```bash
cp data/game_hub.db "data/game_hub.db.bak.$(date +%Y%m%d%H%M%S)"
```

**备份（Windows PowerShell）：**

```powershell
Copy-Item .\data\game_hub.db ".\data\game_hub.db.bak.$(Get-Date -Format 'yyyyMMddHHmmss')"
```

**恢复：** 先 `docker compose down`，替换 `data/game_hub.db`，再 `docker compose up -d`。

---

## 5. 线上部署流程（Linux 服务器）

### 5.1 在构建机（本机或 CI）构建并推送

```bash
cd /path/to/huui-game-hub

# 构建
docker build -t ghcr.io/littlehuui/huui-game-hub:latest .
docker build -t ghcr.io/littlehuui/huui-game-hub:1.0.0 .

# 登录 GitHub Container Registry（Token 需 write:packages）
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# 推送
docker push ghcr.io/littlehuui/huui-game-hub:latest
docker push ghcr.io/littlehuui/huui-game-hub:1.0.0
```

**Windows 构建机** 将上述 `bash` 命令在 PowerShell 中同样可用（需已 `docker login`）。

### 5.2 在服务器拉取并启动

```bash
git clone <你的仓库地址> huui-game-hub
cd huui-game-hub
mkdir -p data

# 使用 compose 中配置的镜像名拉取
docker compose pull huui-game-hub
docker compose up -d
```

若服务器**本地构建**而不拉远程：

```bash
docker compose build
docker compose up -d
```

### 5.3 更新镜像

```bash
cd huui-game-hub
docker compose pull huui-game-hub
docker compose up -d
```

或强制重建容器：

```bash
docker compose up -d --force-recreate huui-game-hub
```

### 5.4 可选：Watchtower 自动更新

`compose.yaml` 中 Watchtower 使用 profile，默认不启动。需要自动拉取时：

```bash
docker compose --profile watchtower up -d
```

私有 GHCR 需在 Watchtower 环境变量中配置 `REPO_USER` / `REPO_PASS`。

---

## 6. 仅本地镜像名（不推远程）

```powershell
docker build -t huui-game-hub:local .
docker run -d --name huui-game-hub-test -p 8080:80 -v "${PWD}/data:/app/data" -e DATABASE_URL=sqlite:////app/data/game_hub.db huui-game-hub:local
```

访问 `http://127.0.0.1:8080/`。

---

## 7. 目录与配置文件

```
huui-game-hub/
├── Dockerfile
├── compose.yaml
├── .dockerignore
├── docker/
│   ├── nginx.conf       # 静态 + /api/ 反代
│   ├── supervisord.conf # nginx + uvicorn
│   └── entrypoint.sh    # 创建 /app/data
└── data/                # 运行时生成，挂载卷
```

---

## 8. 常见问题

### 8.1 前端能开，接口 404 / 502

- 确认请求路径为 `/api/game-hub/...`（不是直连 8000，除非单独暴露后端）。
- 查看日志：`docker compose logs huui-game-hub`。

### 8.2 `entrypoint.sh: exec format error`（Windows）

脚本须为 **LF** 换行。仓库 `.gitattributes` 已指定；重新 checkout 或转换后 **重新 build**。

### 8.3 更新后数据丢失

检查是否删除宿主机 `data/` 或 compose 中 `volumes` 被改掉。

### 8.4 健康检查失败

容器启动后约 40s 内可能仍在初始化；`docker compose ps` 查看 HEALTH。手动：

```bash
curl http://127.0.0.1/api/game-hub/health
```

---

## 9. 运维命令速查

| 操作 | 命令 |
|------|------|
| 构建 | `docker compose build` |
| 启动 | `docker compose up -d` |
| 导入业务种子（空库必须） | 见上文 [§1.4.1](#141-导入游戏种子首次--空库必须)：将 `/game-seed.json` POST 至 `import-game-seed` |
| 停止 | `docker compose down` |
| 日志 | `docker compose logs -f huui-game-hub` |
| 进入容器 | `docker exec -it huui-game-hub sh` |
| 拉取最新 | `docker compose pull huui-game-hub` |

---

## 10. 与非 Docker 本地开发的区别

| 项 | 本地 dev | Docker |
|----|----------|--------|
| 前端 | `npm run dev` :5173 | 构建后静态文件 |
| API 地址 | `VITE_API_BASE=http://127.0.0.1:8000` | 空，走同源 `/api` |
| 后端 | 单独 `uvicorn` :8000 | 容器内 127.0.0.1:8000 |
| CORS | 允许 5173 | 同源无需 CORS |
| 业务种子 | `npm run export:seed` 后 curl 导入后端 | 启动后从 `/game-seed.json` 导入（见 §1.4.1） |

本地开发说明见根目录 [README.md](../README.md)。
