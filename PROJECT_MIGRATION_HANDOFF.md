# 项目迁移交接文档

## 当前目标

项目已从“行测智脑”迁移为“数理智学：大学数学智能学习系统”。

核心定位不变：教学辅助智能体系统，负责诊断薄弱点、生成学习规划、推荐练习、做题解析和错题复盘。

## 当前技术栈

- 后端：FastAPI
- 数据库：MySQL `math_brain`
- 前端：Vue 3 + Vite + Vue Router + Pinia + ECharts
- 网关：Docker Compose + Nginx
- 本地统一入口：`http://localhost:8080`

## 已完成

- 备份旧 `xingce` 数据库，备份文件位于 `backups/`。
- 删除旧 `xingce` 数据库并创建 `math_brain`。
- 导入数学题库 680 道，覆盖选择题、填空题、计算题、证明题、综合题。
- 建立 4 个学习阶段、10 门课程、57 个知识节点。
- 生成数学数据文件：
  - `data/math_questions.csv`
  - `data/math_knowledge_graph.json`
  - `data/source_attributions.json`
  - `data/math_import_report.json`
- 后端接口已切换到数学域：
  - `/api/stages`
  - `/api/courses`
  - `/api/knowledge-graph`
  - `/api/question-types`
  - `/api/practice/random`
  - `/api/practice/submit`
  - `/api/diagnose`
  - `/api/recommend`
  - `/api/study-roadmap`
  - `/api/review/wrong-questions`
  - `/api/chat`
- 登录注册已适配新 `users` 表。
- 前端已改为 Vue 版独立页面：
  - `/` 学习中控台
  - `/practice` 做题训练与解析
  - `/roadmap` 完整学习规划
  - `/knowledge` 知识图谱
  - `/review` 错题复盘
- Docker `gateway` 已改为构建 Vue 产物并用 Nginx 提供。
- GitHub Actions 已改为构建 Vue 前端和 Docker backend/gateway 镜像。

## 重要注意

- `backend/.env` 不要提交。
- `backups/` 不要提交。
- `tmp/sources/webwork-opl/` 不要提交。
- 当前用户表为空，需要重新注册测试账号。
- 本地 `backend/.env` 的 `DATABASE_URL` 应指向 `math_brain`。

## 后续建议

1. 启动后端和前端，浏览器实测注册、登录、做题、提交解析、知识图谱和小逻对话。
2. 根据页面截图继续微调 UI 细节，尤其是移动端和小屏布局。
3. 为关键接口补最小测试用例。
4. 如果要继续外网演示，使用 Docker 入口 `http://localhost:8080` 加 Cloudflare Tunnel。
5. 推送 GitHub 前执行 secret scan，确认 `.env`、备份和临时题源未进入提交。

## 2026-07-15 进度补充：UI 层级、中文题库与侧边功能

- 首页侧栏入口已从 `href="#"` 改为真实 Vue Router 路由：
  - `/messages`
  - `/profile`
  - `/achievements`
  - `/resources`
  - `/notebook`
  - `/settings`
- 新增统一侧边功能页组件 `frontend/src/views/SideFeatureView.vue`：
  - 消息中心：展示任务、复盘、小逻建议和系统通知。
  - 学习档案：展示阶段目标、练习次数、正确率、薄弱课程、最近记录。
  - 成就徽章：根据做题量、正确率、错题回炉、证明题、模拟练习生成徽章状态。
  - 资源中心：按阶段和课程展示讲义、专项练习、路线和项目资源。
  - 笔记本：支持新增、编辑、删除用户笔记。
  - 设置中心：支持保存目标阶段、目标课程、每周学习时长和目标日期。
- 新增后端接口：
  - `GET /api/messages?user_id=`
  - `GET /api/profile/summary?user_id=`
  - `GET /api/achievements?user_id=`
  - `GET /api/resources?stage=&course=`
  - `GET /api/notes?user_id=`
  - `POST /api/notes`
  - `PUT /api/notes/{note_id}`
  - `DELETE /api/notes/{note_id}?user_id=`
- 新增数据库表自动初始化逻辑：
  - `user_notes`
  - `user_notifications`
  - `learning_resources`
- 中文题库已补充：
  - 运行脚本：`scripts/seed_additional_chinese_math_questions.py`
  - 当前中文演示题源共 120 题。
  - 五类题型分布：选择、填空、计算、证明、综合各 24 题。
- 抽题策略已调整：
  - `/api/practice/random` 和 `/api/mock-exam` 默认只从 `数理智学中文演示题库` 抽题。
  - 旧 WeBWorK 英文题源保留在数据库中，但不进入普通练习、今日练习、模拟考试默认题池。
- UI 层级已调整：
  - 首页阶段卡标题和保存按钮分层，避免按钮压住标题或文字竖排。
  - 左侧菜单降低发光强度，增加 hover 反馈。
  - 小逻入口改为全局固定助手按钮，不再只出现在首页。
- 已验证：
  - `python -m compileall -q backend scripts` 通过。
  - `npm run build` 通过。
  - `docker compose config --quiet` 通过。
  - `docker compose build backend gateway` 通过。
  - `docker compose up -d backend gateway` 已重启新版容器。
  - `http://localhost:8080/api/health` 返回正常。
  - `http://localhost:8080/api/practice/random?limit=5` 返回题源只包含中文演示题库。
  - 新路由 `/messages`、`/profile`、`/achievements`、`/resources`、`/notebook`、`/settings` 均能通过网关返回前端页面。

## 2026-07-15 进度补充：新账号空状态与知识图谱优化

- 新账号已改为严格真实数据驱动：
  - `/api/diagnose` 无做题记录时返回 `recent_record_count: 0`、`course_scores: []`、`weak_points: []`、`radar: []`。
  - `/api/recommend` 无做题记录时返回空任务列表，不再生成假今日任务。
  - `/api/messages`、`/api/profile/summary`、`/api/achievements`、`/api/notes` 不再为新用户自动写入个人默认数据。
  - 新用户成就徽章全部为未解锁，注册账号本身不算学习成就。
- 首页已适配空状态：
  - 无记录时显示“尚未首测”、0 题、0.0 小时、0% 进度。
  - 今日练习、雷达图、薄弱课程均显示首测引导，不再展示模拟进度或假薄弱点。
  - `RadarChart` 已移除默认假雷达值，空数据时显示占位提示。
- 知识图谱已改为真实接口驱动：
  - `/api/knowledge-graph` 支持按 `user_id` 返回节点掌握状态。
  - 常见英文知识点已做中文映射；未映射的纯英文知识点在展示层过滤，不再显示“待整理知识点”堆叠。
  - 图谱页使用 ECharts graph 渲染真实“阶段 → 课程 → 知识点”结构，支持阶段筛选、课程筛选、搜索、缩放、重置和节点点击详情。
  - 无做题记录时，错题复盘、薄弱热力图、恢复训练均显示空状态。
  - 知识图谱页已移除页面内重复的小逻入口，只保留全局小逻按钮。
- 已验证：
  - `python -m compileall -q backend scripts` 通过。
  - `npm run build` 通过。
  - `docker compose config --quiet` 通过。
  - `docker compose build backend gateway` 通过。
  - `docker compose up -d backend gateway` 已启动新版容器。
  - 测试空用户 `user_id=3`：诊断、推荐、消息、档案、成就、笔记均为空状态。
  - `/api/knowledge-graph?user_id=3` 返回 55 个中文展示节点、51 条关系，未发现常见英文标签泄漏。
  - 已用浏览器截图检查首页与知识图谱页，首页无假数据，图谱节点集中在画布内且无重复“待整理知识点”。

## 2026-07-18 进度补充：统一账号入口、本科课程题库与响应式修复

- 统一账号入口已完成：
  - 新增 `frontend/src/components/UserAccountButton.vue`，未登录显示“登录 / 注册”，登录后显示用户名并提供退出菜单。
  - Pinia 用户仓库新增全局 `authVisible`、`openAuth()`、`closeAuth()`，所有路由共用同一登录注册弹窗。
  - 首页、知识图谱、完整规划、做题、错题复盘和侧边功能页均已接入统一账号组件。
  - 规划页不再把未登录用户显示为“张同学”。
  - 登录弹窗新增关闭按钮、点击遮罩关闭和 `Esc` 关闭，并完成手机视口适配。
- 浏览器账号实测：
  - `/`、`/knowledge`、`/roadmap`、`/practice`、`/review`、`/messages` 均可打开登录注册弹窗。
  - 已有学生测试账号登录成功，跨路由和刷新后登录态保持，退出登录成功。
  - 临时注册账号验证成功；诊断、推荐、雷达和薄弱点均为空状态；测试后已删除临时账号。
  - 浏览器控制台未发现错误或警告。
- 中文本科数学题库扩充：
  - 新增 `scripts/bachelor_math_seed_data.py` 与 `scripts/seed_bachelor_math_curriculum.py`。
  - 运行命令：`python -m scripts.seed_bachelor_math_curriculum`，脚本可重复执行。
  - 默认中文题池从 120 题扩充到 310 题；选择、填空、计算、证明、综合各 62 题。
  - 覆盖大一至大四共 17 门课程、58 个一级知识标签、62 个细知识节点。
  - 310 道题均包含题干、标准答案、详细解析、关键步骤、常见错误和错因标签；选择题均有 A/B/C/D 与正确答案。
  - 310 道题已全部绑定知识节点；课程别名 `线性代数上/下` 已统一为 `线性代数基础/进阶`。
  - WeBWorK 英文题仍保留为备用题源，不进入默认练习和模拟考试。
- 数据安全：
  - 写入课程和题库前已备份 `math_brain`。
  - 备份文件：`backups/math_brain_before_curriculum_20260718_192719.sql`，大小 934608 字节。
- UI 响应式修复：
  - 1440px 宽度下首页改为两列主区，知识图谱与薄弱课程进入独立第二行。
  - 阶段统计不再逐字竖排；小逻入口与内容区保留 12px 间距。
  - 手机登录弹窗完整位于视觉视口内，左右边缘和关闭按钮均可见。
- 做题评分修复：
  - 填空题和计算题新增标准答案规范化与精确匹配，`0`、`N`、`π` 等短答案不再因字数不足被误判。
  - 证明题、综合题在答案与标准答案完全一致时直接返回 100 分，其余答案继续使用关键词与步骤覆盖度评估。
  - 已用临时账号逐一提交选择、填空、计算、证明、综合题，五类题均正确返回 100 分、解析、关键步骤、常见错误和下一组推荐；测试账号已删除。
- 最终验证：
  - `python -m compileall -q backend scripts` 通过。
  - `npm run build` 通过。
  - `docker compose config --quiet` 通过。
  - Docker Desktop 29.5.3 的 BuildKit 在中文工作目录出现 gRPC header 异常；使用项目兼容方式
    `$env:DOCKER_BUILDKIT='0'; $env:COMPOSE_DOCKER_CLI_BUILD='0'; docker compose build gateway` 构建成功。
  - `backend`、`gateway` 容器均为 `Up`，入口 `http://localhost:8080` 可用。
  - `/api/health`、五类随机练习、20 题模拟考试、17 门课程和知识图谱接口均通过回归。
  - 默认随机题和模拟题全部来自中文题源，抽题响应不会提前泄露答案。
- 登录注册弹窗层级修复：
  - `AuthModal.vue` 已拆分为标题说明、输入区、操作区三个明确层级。
  - 输入框与按钮采用稳定高度，桌面端标题到表单、表单到主按钮均保留 28px 间距；移动端均保留 24px 间距。
  - 登录与注册三输入框状态均完成浏览器截图检查，无重叠、遮挡或弹窗溢出。
  - 学生账号登录回归通过，浏览器未发现 JavaScript 错误。

## 2026-08-12 进度补充：教师端与图片答题优化需求

- 新一阶段需求已记录在 `TEACHER_PORTAL_OPTIMIZATION_PLAN.md`。
- 已确认新增独立教师端，视觉继续沿用当前学生端的深色学术科技风格。
- 教师端核心范围：班级与学生进度、学生只读视角、题库创建/发布、作业组卷/发布、完成情况、图片答案批改。
- 学生做题页将支持图片上传；带图片的主观题进入人工批改状态，不生成虚假自动分数。
- 权限基线：注册时可选择学生或教师；教师注册必须通过管理员发放的邀请码；教师后续只能查看自己班级。
- 当前系统仍使用前端 `user_id` 和本地登录态，正式开发教师端前必须先改为服务端认证和角色授权。
- 页面编码前必须先提供教师工作台、题目/作业发布页样图并等待确认。
- Docker Desktop 已于本次任务启动，`backend`、`gateway` 已恢复运行，`/api/health` 返回 `math_brain` 正常。
- 下一步顺序：数据库备份与增量迁移设计 → 教师端样图 → 权限与班级后端 → 教师页面 → 图片上传与批改 → 全流程测试。

## 2026-08-12 进度补充：独立统一认证页与双角色注册

- 已按确认样图实现独立 `/auth` 登录注册页，替换原全局认证弹窗。
- 登录和注册均提供明确的“学生 / 教师”双身份分段选择。
- 学生账号登录后进入学生端 `/`；教师账号登录后进入教师端 `/teacher`。
- 教师注册允许在统一注册页选择，但必须通过服务端教师邀请码验证。
- 本机教师邀请码保存在未提交的 `backend/.env`；示例配置只保留空值，不会向 GitHub 提交真实邀请码。
- 数据库已增量增加 `users.role`、`idx_users_role_status` 和 `teacher_profiles`，现有账号全部保留为学生。
- 数据库备份：`backups/math_brain_before_auth_roles_20260812_140100.sql`，大小 1099314 字节。
- 新增迁移参考：`scripts/migrate_auth_roles.sql`；新建数据库脚本也已包含角色和教师资料结构。
- Vue 路由加入身份守卫：未登录访问业务页跳到 `/auth`；学生不能进入 `/teacher`；教师不能进入学生业务页。
- `/teacher` 当前提供教师端入口骨架，班级、题库、作业和批改功能仍按 `TEACHER_PORTAL_OPTIMIZATION_PLAN.md` 后续实施。
- 接口回归通过：学生注册、教师邀请码注册、错误邀请码拒绝、身份选择错误拒绝、教师资料自动生成。
- 浏览器回归通过：学生账号进入 `/`，教师账号进入 `/teacher`；双向路由拦截正常；临时测试账号已全部删除。
- 认证页在 1440×1000 和 390×844 视口无横向溢出；教师注册表单在 1000px 高桌面视口完整显示。
- `python -m compileall -q backend scripts`、`npm.cmd run build`、`docker compose config --quiet` 和 Docker 健康检查均通过。

## 2026-08-12 进度补充：学生端图片作答、基础首测与小逻闭环

- 数据安全与迁移：
  - 迁移前备份：`backups/math_brain_before_assessment_20260812_142558.sql`，大小 1100473 字节。
  - 新增迁移脚本：`scripts/migrate_assessment_and_uploads.sql`。
  - 新增 `uploaded_files`、`answer_attachments`、`assessment_sessions`、`assessment_session_questions`。
  - `practice_records` 新增 `assessment` 模式、`review_status`、`teacher_score`、`teacher_feedback`。
- 图片作答：
  - 新增 `POST /api/uploads/answer-images`、`GET /api/files/{file_id}`、`DELETE /api/uploads/{file_id}`。
  - 支持 JPEG、PNG、WebP；每题最多 5 张，单张最多 8 MB。
  - 后端会验证文件、纠正图片方向、重新编码去除元数据，并用随机文件名保存。
  - Docker 新增 `math_answer_uploads` 持久化卷，MySQL 不暴露图片二进制。
  - 含图片的主观题进入 `pending` 待复核状态，不生成虚假自动分数，也不计入错误率或错题本。
- 基础首测：
  - 首页首测入口统一改为 `/practice?mode=assessment&limit=12`。
  - `POST /api/assessment/start` 创建或恢复首测会话，题目按选择、填空、计算、证明、综合五类均衡抽取。
  - 首测严格从 `CURATED-*` 和 `BACHELOR-CN-*` 中文自制题抽取，不把中文前缀包裹英文正文的旧转换题计入默认题池。
  - 答题进度、正确数、错误数、待复核数和未做数全部来自真实提交记录，不再按当前页码伪造。
  - 最后一题完成后生成正确率、优势、薄弱点、7 天计划和下一组练习，并保存到 `learning_plans`。
- 小逻与做题页：
  - 首测完成后全局小逻自动从右侧展开，显示诊断报告、前三天安排、开始第一组练习和完整规划入口。
  - 首测分析同步写入小逻对话历史，规划页优先读取首测生成的真实计划。
  - 做题页草稿纸、收藏、题目笔记、小逻按钮均已连接真实行为。
  - 图片支持选择或拖放、预览、移除；移除后数据库与存储文件同步删除。
  - 做题页在 1680px 以上保留三栏布局，较窄桌面改为顺序布局，390px 手机视口无横向溢出。
- 验证结果：
  - `python -m compileall -q app`、`npm.cmd run build`、`docker compose config --quiet` 通过。
  - 图片上传、受控读取、移除、记录绑定、图片待复核、五类首测、报告、计划和小逻历史接口回归通过。
  - 真实 Edge 浏览器完成五类首测后，小逻自动展开；桌面和 390x844 视口均无横向溢出，控制台和网络请求无异常。
  - 浏览器真实文件选择、图片预览、移除及数据库同步删除通过；所有临时测试账号已清理。
  - `backend`、`gateway` 当前均由 Docker 运行，本机入口为 `http://localhost:8080`。

## 新对话继续提示词

## 2026-08-12 进度补充：教师工作台、班级创建与学生成员管理

- 已将原 `/teacher` 展示骨架替换为真实教师工作台：
  - 班级数、学生数、今日活跃、平均正确率、待批改数量均来自数据库。
  - 已接入最近 7 天学习趋势、课程掌握度、需要关注学生、最近学习动态和班级入口。
  - 无班级时显示明确的创建引导，不再展示不可点击的模块卡片。
- 已新增独立 `/teacher/classes` 班级管理页：
  - 教师可创建班级并选择阶段、课程。
  - 每个班级自动生成 8 位班级邀请码并支持复制。
  - 教师可按用户名添加已注册学生、查看真实练习量/正确率/学习时长/最近活跃，并可移出成员。
  - 本轮测试已创建“高等数学 A 班”并加入学生“树虫”，作为可直接查看的教师端演示数据。
- 已新增增量数据结构：`auth_sessions`、`classes`、`class_members`、`audit_logs`。
  - 迁移脚本：`scripts/migrate_teacher_classes_and_sessions.sql`。
  - 迁移前备份：`backups/math_brain_before_teacher_classes_20260812_171611.sql`，大小 1106448 字节。
- 登录安全已开始从前端 `user_id` 迁移到服务端会话：
  - 登录/注册成功后下发 HttpOnly 会话 Cookie。
  - 新增 `/api/auth/me` 和 `/api/auth/logout`。
  - `/api/teacher/*` 只信任服务端会话，并校验教师角色与班级归属。
  - 学生账号访问教师总览已验证返回 `403`，匿名访问返回 `401`。
- 新增教师接口：
  - `GET /api/teacher/overview`
  - `GET/POST /api/teacher/classes`
  - `GET/PUT /api/teacher/classes/{class_id}`
  - `POST /api/teacher/classes/{class_id}/members`
  - `DELETE /api/teacher/classes/{class_id}/members/{student_id}`
- 验证结果：
  - 使用现有教师账号完成真实登录、创建班级、添加学生、查看统计和成员管理。
  - Python 编译、Vue 构建、Compose 配置、接口闭环、Edge 浏览器桌面/390px 移动端截图检查全部通过。
  - 教师工作台和班级管理均无横向溢出；容器日志没有 `500` 或 traceback。
  - 本机 `http://localhost:8080` 与当前 Cloudflare 公网通道均健康。
- 下一阶段：继续教师题库管理、作业发布、学生作业入口和图片答案批改；侧栏中尚未完成的入口已明确标记“下一阶段”，不再伪装为可用按钮。

```text
继续 D:\「行测智脑」——基于多智能体协作的公考全科个性化导航系统 的大学数学系统迁移任务。
先阅读 PROJECT_MIGRATION_HANDOFF.md。
当前项目已经切换为 FastAPI + MySQL math_brain + Vue 3/Vite 前端。
统一账号入口、严格新账号空状态、310 道中文题库、17 门课程和知识图谱绑定均已完成。
教师端与图片答题需求已记录在 TEACHER_PORTAL_OPTIMIZATION_PLAN.md。
独立统一认证页、学生/教师身份选择、教师邀请码注册和角色路由守卫已经完成。
学生端图片作答、独立基础首测、真实进度、自动诊断、7 天计划和小逻自动展开已经完成。
下一步继续实现教师端班级、题库、作业发布、完成情况和图片批改；图片答题数据结构和待复核状态已经可以复用。
注意不要提交 backend/.env、backups/、tmp/。
```

## 2026-08-12 进度补充：教师端完整教学闭环

- 教师端六个模块均已完成并接入真实数据：
  - `/teacher`：班级、学生、今日活跃、平均正确率、待批改、趋势、课程掌握度和重点关注学生。
  - `/teacher/classes`：创建/编辑/归档班级、复制/重置邀请码、按用户名添加或移出学生、查看成员学情、导出 CSV 名单。
  - `/teacher/students`：跨班级筛选学生、查看个人档案、薄弱知识点、做题记录和作业完成情况，并支持学生端只读预览。
  - `/teacher/questions`：中文公共题池、自建题 CRUD、题干/解析图片、草稿/发布/归档、CSV/XLSX 批量导入、复制公开题为个人草稿。
  - `/teacher/assignments`：按班级布置作业、手动选题或按阶段/课程随机抽取中文题、设置分值/时间/限时/尝试次数/解析策略、发布/关闭/归档及完成详情。
  - `/teacher/review`：文字与图片答案批改、原图旋转/缩放/下载、快捷分数、快捷评语、退回订正和消息通知。
- 学生作业闭环已完成：作业列表、开始/续做、答案自动保存、图片上传、限时自动交卷、多次作答、人工批改、退回订正、成绩与解析查看。
- 权限边界已完成：
  - 使用 HttpOnly 会话 Cookie，不接受前端伪造 `user_id` 作为身份。
  - 学生不能访问教师接口；匿名返回 401；错误角色返回 403。
  - 教师只能访问自己班级、作业、学生和附件；跨教师访问与批改已在端到端测试中验证拒绝。
  - 班级私有题不进入普通随机练习，但已发布作业中的归档题仍可继续作答。
- 题库体验补充：默认教师题池和随机组卷隐藏 WeBWorK 英文备用题，只使用教师题与中文题源；原 990 道题保留不删除。
- 数据与迁移：
  - 增量迁移脚本：`scripts/migrate_teacher_workflow.sql`。
  - 迁移前备份：`backups/math_brain_before_teacher_workflow_20260812_175014.sql`，大小 1114285 字节。
  - 图片继续保存在 Docker 命名卷 `math_answer_uploads`，重建容器不会丢失。
- 自动化验证：
  - `scripts/test_teacher_workflow_e2e.py` 覆盖建班、加学生、名单导出、出题、题目复制、中文随机题池、发作业、图片作答、权限隔离、批改、订正、多次作答与超时交卷。
  - `scripts/test_teacher_browser.py` 使用真实 Edge 覆盖统一教师登录、六个模块、班级创建、学生加入、随机组卷，以及 1600×1000 和 430×900 视口。
  - 两个脚本的账号均通过 `E2E_TEACHER_USERNAME`、`E2E_TEACHER_PASSWORD`、`E2E_STUDENT_USERNAME`、`E2E_STUDENT_PASSWORD` 环境变量传入，仓库不保存密码。
  - Python 编译、`pip check`、Vue 生产构建、Compose 配置、生产依赖审计均通过；浏览器无严重 JS 错误、失败接口或横向溢出。
- 当前运行入口：
  - 本机：`http://localhost:8080`
  - 临时公网：`https://substitute-stated-equilibrium-creek.trycloudflare.com`
  - Quick Tunnel 地址每次重建都可能变化，以 `docker compose logs tunnel` 最新输出为准。
  - Tunnel 已固定使用 HTTP/2，规避当前网络下 QUIC 控制流反复断开的问题。
- 回归测试已清理所有临时班级、题目、作业、上传文件和测试教师；数据库只保留原有演示班级与成员。

## 新对话继续提示词（教师端完成后）

```text
继续 D:\「行测智脑」——基于多智能体协作的公考全科个性化导航系统。
先阅读 PROJECT_MIGRATION_HANDOFF.md，特别是“2026-08-12 进度补充：教师端完整教学闭环”。
当前 FastAPI + MySQL math_brain + Vue 3/Vite 项目已完成教师端六模块、学生作业、图片提交、人工批改、订正、随机中文组卷和服务端会话权限。
先运行 python -m compileall -q backend scripts、npm.cmd run build、docker compose config --quiet，再按新需求继续。
不要提交 backend/.env、backups/、tmp/，不要删除 math_brain 的现有数据。
```

## 2026-08-12 进度补充：题库文件导入与上传试卷组卷

- 教师题库页新增“文件导入”向导，支持 `.pdf`、`.xlsx`、`.xls` 和 UTF-8 `.csv`，单文件最大 15 MB、单次最多 500 道题。
- 导入采用两阶段流程：先解析预览，再确认写库；预览会显示题型、题干、答案、分值、缺失字段、警告和有效/无效数量，无效题不会写入。
- 提供可下载的 Excel 模板，字段覆盖阶段、课程、知识点、题型、A/B/C/D、答案、解析、关键步骤、常见错误、错因标签和分值。
- 文字型 PDF 支持常见的“题号 + A/B/C/D + 答案/解析”以及卷尾统一“答案与解析”结构；扫描图片型 PDF 会明确提示先做 OCR，不会把乱码写入题库。
- 作业编辑页新增“上传试卷”：解析后的有效题会自动发布到教师题库并加入当前作业，同时保留搜索手选、随机中文抽题和逐题改分。
- 重复题保护：题库导入会跳过同一教师的重复题；上传试卷时会复用教师已有的未归档题，草稿会自动发布，不重复创建。
- 作业继续限制最多 100 道题，手选、随机和文件导入均遵守剩余容量。
- 新增接口：
  - `GET /api/teacher/question-imports/template`
  - `POST /api/teacher/question-imports/preview`
  - `POST /api/teacher/question-imports/commit`
- 新增回归脚本：
  - `scripts/test_question_document_parser.py`：离线覆盖 Excel、文字 PDF 和扫描 PDF 拒绝。
  - `scripts/test_question_import_api.py`：覆盖模板、预览、写库、去重与组卷复用，测试数据自动清理。
  - `scripts/test_teacher_browser.py` 已覆盖题库导入弹窗和组卷上传试卷弹窗。
- 运行环境：`pypdf`、`xlrd` 已加入后端依赖；Nginx `client_max_body_size` 已调整为 20 MB；GitHub Actions 会运行离线文件解析回归。
- 验证结果：Python 编译、依赖检查、Vue 构建、Compose 配置、Excel/API 回归、PDF 回归、Edge 桌面与移动端检查均通过。

## 2026-08-20 进度补充：笔记本文件与图片附件

- 笔记本编辑器新增点击选择和拖拽上传，可同时保存文字、图片和学习文件。
- 支持格式：JPEG、PNG、WebP、PDF、Word、Excel、PPT、TXT、Markdown、CSV；单个附件最大 20 MB、单次上传最大 60 MB，每条笔记最多 10 个附件。
- 新增 `POST /api/uploads/note-files`，上传过程校验账号归属、文件扩展名、图片内容和 PDF/Office 文件签名。
- 新增 `note_attachments`，附件与用户笔记真实绑定；增量迁移为 `scripts/migrate_note_attachments.sql`。
- 笔记列表返回附件名称、类型、大小与受控访问地址；图片显示缩略图，文档支持查看或下载。
- 编辑笔记可增加或移除附件，删除笔记会同步删除数据库文件记录和 Docker 上传卷中的实体文件。
- 笔记接口增加当前 HttpOnly 会话账号校验，不能通过修改 `user_id` 读取或改写其他账号笔记。
- 已执行数据库增量迁移；使用“树虫”账号完成图片和 Markdown 上传、纯附件笔记创建、附件移除、列表读取与整条删除回归，清理结果正常。
- 修复侧边功能页在 430px 手机宽度下顶部导航竖排重叠的问题；手机端采用精简顶栏，小逻缩为不遮挡表单的紧凑入口。
- 已验证 `python -m compileall -q backend scripts`、`python -m pip check`、`npm.cmd run build` 和 `docker compose config --quiet` 通过。
- Docker backend/gateway 已重建并运行；经 Nginx 网关完成图片与 CSV 上传、笔记保存、受控下载和删除清理回归。
- 真实 Edge 已完成桌面/430px 移动端布局检查，以及文件选择、上传、保存、笔记卡片展示和删除全过程；无横向溢出或严重控制台错误。
