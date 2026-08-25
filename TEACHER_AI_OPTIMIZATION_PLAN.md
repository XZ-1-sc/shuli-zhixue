# 教师端 AI 与消息中心优化方案

> 版本：v1.0（2026-08-23）
> 定位：教师端 AI 能力从"页面内嵌孤立卡片"升级为**以小逻为中心的 AI 教学分析工作台**，并新增**教师-学生双向消息中心**，形成"AI 自动分析 → 教师审阅 → 发送学生 → 学生收到执行"的完整教学闭环。
> 状态图例：⬜ 未开始 ｜ 🔄 部分完成 ｜ ✅ 已完成

---

## 0. 背景与已确认决策

### 0.1 现状问题（已核实）

- 班级/学生 AI 解读后端接口已存在，但**前端渲染契约不匹配**：后端返回 `TeachingInsight`（`summary / highlights[] / risks[] / suggestions[]`，字符串数组），前端 `AICard` 只认 `metrics / details / mistakes` 等结构化字段 → **三个数组全部不渲染，卡片只剩一行文字，表现为"点击后无法查看"**；
- AI 结果内嵌在页面里（`TeacherHomeView` / `TeacherStudentDetailView`），无统一入口、不可回溯；
- **无作业级 AI 分析**、**无班级数据分析图表**、**无教师-学生双向消息**。

### 0.2 已确认决策（2026-08-23）

| # | 决策 | 结论 |
|---|---|---|
| 1 | 页面内嵌 AICard | **完全移除**，AI 结果全部在小逻抽屉中弹出 |
| 2 | 作业分析报告触发 | 学生提交作业后**自动生成**摘要推给教师；完整报告教师按需查看 |
| 3 | 班级数据分析图表 | 放**作业详情页 + 班级详情页**，且**精确到每一个学生** |
| 4 | 学习调整建议 | **自动生成** → 存入**班级草稿箱**（每个学生单独一版）→ 教师**手动**发送到学生个人学习收件箱 |
| 5 | 消息中心 | **新增教师-学生双向消息交互**（新表） |

---

## 1. 渲染契约修复（治"无法查看"，先行）

**后端**（`services/teacher_ai_service.py`）新增结构化转卡片方法，接口响应附带 `card` 字段：

```python
def teaching_insight_to_card(insight: TeachingInsight, scope: str) -> dict[str, Any]:
    return {
        "type": "insight",
        "title": "班级学情解读" if scope == "class" else "学生学情解读",
        "summary": insight.summary,
        "details": [
            {"label": "亮点", "value": "；".join(insight.highlights)},
            {"label": "风险点", "value": "；".join(insight.risks)},
            {"label": "建议", "value": "；".join(insight.suggestions)},
        ],
    }
```

- `POST /api/teacher/ai/class-insight` 响应增加 `"card": teaching_insight_to_card(...)`（原 `insight` 字段保留，兼容）；
- 前端统一用 `data.card` 喂给 AICard。

**验证**：学生/班级两种 scope 调用接口，`card` 含完整 details；AICard 渲染出亮点/风险/建议三块。

---

## 2. 交互迁移：AI 结果统一在小逻弹出（完全迁移）

**目标**：教师端所有 AI 分析（班级解读 / 学生解读 / 作业报告 / 图表叙事）点击后**只在小逻抽屉中呈现**，删除页面内嵌 AICard 区块。

**做法**：
1. `XiaoluoAssistant.vue` 的 `handleOpenRequest` 支持 `detail.card` 直投：收到即 `pushProactiveCard(detail.card)` + 打开抽屉（教师端 `assistantRole: "teacher"` 已接好）；
2. 各页面 AI 按钮统一改为：
   ```js
   window.dispatchEvent(new CustomEvent("xiaoluo:open", {
     detail: {
       card: data.card,
       prompt: "请结合这份分析，说明下一步教学重点。",
       autoSend: true
     }
   }));
   ```
3. **删除**以下页面内嵌渲染：
   - `TeacherHomeView.vue`：`teacher-ai-insight-wrap` 区块 + `aiInsight` 状态；
   - `TeacherStudentDetailView.vue`：`teacher-student-ai` 区块（第 14 行附近）+ `aiInsight` 状态；
   - `TeacherAssignmentDetailView.vue`：新增的作业报告同样走小逻，不内嵌。
4. 小逻中保留会话历史 → 教师所有 AI 分析可回溯（历史里可重新展开卡片）。

**验证**：班级/学生/作业三处点击 AI 按钮 → 小逻自动打开显示完整卡片；页面无残留 AICard。

---

## 3. 学习调整建议工作流（班级草稿箱 → 教师审阅 → 发送收件箱）

**流程**：AI 按班级自动为每个学生生成调整建议（草稿）→ 教师进入草稿箱审阅/编辑 → 手动发送 → 建议进入学生个人收件箱（消息中心）→ 学生小逻收到提醒。

### 3.1 新表 `advice_drafts`（随 Alembic 迁移新增）

```sql
CREATE TABLE advice_drafts (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  teacher_id BIGINT UNSIGNED NOT NULL,
  class_id BIGINT UNSIGNED NOT NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  content TEXT NOT NULL,                          -- 建议正文（教师可编辑）
  status ENUM('draft','sent','archived') NOT NULL DEFAULT 'draft',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  sent_at DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_advice_drafts_class_student (class_id, student_id, status),  -- 每学生每班一份未发送草稿
  KEY idx_advice_drafts_teacher_status (teacher_id, status),
  CONSTRAINT fk_advice_drafts_teacher FOREIGN KEY (teacher_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_advice_drafts_class FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE,
  CONSTRAINT fk_advice_drafts_student FOREIGN KEY (student_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

### 3.2 后端接口（`require_teacher`，全部校验班级归属）

| 接口 | 说明 |
|---|---|
| `POST /api/teacher/advice/generate` | 入参 `{class_id}`：对该班**每个学生**调用 `call_llm_json` 生成一版调整建议（数据：学生解读 insight + 最近作业表现），写入 `advice_drafts(status='draft')`；已有未发送草稿的学生跳过（幂等）；返回生成数量 |
| `GET /api/teacher/advice/drafts?class_id=` | 草稿列表（按学生分组，含内容/状态/最近作业表现摘要） |
| `PUT /api/teacher/advice/drafts/{id}` | 教师编辑草稿内容 |
| `POST /api/teacher/advice/drafts/{id}/send` | 发送单个：写 `teacher_student_messages(type='advice')` + 学生 `user_notifications(type='teacher_advice')`，草稿置 `sent` |
| `POST /api/teacher/advice/drafts/batch-send` | 入参 `{draft_ids}`：批量发送选中草稿 |

**前端**：教师端班级详情页新增"建议草稿箱"Tab/区块——列表展示每学生草稿（AI 已生成、可编辑、发送按钮、全选批量发送）；发送成功给 toast 反馈。

**验证**：对演示班级生成草稿 → 每学生一版 → 编辑 → 发送 → 学生端消息中心收到建议 + 小逻收到提醒。

---

## 4. 作业 AI 分析报告（提交后自动生成）

### 4.1 自动摘要（学生提交时触发）

- 在 `assignments.py` 学生提交作业处（已有"学生已提交作业"通知逻辑）：**追加自动摘要**——统计该作业已提交答案的正确率/待批改数/覆盖知识点，写入教师通知 `type='assignment_report'`（`action_url` 指向作业详情），并标记 `assignment_attempts` 有新的分析待查看；
- 纯统计计算，不调 LLM（快、稳），LLM 完整报告按需生成。

### 4.2 完整报告（按需生成）

- 新增 `POST /api/teacher/ai/assignment-report`（`require_teacher`，入参 `{assignment_id}`）：
  - 聚合 `assignment_answers`：整体正确率、按知识点掌握度、错因分布（`mistake_tags`）、**异常题**（正确率 < 40% 的题）、**每个学生的个体摘要**（正确率 + 薄弱知识点）；
  - `call_llm_json` 生成结构化 `AssignmentReport`（`overall / weak_points / at_risk_students / suggestions`）；
  - 响应含 `card`（转 AICard 结构），前端 dispatch 小逻弹出。

**前端**：作业详情页"AI 分析报告"按钮 → 小逻弹出叙事报告；自动摘要通知点开直达。

**验证**：学生提交作业 → 教师收到自动摘要通知；教师点完整报告 → 小逻展示含学生个体与异常题的完整分析。

---

## 5. 班级数据分析图表（作业详情页 + 班级详情页，精确到每个学生）

### 5.1 数据接口（纯统计，无 LLM）

- 新增 `GET /api/teacher/assignments/{id}/analytics`（`require_teacher`）：该作业的分析数据；
- 新增 `GET /api/teacher/classes/{id}/analytics`（`require_teacher`）：班级维度的汇总（近 N 次作业/整体表现）；
- 响应结构（两者同构）：
  ```json
  {
    "accuracy_distribution": [{ "bucket": "90-100", "count": 5 }, ...],
    "knowledge_mastery": [{ "knowledge_tag": "极限", "accuracy": 72.5, "attempts": 40 }, ...],
    "reason_distribution": [{ "reason": "计算失误", "count": 12 }, ...],
    "students": [{ "student_id": 5, "username": "树虫", "accuracy": 68, "attempts": 20,
                   "weak_knowledge": ["导数"], "last_active": "..." }, ...]
  }
  ```

### 5.2 前端组件 `components/teacher/AssignmentAnalytics.vue`（ECharts 已有依赖）

- **正确率分布**：分数段人数柱状图；
- **知识点掌握度**：该作业覆盖知识点 × 正确率条形/热力；
- **错因分布**：饼图；
- **学生个体对比**：每学生正确率条形图（**精确到每一个学生**），行内附薄弱知识点，点击跳转学生详情页；
- 图表区上方小字标注"数据来自真实作答，AI 叙事分析请在小逻查看"。

**放置**：作业详情页（该作业分析）+ 班级详情页（班级汇总分析，含"最近作业表现"下拉切换）。

**验证**：两类页面图表数据与做题记录一致；学生条形可点击跳详情；390px 移动端图表不溢出。

---

## 6. 教师-学生消息中心（双向消息交互）

### 6.1 新表 `teacher_student_messages`

```sql
CREATE TABLE teacher_student_messages (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  teacher_id BIGINT UNSIGNED NOT NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  class_id BIGINT UNSIGNED NULL,                 -- 关联班级（可选，便于归属校验）
  sender_role ENUM('teacher','student') NOT NULL,
  message_type ENUM('chat','advice') NOT NULL DEFAULT 'chat',  -- advice 标记"教师发送的调整建议"
  content TEXT NOT NULL,
  is_read TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_tsm_pair_time (teacher_id, student_id, created_at),
  KEY idx_tsm_student_read (student_id, is_read, created_at),
  CONSTRAINT fk_tsm_teacher FOREIGN KEY (teacher_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_tsm_student FOREIGN KEY (student_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

### 6.2 后端接口

| 接口 | 权限 | 说明 |
|---|---|---|
| `GET /api/teacher/messages` | teacher | 会话列表：按学生分组，含最新消息/未读数/所属班级 |
| `GET /api/teacher/messages/thread?student_id=` | teacher（校验该生在自己班级） | 与某学生的完整对话 |
| `POST /api/teacher/messages/thread?student_id=` | teacher | 教师发消息（`content`，`message_type='chat'`） |
| `GET /api/messages/thread?teacher_id=` | student（校验该教师在任教班级） | 学生视角：与某教师的对话 |
| `POST /api/messages/thread?teacher_id=` | student | 学生回复教师 |
| `GET /api/messages/unread-count` | 双角色 | 未读私信数（供 orb/入口徽标轮询，可与 `notifications/summary` 合并返回） |

**联动**：新私信写入时同步 `user_notifications(type='teacher_message'/'student_message')` → 小逻 orb 未读徽标 + 气泡提示（复用现有主动通知通道）。

### 6.3 前端

- **教师端**：`TeacherSidebar` 新增"消息中心"入口（`/teacher/messages`）→ 新页面 `TeacherMessagesView.vue`：左侧学生会话列表（按班级分组 + 未读红点），右侧聊天式对话窗（支持发送/标记已读）；
- **学生端**：`SideFeatureView` 消息中心扩展为双 Tab：**通知**（现有 `user_notifications` 列表）+ **与老师**（会话列表 + 对话窗，展示教师发送的建议 `advice` 消息并有醒目样式）；
- 学生收到建议消息 → 小逻收到提醒（通知联动）→ 点开小逻/消息中心查看。

**验证**：教师 → 学生 → 教师双向收发；建议消息在收件箱以特殊样式展示；未读数跨端一致；权限隔离（教师只能与任教班级学生会话）。

---

## 7. 涉及文件

| 域 | 新增 | 修改 |
|---|---|---|
| 后端 | `api/routes/teacher_messages.py`、`api/routes/teacher_advice.py`（或并入 teacher_ai.py）、`database/models/message.py`（两新表）、`services/advice_service.py`、`services/assignment_report_service.py`、Alembic 迁移（两表） | `teacher_ai_service.py`（card 转换/student 建议）、`teacher_ai.py`、`teacher_assignments.py`（analytics）、`assignments.py`（提交自动摘要）、`teacher_schemas.py`、`notification_service.py`（unread-count 合并） |
| 前端 | `components/teacher/AssignmentAnalytics.vue`、`views/TeacherMessagesView.vue` | `XiaoluoAssistant.vue`（card 直投）、`TeacherHomeView.vue`、`TeacherStudentDetailView.vue`、`TeacherAssignmentDetailView.vue`、`TeacherClassesView.vue`（草稿箱 Tab）、`TeacherSidebar.vue`（消息入口）、`SideFeatureView.vue`（双 Tab）、`router/index.js` |
| 测试 | — | `scripts/test_ai_features_api.py`（报告/草稿/发送/消息回归）、`scripts/test_teacher_browser.py`（消息页 + 草稿箱视口检查） |

---

## 8. 实施顺序

```
第一批（先治病，最小可用）：
  M1 渲染契约修复 → M2 小逻弹出迁移（班级/学生解读点开可看）

第二批（消息中心，为建议发送打地基）：
  M6 新表 + 接口 + 教师/学生消息页面 + 未读联动

第三批（建议工作流）：
  M3 草稿箱：生成 → 列表 → 编辑 → 发送（衔接 M6 收件箱）

第四批（作业分析）：
  M4 提交自动摘要 → 完整报告（小逻弹出）

第五批（图表）：
  M5 analytics 接口 + AssignmentAnalytics.vue（作业页 + 班级页）
```

每批完成后：`compileall` + `unittest discover -s backend/tests` + `npm run build` + 教师/学生双角色、1440/390 双视口浏览器回归；新表走 Alembic 迁移并在备份库验证。

---

## 9. 验收总标准

1. 教师端任何 AI 入口点击后**小逻立即弹出完整卡片**，页面无内嵌 AICard 残留；
2. 班级/学生/作业三处 AI 解读均可查看（高亮/风险/建议三块齐全）；
3. 学生提交作业 → 教师**自动收到**作业分析摘要通知；完整报告含异常题与**每学生个体**摘要；
4. 班级/作业详情页图表**精确到每个学生**，可点击跳转；
5. 调整建议自动生成 → 草稿箱每学生一版 → 教师编辑/批量发送 → 学生收件箱收到（advice 特殊样式）+ 小逻提醒；
6. 教师-学生双向消息收发、未读数一致、权限隔离（仅任教班级学生）；
7. `test_ai_features_api.py` / `test_authz_e2e.py` 全绿。
