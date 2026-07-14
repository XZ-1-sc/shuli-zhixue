# 行测智脑临时公网访问指南

这个方案不需要部署服务器。你的电脑负责运行项目，Cloudflare Tunnel 负责生成一个临时公网链接。

最终访问入口：

```text
http://localhost:8080
https://xxxx.trycloudflare.com
```

## 1. 准备 MySQL 连接

Docker 后端需要通过 `host.docker.internal` 访问你电脑上的 MySQL。

项目已经做了自动适配：Docker 模式下，如果 `backend/.env` 里的 `DATABASE_URL` 是 `localhost` 或 `127.0.0.1`，后端会自动改用 `host.docker.internal`。

如果你想手动指定 Docker 专用数据库地址，可以在 PowerShell 设置：

```powershell
$env:DOCKER_DATABASE_URL="mysql+pymysql://root:%40你的密码@host.docker.internal:3306/xingce"
```

注意：

- 如果密码里有 `@`，要写成 `%40`。
- 这个变量只在当前 PowerShell 窗口有效，关掉后下次需要重新设置。
- 不设置也可以，系统会优先使用自动适配。
- 不要把 MySQL 端口暴露给公网，公网只暴露 `8080` 对应的 Web 入口。

如果 root 用户无法从 Docker 连接 MySQL，可以新建一个只用于本项目的账号：

```sql
CREATE USER 'xingce_app'@'%' IDENTIFIED BY '你的新密码';
GRANT ALL PRIVILEGES ON xingce.* TO 'xingce_app'@'%';
FLUSH PRIVILEGES;
```

然后手动指定连接地址：

```powershell
$env:DOCKER_DATABASE_URL="mysql+pymysql://xingce_app:你的新密码@host.docker.internal:3306/xingce"
```

## 2. 启动项目

在项目根目录执行：

```powershell
docker compose up --build
```

本机打开：

```text
http://localhost:8080
```

后端健康检查：

```text
http://localhost:8080/api/health
```

API 文档：

```text
http://localhost:8080/docs
```

## 3. 启动 Cloudflare Tunnel

另开一个 PowerShell 窗口，执行：

```powershell
docker run --rm cloudflare/cloudflared:latest tunnel --url http://host.docker.internal:8080
```

终端会输出类似：

```text
https://xxxx.trycloudflare.com
```

把这个链接发给另一台电脑，对方直接打开即可。

也可以用 compose 自带的 tunnel profile：

```powershell
docker compose --profile tunnel up tunnel
```

## 4. 验证流程

在外网电脑打开 tunnel 链接后，依次测试：

- 登录账号：`树虫 / 123456`
- 首页加载今日必做和雷达图
- 进入方案页
- 进入做题页并提交题目
- 打开小逻对话，发送消息
- 查看历史记录

## 5. 关闭临时访问

演示结束后关闭两个终端窗口，或执行：

```powershell
docker compose down
```

Cloudflare Tunnel 关闭后，公网链接会失效。
