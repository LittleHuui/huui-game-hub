# huui-game-hub Docker 部署教程

本文档说明如何使用 Docker 将 **huui-game-hub**（前端 Vue3 + 后端 FastAPI + SQLite）部署到服务器，并通过 nginx 对外提供访问。

## 架构概览

```
浏览器
   │
   ▼
nginx :80  ── /        → 前端静态文件（Vue SPA）
         └── /api/     → uvicorn :8000（FastAPI）
                              │
                              ▼
                         SQLite（/app/data/game_hub.db）
                              ▲
                         宿主机 ./data 卷挂载
```

| 组件 | 版本（镜像内） | 说明 |
|------|----------------|------|
| Node.js | 22.22.0 | 仅构建阶段使用 |
| Python | 3.8.11 | 运行阶段 |
| nginx | Debian 包 | 对外 80 端口 |
| 数据库 | SQLite | 无需独立数据库容器 |

---

## 前置条件

### 本机 / CI（构建镜像）

- [Docker](https://docs.docker.com/get-docker/) 20.10+
- 可访问镜像仓库（如 [GitHub Container Registry](https://ghcr.io)）

### 服务器（运行容器）

- Linux 服务器（推荐 Ubuntu 22.04+ / Debian 11+）
- 已安装 Docker Engine 与 Docker Compose v2
- 开放 **80** 端口（或自行修改 `compose.yaml` 端口映射）

验证命令：

```bash
docker --version
docker compose version
```

---

## 目录与文件说明

```
huui-game-hub/
├── Dockerfile              # 多阶段构建：Node 构建前端 + Python 运行后端
├── compose.yaml            # 应用 + Watchtower 编排
├── .dockerignore
├── docker/
│   ├── nginx.conf          # 静态资源 + /api/ 反代
│   ├── supervisord.conf    # nginx + uvicorn 进程管理
│   └── entrypoint.sh       # 启动前创建数据目录
├── data/                   # 运行时生成，SQLite 持久化（勿删）
└── docs/
    └── docker-deploy.md    # 本文档
```

---

## 快速部署（使用已推送镜像）

适用于服务器直接拉取 `ghcr.io/littlehuui/huui-game-hub:latest`。

### 1. 准备目录

```bash
git clone <你的仓库地址> huui-game-hub
cd huui-game-hub
mkdir -p data
```

`data/` 用于挂载 SQLite，**请勿删除**，否则数据丢失。

### 2. 启动服务

```bash
docker compose up -d
```

### 3. 验证

```bash
# 查看容器状态
docker compose ps

# 查看应用日志
docker compose logs -f huui-game-hub

# 健康检查（经 nginx 反代）
curl -s http://127.0.0.1/api/game-hub/health
```

浏览器访问：

- 前端：`http://<服务器IP>/`
- API 前缀：`http://<服务器IP>/api/game-hub/...`

### 4. 停止 / 重启

```bash
# 停止
docker compose down

# 重启（保留 data 卷数据）
docker compose restart huui-game-hub
```

---

## 本地构建并推送镜像

### 1. 构建

在项目根目录执行：

```bash
docker build -t ghcr.io/littlehuui/huui-game-hub:latest .
```

指定版本标签（推荐发布时打版本号）：

```bash
docker build -t ghcr.io/littlehuui/huui-game-hub:1.0.0 .
```

### 2. 登录 GHCR

```bash
echo <GITHUB_TOKEN> | docker login ghcr.io -u <GITHUB_USERNAME> --password-stdin
```

Token 需具备 `write:packages` 权限。

### 3. 推送

```bash
docker push ghcr.io/littlehuui/huui-game-hub:latest
docker push ghcr.io/littlehuui/huui-game-hub:1.0.0
```

### 4. 服务器拉取并更新

```bash
docker compose pull huui-game-hub
docker compose up -d
```

若已配置 **Watchtower**（见下文），推送后服务器会自动拉取并重启。

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:////app/data/game_hub.db` | SQLite 绝对路径（四个 `/`） |
| `VITE_API_BASE` | （构建时为空） | 前端 API 基址；生产使用同源 `/api` 反代 |

在 `compose.yaml` 中修改示例：

```yaml
environment:
  DATABASE_URL: sqlite:////app/data/game_hub.db
```

首次启动时，后端会自动 `init_db()` 建表并写入种子数据，**无需**预置数据库文件。

---

## 数据持久化

SQLite 文件路径：

- 容器内：`/app/data/game_hub.db`
- 宿主机：`./data/game_hub.db`（相对 `compose.yaml` 所在目录）

**备份示例：**

```bash
cp data/game_hub.db data/game_hub.db.bak.$(date +%Y%m%d%H%M%S)
```

**恢复：** 停止容器 → 替换 `data/game_hub.db` → 再启动。

```bash
docker compose down
cp /path/to/backup.db data/game_hub.db
docker compose up -d
```

---

## Watchtower 自动更新

`compose.yaml` 已包含 Watchtower，行为如下：

- 每 **300** 秒检查一次带 label 的容器
- 仅更新 `com.centurylinklabs.watchtower.enable=true` 的容器（即 `huui-game-hub`）
- 拉取新镜像后自动重启应用容器

### 私有镜像仓库认证

若 GHCR 为私有仓库，在服务器创建 `~/.docker/config.json` 或配置 Watchtower 凭据，例如：

```yaml
watchtower:
  environment:
    REPO_USER: <github_username>
    REPO_PASS: <github_token>
```

### 手动触发更新（不等待轮询）

```bash
docker compose pull huui-game-hub
docker compose up -d huui-game-hub
```

---

## 仅本地测试（不推远程）

```bash
docker build -t huui-game-hub:local .

# 临时覆盖 compose 中的 image，或 docker run：
docker run -d --name huui-game-hub-test \
  -p 8080:80 \
  -v "$(pwd)/data:/app/data" \
  -e DATABASE_URL=sqlite:////app/data/game_hub.db \
  huui-game-hub:local
```

访问：`http://127.0.0.1:8080/`

---

## 常见问题

### 1. 端口 80 被占用

修改 `compose.yaml`：

```yaml
ports:
  - "8080:80"
```

访问 `http://<服务器IP>:8080/`。

### 2. 容器启动后 API 502

```bash
docker compose logs huui-game-hub
```

确认 uvicorn 已启动；常见原因为 Python 依赖安装失败或数据库目录无写权限。

```bash
# 确保 data 目录可写
chmod 755 data
```

### 3. 前端能打开，接口 404

确认请求路径为 `/api/game-hub/...`，且 nginx 配置中 `location /api/` 已反代到 `127.0.0.1:8000`。

### 4. `entrypoint.sh` 报错 `exec format error`

多为 Windows 下 CRLF 换行导致。将 `docker/entrypoint.sh` 转为 LF 后重新构建：

```bash
# Git 全局或仓库 .gitattributes 中对该文件设置 eol=lf
```

### 5. 更新镜像后数据丢失

检查是否删除了宿主机 `data/` 目录，或 compose 中 `volumes` 挂载是否被改动。

---

## CI 构建示例（GitHub Actions 片段）

```yaml
- name: Build and push
  run: |
    docker build -t ghcr.io/littlehuui/huui-game-hub:${{ github.sha }} .
    docker tag ghcr.io/littlehuui/huui-game-hub:${{ github.sha }} ghcr.io/littlehuui/huui-game-hub:latest
    docker push ghcr.io/littlehuui/huui-game-hub:${{ github.sha }}
    docker push ghcr.io/littlehuui/huui-game-hub:latest
```

服务器 Watchtower 会在检测到 `latest` 更新后自动重启业务容器。

---

## 运维命令速查

| 操作 | 命令 |
|------|------|
| 启动 | `docker compose up -d` |
| 停止 | `docker compose down` |
| 查看日志 | `docker compose logs -f huui-game-hub` |
| 进入容器 | `docker exec -it huui-game-hub sh` |
| 拉取最新镜像 | `docker compose pull` |
| 重建并启动 | `docker compose up -d --force-recreate huui-game-hub` |

---

## 相关链接

- 镜像：`ghcr.io/littlehuui/huui-game-hub:latest`
- 后端 API 文档：见 `game-hub-end/docs/api.md`
