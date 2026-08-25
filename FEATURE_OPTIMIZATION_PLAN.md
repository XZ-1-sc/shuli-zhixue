# 数理智学 · AI 赋能学习优化方案（v3.0）

> 版本：v3.0（2026-08-20）
> 定位：与 `OPTIMIZATION_PLAN.md`（问题整改）互补。主线为**"AI 赋能学习"**：小逻 = 学生端 **AI 学习伙伴** + 教师端 **AI 教学助手** + **多智能体协作的指挥台**，并升级为**私人学习助手**——主动开口、时刻陪伴、懂你状态。
> 状态图例：✅ 已实施 ｜ ⬜ 本轮待实施 ｜ 🔮 远期规划

---

## 0. 方案总览

### 0.1 决策记录

**v2.0 已确认并已实施（5 项）**：
1. 小逻界面 = 聊天抽屉 + 丰富卡片流；
2. 教师端 AI = 批改评语 + 学情解读 + 组卷建议；
3. 做题后自动弹复盘卡；
4. 多智能体思考过程可视化；
5. 页面美化范围 = AI 触点 + 首页。

**v3.0 本轮新确认（2026-08-20）**：
1. **主动对话全做**：L2 站内主动 + L3 行为触发 + L4 定时关心；
2. **陪伴感 A 组全做**：A1 早安/晚安播报、A2 orb 状态呼吸、A3 路由感知、A4 行为回溯追问；
3. **B1 情绪智能话术 + B2 连错共情/突破庆祝 + B3 AI 相似题**本轮做；**B4 语音交互下一轮**；
4. **项目级创新 AI 主线四项全做**：错因基因库（三维能力画像）、AI 一页纸周报、教师 AI 工单分流、批改流水线；
5. **防打扰 = 完整护栏**：设置开关 + 同条件每日最多 1 条 + 深夜静默时段。

**设计原则**：小逻的"私人感"来自三层——被动（你问它答）+ 主动（它来找你）+ 陪伴（它"活着"：有状态、有情绪、有记忆）。判断标准：**用户打开页面 10 秒内，小逻应已"说了什么"或"显示它在关注你"**。所有能力复用现有鉴权/仓储/多智能体管线，不新增重型依赖。

### 0.2 状态总表

| 编号 | 内容 | 状态 |
|---|---|---|
| §1 | 小逻学生端基础能力（SSE 协议/复盘卡/上下文/快捷场景/思考可视化） | ✅ 已实施 |
| §2 | 小逻教师端（入口/批改评语/学情解读/组卷建议/权限） | ✅ 已实施 |
| §3 | 小逻 UI（AICard 卡片流/状态动画/思考折叠区） | ✅ 已实施 |
| §4 | 页面美化（AI 触点 + 首页） | ✅ 已实施 |
| §5 | 主动对话与陪伴感（L2+L3+L4 + A 组 + B1~B3 + 护栏） | ⬜ 本轮 |
| §6 | 项目级创新（错因基因库/一页纸周报/教师工单/批改流水线） | ⬜ 本轮 |
| §7 | 远期规划（语音/仪式感/作战室/PWA/排行榜） | 🔮 |

---

## 1. 小逻学生端基础能力 ✅ 已实施

1.1 **SSE 协议扩展**：`session → thinking → delta → card → action → [DONE]`（`chat_service.py` + `client.js` `streamChat` 完整解析）。
1.2 **做题后自动弹复盘卡**：`PracticeView`/`StudentAssignmentView` dispatch `xiaoluo:practice-complete`，小逻自动打开抽屉插入复盘卡。
1.3 **上下文感知**：`ChatContext`（question/wrong/plan/assignment/diagnosis）+ `services/chat_context.py` 权限化组装；各页"问小逻"已接入。
1.4 **快捷场景菜单**：学生 6 项 + 教师 4 项 + 无记录"先做首测"。
1.5 **思考过程可视化**：`negotiation-panel` 折叠区 + `GET /api/negotiation/recent`。

---

## 2. 小逻教师端 ✅ 已实施

- 教师端入口（`assistantRole` 分流，身份"AI 教学助手"）；
- `POST /api/teacher/ai/grade-comment`（评语草案）、`/class-insight`（班级/学生学情解读）、`/assignment-suggestion`（组卷建议），全部"草案后确认"、归属校验 403 隔离；
- 权限边界：教师小逻只能访问名下班级/学生/作答。

---

## 3. 小逻 UI ✅ 已实施

`AICard.vue` 卡片流 + `LightMarkdown.vue` + thinking 状态动画 + 思考过程折叠区 + orb 未读徽标。

---

## 4. 页面美化 ✅ 已实施

做题页/复盘页/规划页/作业页"问小逻"入口、首页 AI 建议卡 + 热力日历（`HeatmapCalendar.vue`，原生 CSS/SVG）、侧栏收敛、`styles/views/` 样式拆分。

---

## 5. 主动对话与陪伴感（本轮 ⬜）

> 目标：小逻从"事件响应"升级为"主动开口 + 时刻陪伴"。分三个机制：**主动通道（L2/L3/L4）**、**陪伴行为（A 组）**、**情绪智能（B1/B2/B3）**。

### 5.1 主动通道

**L2 站内主动（前端通道）**
- 新增 `GET /api/notifications/summary`（会话鉴权）：返回 `{unread_count, latest: {type,title,content,action_url,created_at}}`；
- 前端全局轻量轮询（60s，`App.vue` 挂载时启动，路由守卫复用；仅登录态运行），有新增 AI 通知时：orb 未读徽标 + 气泡提示（"小逻有话对你说"）；点开抽屉自动开口播报 `latest.content`；
- 进阶（可选替换轮询）：`GET /api/push/stream` SSE 长连接，复用现有 SSE 经验；断线自动重连。**MVP 用轮询，简单可靠**。

**L3 行为触发**
- 进入首页：若当日未播报 → 小逻自动开口（见 5.2）；
- 每日计划任务到期（`learning_plans`）→ 生成通知 `type='plan_due'`；
- 做题提交后复盘卡已有 → 增加"小逻追加一句话"（错因一句话点评，LLM 生成，异步写入通知）。

**L4 定时关心（后端任务）**
- 新增独立脚本 `scripts/daily_reminder.py`（**不用 APScheduler 常驻**，避免多副本重复触发；由系统计划任务/Docker sidecar 每日定时调用）：
  - 3 天未学习 → `type='care_inactive'` 温和提醒；
  - 正确率较上周下滑 ≥10% → `type='care_regress'` 共情式关心；
  - 计划到期未完成 → `type='plan_due'` 催办；
  - 23:00 后仍活跃做题 → 次日 `type='care_late_night'` 提醒休息；
- 写入 `user_notifications`（复用现有表与消息中心展示），触发小逻 orb 提示。

### 5.2 A1 早安/晚安播报

- 前端进入首页时按时间段 + `hasRecords` 判定：首次进入当天未播报 → 小逻自动开口（本地模板 + `profile/summary`/诊断数据填充，**不耗 token**；进阶版可 LLM 生成个性化一句）；
- 早安模板："早上好，今天计划是先攻 {focus_course}，昨天 {昨日正确率}，建议先做 {薄弱知识点} 热身"；
- 晚安模板："今天完成 {n} 题，正确率 {p}%，比上周{升/降}，明天建议 {建议}"；
- 播报状态记录在 `user_notifications`（`type='daily_greeting'`，当日查重）。

### 5.3 A2 orb 状态呼吸

- orb 按钮视觉状态机（纯 CSS 类切换，数据来自 `notifications/summary` + `profile/summary`）：
  - 有未读 AI 建议 → 亮青气泡 + 未读数字；
  - 今日已学习 → 绿色呼吸（微光动画）；
  - 3 天未学习 → 橙色"想你了"；
  - 23:00 后 → 暗淡（配合静默时段）；
- 状态计算放前端，服务端只提供数据，不新增轮询接口以外的请求。

### 5.4 A3 路由感知

- `XiaoluoAssistant.vue` 监听 `route.path`，快捷场景菜单按当前页联动：
  - `/knowledge` → 首项变"问这个知识点"（携带当前选中节点）；
  - `/review` → 首项变"帮我看这批错题"（`wrong` 上下文）；
  - `/roadmap` → 首项变"调整本周安排"（`plan` 上下文）；
  - `/teacher/*` → 教师场景（已有）；
- 其余场景保持通用菜单。

### 5.5 A4 行为回溯追问

- 聊天时注入"上次对话后发生了什么"：`chat_context.py` 增加轻量回溯——最近一次会话主题（`negotiation_log`/`learning_plans` 最近更新）+ 计划完成度 + 新做题量；
- 效果示例：用户再次打开小逻，小逻问候语含"上次你说导数薄弱，那组题做了 6 题、正确率 67%，要继续吗？"；
- 由后端组装进 `authorized_context`，前端无感知。

### 5.6 B1 情绪智能话术

- 在 `chat_service.py` 增加话术分级配置（prompt 引导 + 模板）：
  - 鼓励型（进步/连续学习）："比上周快了 2 天，保持这个节奏"；
  - 共情型（下滑/连错）："先别焦虑，我帮你定位是哪块退步"；
  - 督促型（计划逾期/久未学）："知识会遗忘，回来做 5 题热热身"；
- 触发依据：`practice_records` 时间窗聚合（正确率变化、连错、间隔天数），数据现成。

### 5.7 B2 连错共情与突破庆祝

- 同一知识点连错 ≥3 次：提交后复盘卡追加共情句 + "换个角度再讲一次"按钮（触发 `question` 上下文对话）；
- 掌握度首次破 80%（`/api/diagnose` 数据）：庆祝卡片（AICard 样式）+ 小逻喝彩 + 成就徽章联动（`achievements` 已有）；
- 前端 `PracticeView` 提交后按返回数据判断触发，`XiaoluoAssistant` 渲染。

### 5.8 B3 AI 相似题生成

- 后端 `POST /api/practice/ai-similar`（会话鉴权）：入参 `{question_id}`，后端取原题（题干/知识点/题型）→ `call_llm_json` 生成 1-2 道变式题（题干/选项或答案/解析/知识点），返回结构化 JSON；
- **内容安全**：AI 生成题标注"AI 生成，仅供参考"，不写入正式题库；答题不计入诊断统计（`practice_mode='ai_similar'`，`practice_records` 该模式排除出统计）；教师端题库可"收录为草稿"人工审核后入正式库；
- 前端"再练一题"旁增加"AI 出题"按钮，作答流程复用现有提交逻辑（模式标记 `ai_similar`）。

### 5.9 防打扰护栏（完整版）

1. **设置开关**：设置中心新增"小逻主动提醒"（默认开，关闭后：不自动开口、不气泡、orb 仅静态徽标；L2 轮询降级为不打扰）；
2. **频率上限**：同一触发条件（type + user）每日最多 1 条（`user_notifications` 当日查重，已有周报查重可复用模式）；
3. **深夜静默**：23:00-7:00 不生成主动播报/气泡（L4 脚本跳过该时段，前端轮询在该时段只更新静态徽标）；
4. 存储：新增 `user_preferences` 表（user_id, key, value；`notify_xiaoluo` 默认 '1'），Alembic 迁移随本轮加入。

**涉及文件**：`profile.py`/`repositories/profile.py`（summary 接口 + 播报查重）、`repositories/practice.py`（触发聚合）、新 `scripts/daily_reminder.py`、`chat_service.py`/`chat_context.py`（回溯+话术）、新 `api/routes/practice.py`（ai-similar）、`api/schemas.py`、`XiaoluoAssistant.vue`、`App.vue`（轮询）、`StudentLayout.vue`/`SettingsView`（开关）、`models/side.py`（user_preferences）、迁移。
**验证**：新账号无打扰；触发条件各场景各产生 1 条通知；关闭开关后无主动行为；23:00 后无播报；`compileall` + `unittest` + 双视口回归。

---

## 6. 项目级创新（本轮 ⬜）

### 6.1 错因基因库（三维能力画像）

- 后端 `GET /api/profile/ability-map`（会话鉴权）：按 **知识点 × 题型 × 错因**（`knowledge_nodes` × `question_type` × `mistake_tags`）三维聚合 `practice_records`，返回画像：
  ```json
  { "dimensions": ["knowledge","type","reason"],
    "cells": [{ "knowledge":"极限", "type":"计算题", "reason":"计算失误", "count":5, "accuracy":0.4 }],
    "dominant_reason": "计算失误", "advice": "建议先练笔算规范与步骤化草稿" }
  ```
- 前端学习档案页新增"能力画像"视图（表格热力 + 雷达），早安播报/诊断升级复用该数据源；
- 价值：把"诊断"从薄弱点列表升级为可量化画像，是小逻所有个性化话术的数据底座。

### 6.2 AI 一页纸周报

- 周报升级：现有 `weekly_report` 通知基础上，新增"一页纸"模式——`POST /api/review/weekly-digest`（会话鉴权）由 LLM 把本周错题/错因/进展浓缩为结构化摘要（`{stats, mistakes_top3, progress, next_week}`）；
- 前端消息中心周报条目展开显示摘要卡 + "导出"（打印友好 CSS 页面，不引 PDF 库）；
- 与 6.1 画像联动：错因变化写进周报。

### 6.3 教师 AI 工单分流

- 学生问小逻时，若判定为**需教师介入**的问题（作业截止/请假/超纲题/情绪求助）→ 生成工单：`user_notifications(type='ticket_student')` 推送给对应教师（经 `class_members` 找到班主任/任课教师）；
- 教师端消息中心看到工单 → 回复（写回 `chat_messages` 或通知 `type='ticket_reply'`）→ 学生小逻收到回复通知；
- **MVP 边界**：判定用关键词 + LLM 二次确认（`call_llm_json` 输出 `{needs_teacher: bool, reason}`）；不做独立工单表，先复用通知 + 会话；
- 价值：形成"AI 先答、教师兜底"的教学协同闭环，是教师端"AI 助教"概念的自然延伸。

### 6.4 批改流水线

- 批量评语：`POST /api/teacher/ai/grade-comment` 扩展批量模式（入参 `record_ids`，复用单题上下文组装，逐题 `call_llm_json`），前端批改页"为待批改列表批量生成草案"（逐条可编辑保存）；
- 预判需人工复核：新增 `GET /api/teacher/review/flag`（`require_teacher`）：对待批改队列输出标记——图片清晰度过低（Pillow 已有处理能力可算清晰度/分辨率）、空答案、答案与标准答案文本相似度过高（疑似照抄）、超纲题型；批改页按标记排序，教师优先处理"疑似问题"；
- 价值：教师从"逐题看"变为"只看重点"，AI 处理常规项。

**涉及文件**：`repositories/profile.py`/`practice.py`（画像聚合）、新 `api/routes/profile.py` 子接口、`api/routes/review.py`（digest）、`teacher_ai_service.py`（批量/flag）、`teacher_review.py`、`chat_service.py`（工单判定）、`XiaoluoAssistant.vue`、`SideFeatureView.vue`（档案画像）、`TeacherReviewView.vue`、`TeacherHomeView.vue`。
**验证**：画像数据与做题记录一致；周报可导出；工单从学生侧触发、教师侧可见并可回复；批量评语逐条可编辑；flag 标记准确率人工抽检。

---

## 7. 远期规划（🔮 记入文档，不排期）

- **B4 语音交互**：Web Speech API 语音提问 + 播报（下一轮做）；
- **学习仪式感**：每日目标设定→小逻见证达成；专注模式（小逻监督计时 + 鼓励）；
- **多智能体"实时作战室"**：诊断/策略/推荐智能体在画布上依次"工作"的动画（思考可视化的升级版）；
- **个性化记忆**：昵称、早晚学习习惯、讲解风格偏好（详细/简洁）；
- **PWA 化**：离线缓存 + 桌面图标 + 系统通知（L5 载体，"时时刻刻"的移动端入口）；
- **学习故事时间线**：入学至今成长曲线页（周报叙事化）；
- **班级排行榜 + 周目标徽章**：教师端数据现成，运营钩子。

---

## 8. 实施顺序

```
第一批（主动通道，先立"会主动"）：
  5.1 L2 轮询 + notifications/summary → 5.9 防打扰护栏（含 user_preferences 迁移）
  5.2 A1 早安/晚安 → 5.3 A2 orb 呼吸 → 5.4 A3 路由感知

第二批（陪伴与情绪）：
  5.5 A4 行为回溯 → 5.6 B1 情绪话术 → 5.7 B2 连错共情/突破庆祝 → 5.8 B3 AI 相似题

第三批（L4 定时关心）：
  5.1 L4 daily_reminder.py 脚本 + 四种触发场景 + 静默时段

第四批（项目级创新）：
  6.1 错因基因库 → 6.2 一页纸周报 → 6.4 批改流水线 → 6.3 教师工单分流
```

每批完成后：`compileall` + `unittest discover -s backend/tests` + `npm run build` + 学生/教师双角色、1440/390 双视口浏览器回归；涉及新表走 Alembic 迁移并在备份库验证。
