# 数理智学

数理智学是一个基于多智能体协作的全科个性化学习导航系统，覆盖学生学习、教师教学、题库与作业、消息协作、知识图谱、学习分析及智能交互等功能。

## 项目结构

- `frontend/`：Vue 3 前端应用。
- `backend/`：Python 后端服务、数据模型与业务服务。
- `backend/migrations/`：Alembic 数据库迁移。
- `scripts/`：初始化、迁移、数据处理与自动化测试脚本。
- `data/`：课程、知识图谱和题目数据。
- `docker/`、`docker-compose.yml`：容器化运行配置。
- `docs/`：项目说明、设计材料和交付文档。

## 本地启动

复制示例环境配置并填写本机参数后，通过 Docker Compose 启动：

```powershell
Copy-Item backend/.env.docker.example backend/.env
docker compose up -d --build
```

启动后访问 `http://localhost:8080`。请勿提交真实环境配置、敏感凭据或数据库备份。

## 开发验证

```powershell
cd frontend
npm ci
npm run lint
npm run build

cd ../
python -m unittest discover -s backend/tests -v
```

更完整的功能说明和专项验收材料请查看 `docs/` 目录。
