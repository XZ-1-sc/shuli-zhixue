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

## 检查结果

- `python -m compileall -q backend scripts`：通过
- `node --check frontend/static/js/main.js`：通过
- `node --check frontend/static/js/plan.js`：通过
- `node --check frontend/static/js/practice.js`：通过
- `docker compose config --quiet`：通过
- 首次 `docker compose build backend`：Docker Desktop 未启动，已由 Codex 启动
- 再次 `docker compose build backend`：通过，已成功生成 `xingce-smartbrain-backend:latest`

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
