# 「行测智脑」项目测试报告

> 测试执行人：AI 测试工程师（DeepSeek Harness）
> 测试日期：2026-08-23
> 测试环境：Windows / Python 3.10.11 (venv) / MySQL 8.0.46 / Node v24.18.0 / npm 11.16.0

---

## 一、测试范围与结论总览

| 测试类别 | 结果 | 摘要 |
|---|---|---|
| 环境与依赖检查 | ✅ 通过 | Python/MySQL/Node 均可用，34 张业务表 |
| 后端静态检查（75 个 .py） | ✅ 通过 | AST 语法全通过，FastAPI 应用可正常导入 |
| 后端单元测试 | ✅ 10/10 通过 | unittest：AI 契约 / 诊断 / 协商 / 评分 |
| API 冒烟测试 | ✅ 45/45 通过 | 公开端点、认证、业务流程、边界输入 |
| 前端 ESLint | ✅ 0 错误 | eslint src --ext .js,.vue |
| 前端构建 | ✅ 成功 | vite build 15.3s，产物正常 |
| scripts 集成/E2E 测试 | ⚠️ 6 通过 / 2 失败 | 见下方详情 |
| 安全与健壮性专项 | ✅ 通过 | 注入/穿越/越权/限流均防护正确 |
| **发现缺陷** | 🔴 **2 个问题**（1 严重 + 1 中等）+ 3 个观察项 | 见「缺陷清单」 |

**总体结论：核心功能可用，安全基线良好；但存在 1 个数据库迁移缺陷（全新部署会失败）和 1 处鉴权行为不一致，建议修复后发布。**

---

## 二、测试环境

| 项目 | 版本/状态 |
|---|---|
| Python | 3.10.11（项目 .venv） |
| MySQL | 8.0.46（math_brain 库，34 张表，990 道已发布题目） |
| FastAPI | 0.139.0 / Uvicorn 0.51.0 / SQLAlchemy 2.0.51 / Pydantic 2.13.4 |
| Node.js / npm | v24.18.0 / 11.16.0 |
| 前端 | Vue 3 + Vite，devDependencies 齐备 |
| 认证方式 | Cookie 会话（math_brain_session，HttpOnly + Secure 支持） |

---

## 三、详细测试结果

### 3.1 后端静态检查 ✅

- 对 backend 下 75 个 Python 源文件做 AST 语法解析：**全部通过**。
- `from app.main import app` 成功导入，注册了全部 17 个业务路由模块（auth / health / stages / practice / assessment / diagnosis / profile / chat / uploads / teacher×6 / assignments）。
- 说明：新版 FastAPI 的 `_IncludedRouter` 为懒加载占位，`app.routes` 中显示为占位对象属正常行为，实际请求可正常路由。

### 3.2 后端单元测试 ✅ 10/10

用标准库 `unittest discover` 运行 `backend/tests`：

| 测试文件 | 用例 | 结果 |
|---|---|---|
| test_ai_contracts.py | 6 | ✅ 全过（资源标识、协商范围、批次隔离等） |
| test_diagnostician.py | 1 | ✅ 全过（LLM 载荷小数序列化） |
| test_negotiator.py | 1 | ✅ 全过（单轮清晰诊断并建规划） |
| test_scoring.py | 3 | ✅ 全过（数学符号归一化、空白答案判分） |

### 3.3 API 冒烟测试 ✅ 45/45

对运行中的后端（127.0.0.1:8099）执行 45 项测试，全部通过：

- **公开端点**（7）：`/`、`/api/health`、`/api/stages`、`/api/courses`（含 stage 过滤）、`/api/question-types`、`/openapi.json`
- **匿名访问防护**（5）：diagnose / knowledge-graph / resources / profile-summary / notes 匿名访问均返回 **401**
- **认证流程**（3）：注册 → 登录 → 会话 Cookie 设置
- **登录后接口**（17）：诊断、推荐、规划、错题复盘、AI 报告、热力趋势、消息、通知、偏好、档案、能力图谱、成就、笔记、对话历史、知识图谱、资源、协商记录 —— 均 200
- **核心业务**（5）：随机抽题 → 提交答案（按题型选 selected_answer/answer_text）→ 错题复盘 → 笔记增/改/删 → 偏好更新
- **错误与边界**（5）：空注册 422、错误凭据 401、空提交 422、GET 单笔记 405（未实现，观察项）、学生访问教师接口 403

### 3.4 前端 ✅

- **ESLint**：0 error / 0 warning。
- **Vite 构建**：成功，15.3s，产出 index.html + assets（echarts 511KB 为最大 chunk，gzip 后 175KB，可接受）。

### 3.5 scripts 集成 / E2E 测试 ⚠️ 6 通过 / 2 失败

| 脚本 | 结果 | 说明 |
|---|---|---|
| test_question_document_parser.py | ✅ | 题目文档解析器 |
| test_agents_structured.py | ✅ | 多智能体结构化契约（LLM mock） |
| test_agent_pipeline_e2e.py | ✅ | 智能体管线 E2E（诊断→协商→规划） |
| test_ai_features_api.py | ✅ | AI 功能 API 回归 |
| test_question_import_api.py | ✅ | 题目批量导入 API（Excel 模板/预览/提交） |
| test_teacher_workflow_e2e.py | ✅ | 教师端全流程（建班→组卷→布置→批改→权限隔离） |
| **test_authz_e2e.py** | ❌ **失败** | 鉴权行为不一致（见缺陷 #2） |
| **test_alembic_migrations.py** | ❌ **失败** | 迁移缺陷（见缺陷 #1） |

> 备注：test_student_browser.py / test_teacher_browser.py 为 Selenium 浏览器测试，本环境无 Chrome 浏览器，未执行（属环境限制）。其余测试脚本均通过 `__main__` 入口直接运行。

### 3.6 安全与健壮性专项 ✅

| 探测项 | 结果 |
|---|---|
| SQL 注入（4 种载荷：`' OR '1'='1`、双引号、`admin'--`、UNION） | ✅ 全部 401，参数化查询防护有效 |
| 路径穿越上传（`..\..\`、`../../`、URL 编码） | ✅ 文件名经 basename 提取 + UUID 重命名落盘，无穿越风险 |
| 文件类型白名单 | ✅ `.exe` → 415；伪装图片 → 415；PDF/Office 魔数校验 |
| 越权删除（用户 B 删用户 A 文件） | ✅ 409 拒绝 |
| 越权读取（用户 B 读用户 A 文件） | ✅ 403 拒绝 |
| 越权访问教师接口（学生身份 ×6 接口） | ✅ 全部 403 |
| 聊天限流 | ✅ 第 11 次请求返回 429 |
| 超长/非法参数（stage 超长、非法题型、limit 超限） | ✅ 全部 422 |
| 密码存储 | ✅ PBKDF2-SHA256（260k 迭代 + 16B 随机盐 + 常量时间比较） |
| 会话 Cookie | ✅ HttpOnly + SameSite=lax，HTTPS 转发时置 Secure |

---

## 四、缺陷清单

### 🔴 缺陷 #1（严重 / P1）：Alembic 迁移在全新数据库上无法完成升级

- **文件**：`backend/migrations/versions/20260820_0001_baseline.py`、`20260823_0004_user_preferences.py`
- **现象**：`scripts/test_alembic_migrations.py`（创建全新空库 → upgrade head）失败：
  ```
  pymysql.err.OperationalError: (1050, "Table 'user_preferences' already exists")
  ```
- **根因**：基线迁移 0001 使用 `Base.metadata.create_all(...)` **动态创建当前 ORM 中定义的全部表**。`user_preferences` 模型随后被加入 ORM（`side.py:48`），因此全新库在 0001 阶段就建好了该表；而迁移 0004 又显式 `op.create_table("user_preferences", ...)`，导致重复建表报错。
- **影响**：**任何从零开始的部署（新环境 / CI / 演示环境）执行 `alembic upgrade head` 都会失败**。当前生产库因历史执行顺序侥幸通过，掩盖了该问题。
- **修复建议**：迁移 0004 改为幂等（`op.create_table` 前检查表是否存在），或基线迁移改用显式表清单而非 `create_all`，或将 `user_preferences` 从 0001 的 create_all 范围中排除。

### 🟠 缺陷 #2（中等 / P2）：`/api/messages` 与 `/api/chat/history` 鉴权行为与其他接口不一致

- **文件**：`backend/app/api/routes/profile.py:33`、`backend/app/api/routes/chat.py:43`
- **现象**：`test_authz_e2e.py` 断言 `GET /api/messages?user_id=<他人>` 与 `GET /api/chat/history?user_id=<他人>` 应返回 **403**，实际返回 **200**（且返回的是**当前用户自己的数据**，未泄露他人数据）。
- **对比**：`/api/diagnose`、`/api/notes`、`/api/profile/summary`、`/api/achievements` 等使用 `require_student_user`，该依赖显式拒绝 `user_id` 查询参数（403）；而上述两个接口使用宽松的 `current_session_user`，忽略该参数。
- **影响**：不构成数据泄露（响应数据归属正确），但**防御策略不一致**——攻击者可探测到接口对 `user_id` 参数的宽容行为；且 E2E 回归测试失败，说明安全契约未完全落实。
- **修复建议**：统一为 `require_student_user` 或在两个路由中显式拒绝 `user_id` 查询参数。

---

## 五、观察项（非缺陷，建议改进）

| # | 内容 | 说明 |
|---|---|---|
| 1 | `GET /api/notes/{note_id}` 未实现 | 返回 405，前端仅依赖列表接口，无功能影响 |
| 2 | `requirements-dev.txt` 未声明 pytest | 本项目测试用 unittest/独立 `__main__` 可运行，但若团队期望 pytest 工作流需补充 |
| 3 | StarletteDeprecationWarning：TestClient 建议改用 httpx2 | 依赖升级提示，无功能影响 |
| 4 | `main.py` 中 `/docs` 手写端点列表与真实路由略有出入（如 knowledge-graph、resources 实为需登录接口） | 文档准确性问题，建议核对 |

---

## 六、测试数据清理

本次测试创建的全部临时账号（11 个）与关联数据已从数据库清理，生产数据（14 个原始账号中的 4 个有效账号、990 道题目）未受影响。测试期间临时上传的文件已随账号删除。

---

## 七、结论与建议

1. **可发布性**：核心学习/教师/智能体功能与安全基线通过测试，但 **缺陷 #1（迁移）必须在发布前修复**，否则新环境部署将中断。
2. **建议优先修复**：缺陷 #1（P1）→ 缺陷 #2（P2）→ 观察项 #4（文档）。
3. **建议补充**：在 CI 中固定运行 `test_alembic_migrations.py` 与 `test_authz_e2e.py` 作为回归门禁，防止此类问题复发；浏览器 E2E（Selenium）建议在含 Chrome 的环境补充执行。
