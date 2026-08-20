# 数理智学 · 问题整改执行方案

> 版本：v2.0（2026-08-20）
> 适用范围：当前 FastAPI + MySQL math_brain + Vue 3/Vite 代码库
> 原则：**不推倒重来、按阶段整改、每阶段可独立验证、与并行开发严格串行**

---

## 0. 整改总览

### 0.1 整改项与顺序

| 编号 | 整改项 | 优先级 | 核心动作 |
|---|---|---|---|
| 整改 A | 越权漏洞（IDOR）全量修复 | 🔴 P0 | 学生端接口全部改为会话鉴权 |
| 整改 B | 数据层无 ORM / 无迁移 / 运行时 DDL | 🔴 P0 | 引入 ORM + Alembic，删除运行时建表 |
| 整改 C | 后端巨型文件（learning.py 2527 行） | 🟠 P1 | 按域拆分路由 + 仓储层 |
| 整改 D | 多智能体"假协作"（字符串协议） | 🟠 P1 | 结构化输出 + 接回死代码管线 |
| 整改 E | 前端布局重复 + 全局 CSS 失控 | 🟠 P1 | Layout 收敛 + scoped 化 |
| 整改 F | 基础安全加固（限流/注入/Cookie） | 🟡 P2 | 随 A 一并落地 |

### 0.2 执行依赖

```
A（安全）→ B（数据层）→ C（后端拆分）→ D（智能体）
                              ↓
                      E（前端收敛）
F（安全加固）随 A 落地；每阶段同步补测试与回归。
```

- A、B、C 必须串行且最先做：它们触碰同一批文件（`learning.py`、`security.py`）。
- D 与 E 相互独立（不同文件域），可并行。
- 每阶段完成即跑：`python -m compileall -q backend scripts` + `npm.cmd run build` + `docker compose config --quiet` + 接口回归；阶段间以 git commit 为边界。

### 0.3 并发协作约束（重要）

当前 `backend/app/api/routes/learning.py`、`uploads.py` 存在**实时外部修改**（git status 显示 M）。所有整改开工前：

1. 先 `git status` 确认无未提交冲突，先提交/暂存他人改动再动手；
2. 单文件改动尽量一次成型，避免长时占用；
3. 改动不破坏现有接口契约（除非是本次明确要求移除的 `user_id` 参数）。

---

## 整改 A — 越权漏洞（IDOR）全量修复

### A.1 现状（已精确核实）

`assignments.py`、`teacher.py`、`teacher_workflow.py`、`uploads.py` 已全部使用会话依赖；**`learning.py` 是唯一重灾区**，以下接口仍信任前端传入 `user_id` 且无会话校验：

| 接口 | 行号 | 现状 |
|---|---|---|
| `GET /api/diagnose` | 2369 | `user_id: int = Query(default=1)` ❌ |
| `GET /api/recommend` | 2375 | 同上 ❌ |
| `GET /api/study-roadmap` | 2385 | 同上 ❌ |
| `GET /api/review/wrong-questions` | 2391 | 同上 ❌ |
| `GET /api/user-goals` | 2399 | 同上 ❌ |
| `POST /api/user-goals` | 2404 | `GoalRequest.user_id` ❌ |
| `GET /api/messages` | 2409 | `user_id: int = Query(default=1)` ❌ |
| `GET /api/profile/summary` | 2414 | 同上 ❌ |
| `GET /api/achievements` | 2419 | 同上 ❌ |
| `GET /api/chat/history` | ~2328 | `user_id: int = Query(ge=1)` ❌ |
| `GET /api/chat/sessions` | ~2527 | `user_id: int = Query(default=1)` ❌ |
| `POST /api/chat` | 2282 | `ChatRequest.user_id: Field(default=1)` ❌ |
| `POST /api/practice/submit` | 2358 | `AnswerSubmissionRequest.user_id` ❌ |
| `POST /api/assessment/start` | 2124 | `AssessmentStartRequest.user_id` ❌ |
| `GET /api/assessment/{task_id}/report` | 2129 | 需核实，同模式 ❌ |
| `GET /api/notes` / POST / PUT / DELETE | 2431~2466 | ✅ 已校验（样板可复用） |

> 任意登录用户改 `user_id` 参数即可读写他人做题记录、聊天、笔记、目标、档案。

### A.2 后端改造（`learning.py` + `security.py`）

1. `security.py` 新增统一依赖：
   ```python
   def require_student_user(request: Request) -> dict[str, Any]:
       user = current_session_user(request)
       if user["role"] not in {"student", "admin"}:
           raise HTTPException(403, "当前账号没有学生端权限。")
       return user
   ```
2. 对上表所有接口执行：
   - 删除路由签名中的 `user_id` 参数；
   - 追加 `current: dict[str, Any] = Depends(require_student_user)`；
   - `_xxx_sync(user_id, ...)` 调用改为 `_xxx_sync(current["id"], ...)`；
   - 从 Pydantic 请求模型（`ChatRequest`、`GoalRequest`、`AnswerSubmissionRequest`、`AssessmentStartRequest`、`NoteRequest`、`NoteUpdateRequest`）中移除 `user_id` 字段；
   - `/api/practice/random`、`/api/mock-exam`、`/api/resources` 统一加 `Depends(require_student_user)` 防滥用；
   - 内置 `_get_user_exists` 等依赖 user_id 的辅助函数同步收敛。
3. `/api/chat` 会话隔离：`session_id` 归属校验（`chat_messages` 查询强制 `user_id = current["id"]`）。

### A.3 前端同步（精确到文件）

移除以下调用中的 `user_id` 参数（25 处）：

| 文件 | 行号 |
|---|---|
| `views/DashboardView.vue` | 271, 310, 311, 312, 313 |
| `views/KnowledgeView.vue` | 307, 322, 323 |
| `views/ReviewView.vue` | 100 |
| `views/PracticeView.vue` | 400, 505, 523, 582 |
| `views/RoadmapView.vue` | 188 |
| `views/SideFeatureView.vue` | 398, 403, 407, 417, 422, 552, 574, 584 |
| `components/XiaoluoAssistant.vue` | 130, 136, 159 |

`api/client.js` 无需改动（已带 `credentials: "include"`）；`stores/user.js` 的 `userId` getter 保留仅作展示。

### A.4 验证

1. 新增 `scripts/test_authz_e2e.py`：A 学生登录 → 用 B 的 `user_id` 请求 diagnose/chat/notes/messages → 断言 403/401；未登录 → 401；
2. 匿名、学生、教师三账号权限矩阵回归；
3. 结论门槛：**`learning.py` 中不再出现业务 `user_id: int = Query/Field` 入参**（grep 可验证）。

---

## 整改 F — 基础安全加固（随 A 落地）

1. `/api/chat` 频率限制（如 10 条/分钟/用户，`slowapi` 或自研内存计数）；
2. Prompt 注入防护：系统提示词与用户输入隔离，对话上下文对用户输入仅作引用；
3. 教师邀请码：单静态码 → `teacher_invite_codes` 表（多码、可吊销、带使用次数），校验改查表；
4. Cookie：公网 HTTPS 隧道下置 `secure=True`（保留 `SameSite=Lax`、`HttpOnly`）；
5. 上传文件：补充魔数（magic bytes）校验（图片已重编码去元数据）。

---

## 整改 B — 数据层重构：ORM + Alembic + 仓储层

### B.1 目标

消灭"原生 SQL 散落 + 运行时 DDL 兜底"双轨管理，建立可版本化、可回滚的数据层。

### B.2 步骤

1. **ORM 模型**（新目录 `backend/app/database/models/`）：
   ```
   models/
     __init__.py        # 汇总导出，供 Alembic autogenerate 使用
     base.py            # DeclarativeBase + 通用 Mixin（id/created_at/updated_at）
     user.py            # users, teacher_profiles, auth_sessions, audit_logs
     content.py         # math_stages, math_courses, knowledge_nodes, questions, mistake_tags
     learning.py        # practice_records, subjective_practice_records, user_goal_settings,
                        #   user_study_plans, learning_plans, chat_messages, negotiation_log
     side.py            # user_notes, note_attachments, user_notifications, learning_resources
     assessment.py      # assessment_sessions, assessment_session_questions, uploaded_files, answer_attachments
     teaching.py        # classes, class_members, assignments, assignment_questions,
                        #   assignment_attempts, assignment_answers, question_attachments
   ```
   全表清单见附录 A（35 张，已从 `create_math_schema.sql` + 迁移脚本核实）。
2. **Alembic**：
   ```bash
   cd backend && pip install alembic && alembic init migrations
   # env.py 指向 models.Base.metadata + session.py 的 URL 解析逻辑
   alembic revision --autogenerate -m "baseline all tables"
   alembic upgrade head
   ```
   autogenerate 前先 diff 审查，禁止直接对生产库 upgrade；先在备份库验证。
3. **删除运行时 DDL**：
   - `security.py::ensure_auth_sessions_sync` → 表结构进迁移，函数只留查询；
   - `auth.py::_ensure_auth_schema_sync`（探测 role 列/索引/teacher_profiles）→ 全部进基线迁移；
   - `learning.py::_ensure_side_feature_tables_sync`、`_seed_side_feature_data_sync` → 结构进迁移，种子数据改为幂等 seed 脚本；
   - 其余 `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE` 逐一定位删除。
4. **仓储层**（`backend/app/database/repositories/`）：把 `learning.py` 中 `_xxx_sync` 的 SQL 按域搬入，签名统一 `(db: Session, ...)`；路由层 `Depends(get_db)` + `asyncio.to_thread`。
5. **依赖锁定**：`requirements.txt` 固定主版本，生成 lock 文件（或改用 `uv`/`poetry`）；删除未使用的 `langchain`、`langchain-openai`。

### B.3 验证

- 备份库上 `alembic upgrade head` 成功、`alembic downgrade` 回滚成功；全新空库可完整建表；
- 全接口回归（30+ 接口）；
- 结论门槛：**代码中无运行时 DDL；`alembic current == head`**。

---

## 整改 C — 后端路由拆分：消灭上帝文件

### C.1 目标结构（按域，单文件 < 600 行）

```
backend/app/api/routes/
  auth.py            # 保留
  health.py          # /health
  stages.py          # /stages /courses /knowledge-graph /question-types /resources
  practice.py        # /practice/random /practice/submit /mock-exam（评分逻辑迁入 services/scoring.py）
  assessment.py      # /assessment/start /assessment/{id}/report
  diagnosis.py       # /diagnose /recommend /study-roadmap /review/wrong-questions /user-goals
  chat.py            # /chat SSE /chat/history /chat/sessions（LLM 编排迁入 services/chat_service.py）
  profile.py         # /messages /profile/summary /achievements /notes
  uploads.py         # 保留
  assignments.py     # 保留
  teacher.py         # 保留
  teacher_questions.py / teacher_assignments.py / teacher_review.py / teacher_students.py  # 由 teacher_workflow.py 拆出
```

### C.2 步骤（机械、可脚本化）

1. 以整改 B 的仓储层函数为搬运单元，按附录 B 函数归属表移动；
2. 每个新文件保留自己的 `router = APIRouter(prefix="/api", tags=[...])`，`main.py` 的 `include_router` 同步更新；
3. 公共工具（`_json_safe`、`_row_to_question`、`_parse_json_*`、`_display_knowledge_name` 等）迁入 `backend/app/api/utils.py` 或 `services/common.py`；
4. 每拆一个文件立即 `compileall` + 对应接口抽测，不做大爆炸式一次性提交。

### C.3 验证

- 拆分前后 `/openapi.json` 的 paths 键集合完全一致；
- 学生端 6 页面 + 教师端 6 模块浏览器回归；
- 结论门槛：`learning.py` 与 `teacher_workflow.py` 删除，路由按域归位。

---

## 整改 D — 多智能体结构化升级

### D.1 现状问题（已核实）

- 诊断体输出自由文本，协商靠 `"NEED_REDIAGNOSIS" in text` 判断（`negotiator.py:56`）；
- 导航体 `navigator.py` 用正则/关键词从策略文本抠课程、知识点（`_extract_course` / `_extract_knowledge_tag`），脆弱；
- `orchestrator.run_pipeline`、`evaluator.evaluate` 是死代码，`negotiation_log` 无人消费；
- `call_llm` 丢弃 usage 元数据，无成本/延迟观测。

### D.2 步骤

1. **结构化输出**（`backend/app/agents/schemas.py`）：
   ```python
   class WeakPoint(BaseModel):
       stage: str; course: str; knowledge: str
       reason_type: Literal["概念混淆","计算失误","证明思路断点","知识点不会","做题慢"]
       suggestion: str
   class Diagnosis(BaseModel):
       weak_points: list[WeakPoint]   # 1~3 个
       confidence: float              # 0~1
       needs_first_test: bool = False
   class WeeklyPlan(BaseModel):
       focus_course: str; focus_knowledge: str
       daily_hours: float; priority_order: list[str]; give_up_types: list[str]
   class ClarityReview(BaseModel):
       clear: bool; missing: list[str] = []; feedback: str
   ```
2. **LLM 客户端升级**（`llm_client.py`）：
   - 新增 `call_llm_json(messages, schema/model)`：`response_format={"type":"json_object"}` + 系统提示注入 JSON Schema，解析失败重试 1 次并宽松解析降级；
   - 返回 `(content, usage)`，把 tokens/latency 写入新增 `llm_call_log` 表（随整改 B 的迁移）；
   - 保留现有降级回复逻辑。
3. **智能体重写**：
   - `diagnostician.diagnose(records) -> Diagnosis`；
   - `strategist.plan(diagnosis: Diagnosis) -> WeeklyPlan`；
   - `negotiator`：审查体用 `ClarityReview` 结构化判断，重诊断输入用上一版结构化诊断 JSON；
   - `navigator`：LLM 从 `WeeklyPlan` 抽取 `{course, knowledge_tag, difficulty}` 检索条件 → SQL 查询 → 可选 LLM 排序解释；规则路径保留为 LLM 失败兜底；
   - `evaluator.evaluate` 接入：任务/作业提交后自动生成复盘（结构化 `{accuracy, delta, trend}`）。
4. **接回管线**：`/api/diagnose` 调用 `orchestrator.run_pipeline`（串行 LLM 调用走线程池），响应附 `negotiation` 摘要（轮次、是否重诊断、耗时）。
5. **观测**：`llm_call_log` 关联 `conversation_id`。

### D.3 验证

- mock LLM 单元测试：诊断 JSON 非法降级、重诊断触发、协商最多 3 轮；
- 真实接口：`/api/diagnose` 返回结构化 `weak_points`；`/api/recommend` 命中不再依赖措辞；
- 结论门槛：`negotiator.py` 无字符串协议判断；`navigator.py` 无正则抽词；`orchestrator` 被路由引用。

---

## 整改 E — 前端架构收敛

### E.1 现状（已核实）

`DashboardView`、`SideFeatureView` 各自内联 `ref-topbar` + `ref-sidebar`；教师端 `TeacherHomeView`、`TeacherClassesView` 内联 `teacher-topbar`，与 `TeacherPageShell.vue` 重复。

### E.2 步骤

1. **布局收敛**：新增 `components/student/StudentLayout.vue`（顶栏：品牌+主导航+账号区；侧栏：菜单+首测卡），`App.vue` 按 `route.meta.layout` 包 `StudentLayout` / `TeacherPageShell` / 裸渲染（auth 页）；逐页迁移 Dashboard → Roadmap → Knowledge → Practice → Review → SideFeature → 学生作业页，迁移后删除页面内联布局模板与对应样式类。
2. **组件化**：从 `reference.css` / `teacher.css` 抽 `GlassPanel.vue`、`StatCard.vue`、`EmptyState.vue`、`PageHeader.vue`、`ConfirmDialog.vue`、`Toast.vue`（统一错误提示，配合 `api/client.js` 注入）。
3. **CSS scoped 化**（渐进）：组件/视图迁移时同步 `scoped`，共享变量保留在 `:root`；仅被单页使用的全局选择器随迁移删除；最终全局 CSS 只留 reset + 变量 + 布局基础。
4. **工程化**：接入 `eslint` + `eslint-plugin-vue` + `prettier`（package.json 加 `lint` 脚本并进 CI）；`vite.config.js` proxy 目标改环境变量（消除硬编码 `localhost:8000`）；移动端（<768px）侧栏改抽屉、顶栏改底部 TabBar 5 项。

### E.3 验证

- 构建通过 + 6 学生页面 3 教师页面双视口（1440 / 390）视觉回归；
- 结论门槛：**每个视图文件不再包含顶栏/侧栏模板；`grep ref-topbar` 仅剩 Layout 一处；全局 CSS 体积下降 ≥40%**。

---

## 附录 A：数据库表清单（35 张，已核实）

| 域 | 表 |
|---|---|
| 用户/认证 | `users`、`teacher_profiles`、`auth_sessions`、`audit_logs` |
| 内容 | `math_stages`、`math_courses`、`knowledge_nodes`、`mistake_tags`、`questions`、`question_attachments`、`source_attributions` |
| 学习 | `practice_records`、`subjective_practice_records`、`user_goal_settings`、`user_study_plans`、`learning_plans`、`chat_messages`、`negotiation_log` |
| 侧边功能 | `user_notes`、`note_attachments`、`user_notifications`、`learning_resources` |
| 评测/上传 | `assessment_sessions`、`assessment_session_questions`、`uploaded_files`、`answer_attachments` |
| 教学 | `classes`、`class_members`、`assignments`、`assignment_questions`、`assignment_attempts`、`assignment_answers` |
| 新增 | `llm_call_log`（整改 D）、`teacher_invite_codes`（整改 F） |

## 附录 B：`learning.py` 函数归属表（54 个函数 → 目标文件）

- **practice.py**：`_row_to_question`、`_question_select_sql`、`_build_question_filters`、`_random_questions_sync`、`_get_question_sync`、`_tokenize_answer`、`_normalize_math_answer`、`_score_subjective`、`_submit_answer_sync`、`_validate_attachment_ids` 等
- **assessment.py**：`_assessment_question_rows`、`_assessment_payload`、`_pick_balanced_assessment_questions`、`_start_assessment_sync`、`_validate_assessment_question`、`_build_assessment_report_sync`、`_assessment_after_submit_sync`
- **diagnosis.py**：`_recent_records_sync`、`_diagnose_sync`、`_recommend_sync`、`_study_roadmap_sync`、`_wrong_questions_sync`、`_get_goal_sync`、`_save_goal_sync`
- **profile.py**：`_ensure_side_feature_tables_sync`、`_seed_side_feature_data_sync`、`_messages_sync`、`_profile_summary_sync`、`_achievements_sync`、`_resources_sync`、`_notes_sync`、`_validate_note_attachment_ids`、`_sync_note_attachments`、`_remove_note_files`、`_create_note_sync`、`_update_note_sync`、`_delete_note_sync`
- **chat.py**：`_normalize_session_id`、`_save_chat_message`、`_load_chat_context`、`_chat_history_sync`、`_chat_sessions_sync`、`_chat_event_stream`
- **stages.py / common**：`_display_knowledge_name`、`_is_unmapped_english_label`、`_mastery_status`、`_json_safe`、`_parse_json_list`、`_parse_json_object`、`_get_user_exists`、`_stages_sync`、`_courses_sync`、`_knowledge_graph_sync`、`_question_type_counts_sync`

## 附录 C：改动文件总索引

| 整改 | 新增 | 修改 | 删除 |
|---|---|---|---|
| A/F | `scripts/test_authz_e2e.py` | `learning.py`、`security.py`、`auth.py`、前端 7 文件 | — |
| B | `database/models/*`、`migrations/`、`database/repositories/*`、`tests/` | `session.py`、`security.py`、`auth.py`、`requirements.txt`、`llm_client.py` | 运行时 DDL 代码 |
| C | `api/routes/{practice,assessment,diagnosis,chat,profile,stages}.py`、`api/utils.py`、`services/*` | `main.py` | `learning.py`、`teacher_workflow.py` |
| D | `agents/schemas.py`、`services/chat_service.py`、`llm_call_log` 迁移 | 4 个 agent、`negotiator.py`、`orchestrator.py`、`llm_client.py` | — |
| E | `components/student/StudentLayout.vue`、`GlassPanel/StatCard/EmptyState/Toast` 等 | `App.vue`、全部视图、`client.js`、`vite.config.js`、CSS 4 文件 | 各视图内联布局模板 |

---

## 验收总标准（全部整改完成后）

1. `learning.py` / `teacher_workflow.py` 不存在；grep 无业务 `user_id` 入参；
2. `alembic current == head`；代码无运行时 DDL；
3. `pytest` 全绿、`npm run build` 通过、`docker compose config --quiet` 通过、E2E 脚本全绿；
4. 浏览器 1440×1000 / 390×844 双视口无横向溢出、无 JS 报错；
5. 任意用户越权访问他人数据返回 401/403（E2E 固化）。
