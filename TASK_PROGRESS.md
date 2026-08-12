# 任务回溯

## 当前目标

让不在同一网络的电脑可以临时访问本机项目，不做正式服务器部署。

## 已完成

- 前端 API 地址已从固定 `http://localhost:8000` 改为统一入口优先：
  - Docker/Nginx/Tunnel：使用 `window.location.origin`
  - 本地静态调试端口 `5500`、`5173`、`3000`：自动回退到同主机 `8000`
- 新增 Docker 后端镜像：
  - `docker/backend/Dockerfile`
- 新增 Nginx 网关：
  - `docker/nginx/default.conf`
  - `/` 指向前端
  - `/api/*` 指向后端 `backend:8000`
  - `/docs`、`/openapi.json` 指向后端
- 新增 `docker-compose.yml`：
  - `backend`
  - `gateway`
  - `tunnel` profile
  - 对外只发布 `8080`，后端 `8000` 仅在 Docker 网络内部暴露，避免和本机 uvicorn 冲突
- 后端数据库配置已支持 Docker 覆盖项：
  - `DOCKER_DATABASE_URL`
- Docker 模式下会自动把 `DATABASE_URL` 里的 `localhost` / `127.0.0.1` 转成 `host.docker.internal`
- 新增 Docker 忽略规则：
  - `.dockerignore`
- 新增 Docker 数据库变量示例：
  - `backend/.env.docker.example`
- 新增临时公网访问说明：
  - `DOCKER_TUNNEL.md`
- 已初始化 Git 仓库并推送到 GitHub 私有仓库：
  - `https://github.com/XZ-1-sc/xingce-smartbrain`
  - 默认分支：`main`
  - 初始提交：`f303d60`
- 已新增 GitHub Actions Docker 检查：
  - `.github/workflows/docker-build.yml`
  - 推送到 `main` 或 PR 时会在 GitHub runner 上检查 Python/JS 语法、解析 Compose、构建后端 Docker 镜像
- 已确认真实密钥文件没有被提交：
  - `backend/.env` 处于 Git ignored 状态
  - 远端只包含 `backend/.env.example` 和 `backend/.env.docker.example`

## 检查结果

- `python -m compileall -q backend scripts`：通过
- `node --check frontend/static/js/main.js`：通过
- `node --check frontend/static/js/plan.js`：通过
- `node --check frontend/static/js/practice.js`：通过
- `docker compose config --quiet`：通过
- 首次 `docker compose build backend`：Docker Desktop 未启动，已由 Codex 启动
- 再次 `docker compose build backend`：通过，已成功生成 `xingce-smartbrain-backend:latest`
- GitHub 推送：通过
- GitHub Actions `Docker Checks`：已触发，运行地址在仓库 Actions 页面

## 下一步

1. 启动项目：

   ```powershell
   docker compose up --build
   ```

2. 本机验证：

   ```text
   http://localhost:8080
   http://localhost:8080/api/health
   ```

3. 如需手动覆盖数据库地址，可以设置：

   ```powershell
   $env:DOCKER_DATABASE_URL="mysql+pymysql://root:%40你的密码@host.docker.internal:3306/xingce"
   ```

4. 另开窗口启动公网链接：

   ```powershell
   docker run --rm cloudflare/cloudflared:latest tunnel --url http://host.docker.internal:8080
   ```

## 注意事项

- 不要把真实数据库密码写进仓库文件。
- 如果 Docker 后端连不上 MySQL，优先检查 `backend/.env`、`DOCKER_DATABASE_URL` 和 MySQL 用户权限。
- 如果 Cloudflare Tunnel 无法拉取镜像或访问，可切换 cpolar。

## 2026-07-14 Docker 收尾验证

- Docker Engine：已启动并可用
- 容器状态：`backend`、`gateway`、`tunnel` 均为 `Up`
- 本机入口：`http://localhost:8080/` 返回首页 HTML
- 健康检查：`http://localhost:8080/api/health` 返回 `{"status":"ok"}`
- 登录接口：已有测试账号登录成功（凭据只保存在本机）
- Cloudflare Tunnel：`https://receiver-minneapolis-trusted-darwin.trycloudflare.com`
- 公网健康检查：`/api/health` 返回 `{"status":"ok"}`
- 公网首页：返回首页 HTML
- GitHub 仓库：`https://github.com/XZ-1-sc/xingce-smartbrain`
- GitHub Actions：`Docker Checks` 最新运行成功
- 远端密钥检查：仅包含 `.env.example` 文件，未跟踪真实 `backend/.env`
- 当前策略：保持 Docker 服务和 tunnel 运行，不执行 `docker compose down`，不执行 Docker 清理
