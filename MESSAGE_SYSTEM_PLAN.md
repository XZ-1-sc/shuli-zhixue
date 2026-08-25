# 通用站内消息系统优化方案

> 版本：v1.0（2026-08-23）
> 定位：把教师端 AI 方案中的"师生固定线程"升级为**通讯录式通用站内消息系统**——教师 ⇄ 学生、学生 ⇄ 学生三类关系，任意一方可主动选择对象发起会话；支持文本、图片、题目引用；复用现有会话鉴权与未读轮询通道。
> 状态图例：⬜ 未开始 ｜ 🔄 部分完成 ｜ ✅ 已完成

---

## 0. 背景与已确认决策

### 0.1 背景

- 原 `TEACHER_AI_OPTIMIZATION_PLAN.md` §6 设计的是**师生固定对话**（从班级页进入的一对一线程）；
- 现升级为**通讯录式消息系统**：先"选人"再"聊天"，并新增**学生之间互聊**；
- 原计划中的 `teacher_student_messages` 表**作废**，统一并入本方案的消息表；建议发送（advice）同样挂载本系统。

### 0.2 已确认决策（2026-08-23）

| # | 决策 | 结论 |
|---|---|---|
| 1 | 学生互聊范围 | **扩展到跨班**：同一教师名下所有班级的学生可互聊（不同教师的班级不互通） |
| 2 | 教师对学生互聊的可见性 | **完全不可见**，保留私密性（仅存审计元数据，内容不出现在教师任何界面） |
| 3 | 消息内容类型 | 支持**文本 + 图片 + 题目引用** |
| 4 | 内容治理 | **暂不做**（敏感词/广告过滤留待后续） |

---

## 1. 数据模型（统一消息表）

### 1.1 `conversations`（会话）

```sql
CREATE TABLE conversations (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  participant_a BIGINT UNSIGNED NOT NULL,              -- 较小 user_id（规范化，保证 UNIQUE 唯一）
  participant_b BIGINT UNSIGNED NOT NULL,              -- 较大 user_id
  relation ENUM('teacher_student','student_student') NOT NULL,
  last_message_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_conv_pair (participant_a, participant_b, relation),
  KEY idx_conv_last (last_message_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

- 创建会话时按 `min(user_id), max(user_id)` 规范化，`UNIQUE(a, b, relation)` 保证同两人只有一条会话；
- `relation='teacher_student'`：参与者一方为教师；`relation='student_student'`：双方为学生。

### 1.2 `messages`（消息）

```sql
CREATE TABLE messages (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  conversation_id BIGINT UNSIGNED NOT NULL,
  sender_id BIGINT UNSIGNED NOT NULL,
  content TEXT NULL,                                   -- 文本内容（图片/纯引用时可空）
  attachment_ids JSON NULL,                            -- 图片附件 id 列表（uploaded_files）
  question_ref JSON NULL,                              -- 题目引用 {question_id, record_id?, text?}
  is_read TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_msg_conv_time (conversation_id, created_at),
  KEY idx_msg_sender_unread (sender_id, is_read, created_at),
  CONSTRAINT fk_msg_conv FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE,
  CONSTRAINT fk_msg_sender FOREIGN KEY (sender_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

- 图片附件复用现有 `uploaded_files` 表（新增消息图片上传接口）；
- 题目引用 `question_ref`：做题页"把这题发给同学讨论" → 消息带题目上下文。

### 1.3 迁移

- 走 Alembic 新增迁移（`0005_conversations_messages`），备份库验证后升级。

---

## 2. 会话关系与权限边界（安全核心）

| 关系 | 发起方 | 可联系对象 | 归属校验 |
|---|---|---|---|
| 教师 → 学生 | teacher | 自己任教班级的 active 学生 | `class_members(teacher) JOIN classes ON teacher_id=me` |
| 学生 → 教师 | student | 自己所在 active 班级的教师 | `class_members(student) JOIN classes` |
| 学生 → 学生 | student | **同教师名下所有班级**的学生（跨班） | 两学生共享任一 active 班级 |

**跨班互通校验 SQL**（学生 A 能否联系学生 B）：
```sql
SELECT 1 FROM class_members c1
JOIN class_members c2 ON c2.class_id = c1.class_id
  AND c2.student_id = :student_b AND c2.status = 'active'
JOIN classes c ON c.id = c1.class_id
  AND c.status = 'active' AND c.teacher_id IN (
    SELECT DISTINCT teacher_id FROM classes
    WHERE id IN (SELECT class_id FROM class_members WHERE student_id = :student_a AND status='active')
  )
WHERE c1.student_id = :student_a AND c1.status = 'active'
LIMIT 1
```
（语义：存在一条"共享班级"路径，且该班教师也是 A 所在任一班级的教师——同教师网络内互通。）

**教师不可见学生互聊（隐私）**：所有教师视角接口（会话列表/线程/未读）强制 `WHERE relation='teacher_student' AND participant_a/b 含当前教师`；`student_student` 会话**不出现**在教师任何界面。审计：`audit_logs` 仅记录消息创建频次元数据（不做内容）。

---

## 3. 后端接口（全部会话鉴权 + 归属校验）

| 接口 | 权限 | 说明 |
|---|---|---|
| `GET /api/messages/contacts` | 双角色 | **通讯录**：教师返回任教班级学生（按班级分组）；学生返回"我的教师" + "同学"（同教师网络内，跨班，可搜索） |
| `GET /api/messages/conversations` | 双角色 | 会话列表：对方信息/最后一条/未读数（教师视角不含 student_student） |
| `GET /api/messages/conversations/{id}` | 双角色（参与者） | 会话详情 + 分页消息（limit 50 + 滚动加载） |
| `POST /api/messages/conversations/{id}` | 双角色（参与者） | 发消息：`{content?, attachment_ids?, question_ref?}`；校验归属 + 关系类型合法 |
| `POST /api/messages/conversations/start` | 双角色 | 发起会话：`{target_user_id, relation}`（服务端按关系校验边界，建/取会话） |
| `POST /api/messages/conversations/{id}/read` | 双角色 | 标记对方发来的消息已读 |
| `GET /api/messages/unread-count` | 双角色 | 未读私信数（合并进 `notifications/summary` 返回，orb 轮询复用） |
| `POST /api/uploads/message-images` | 双角色 | 消息图片上传（复用 `_normalize_image` 管线，单张 ≤8MB，每题/消息 ≤5 张） |

**通知联动**：发消息同步写 `user_notifications(type='teacher_message' / 'student_message' / 'peer_message')` → 现有 `/api/notifications/summary` 轮询 → orb 未读徽标 + 气泡提醒（三方消息统一走此通道）。

---

## 4. 前端交互

### 4.1 教师端（新页面 `/teacher/messages`）

- `TeacherSidebar` 新增"消息中心"入口（未读红点）；
- `TeacherMessagesView.vue`：
  - 左侧：**会话列表**（按最近时间，头像/姓名/最后一条/未读红点）+ 顶部"**发起新会话**"按钮 → 弹**通讯录**（按班级分组、搜索学生）→ 选人即进入聊天；
  - 右侧：聊天窗（气泡 + 图片 + 题目引用卡片 + 输入框 + 发送）；
- 教师只看到与学生（teacher_student）的会话，看不到学生互聊。

### 4.2 学生端（`SideFeatureView` 消息中心升级）

- 消息中心升级为 **Tab 结构**：`通知`（现有 user_notifications）｜ `与老师`（会话列表 + 通讯录选教师）｜ `同学`（会话列表 + 通讯录选同学，跨班可搜索）；
- 与老师 Tab：教师发送的调整建议（`type='advice'`）以醒目卡片样式展示；
- 同学 Tab：与同学的会话（图片/引用/文本同样支持）。

### 4.3 图片与题目引用

- **图片**：消息输入框附件按钮 → `POST /api/uploads/message-images` → 预览 → 随消息发送（`attachment_ids`）；气泡内渲染图片（缩略图 + 点击放大，复用批改图片灯箱样式）；
- **题目引用**：
  - 做题页/解析卡"发给同学/老师讨论"按钮 → 预填一条带 `question_ref` 的消息 → 选人发送；
  - 消息内渲染**题目引用卡片**（题干摘要 + 知识点 + 点击跳做题页/解析）；
  - 数据权限：被引用题目必须在双方可访问范围（学生引用自己做过/题库可见的题）。

### 4.4 未读与提醒

- 新消息 → 通知表 + orb 徽标（复用现有 60s 轮询）；
- 打开会话/消息中心 → 调 read 接口，未读清零；
- 未读数以 `messages.is_read` 为准（通知表只做提醒，保证跨端一致）。

---

## 5. 涉及文件

| 域 | 新增 | 修改 |
|---|---|---|
| 后端 | `api/routes/messages.py`、`database/models/message.py`（两表）、`services/message_service.py`、Alembic 迁移（0005） | `uploads.py`（message-images）、`notification_service.py`（unread-count 合并）、`notification_service` 通知类型、`api/schemas.py`（消息模型） |
| 前端 | `views/TeacherMessagesView.vue`、`components/ui/MessageComposer.vue`、`components/ui/MessageBubble.vue`、`components/ui/QuestionRefCard.vue`、`components/ui/ContactPicker.vue` | `TeacherSidebar.vue`（入口）、`SideFeatureView.vue`（三 Tab）、`PracticeView.vue`/`ReviewView.vue`（"发给同学/老师"按钮）、`router/index.js` |
| 测试 | — | `scripts/test_messages_api.py`（权限矩阵/收发/图片/引用/未读）、`scripts/test_teacher_browser.py`（消息页视口） |

---

## 6. 实施顺序

```
第一批（数据与后端底座）：
  0005 迁移 → 通讯录/会话/消息/未读接口 + 三类归属校验 → unread-count 合并

第二批（学生端）：
  SideFeatureView 三 Tab + 通讯录（选教师/选同学）+ 聊天窗 + 未读联动

第三批（教师端）：
  /teacher/messages 页面 + 通讯录（选学生）+ 侧栏入口 + 未读红点

第四批（富内容）：
  消息图片上传与渲染 → 题目引用卡片 + 做题页"发给同学/老师"入口

第五批（收尾）：
  建议发送改挂统一消息表（替换原 teacher_student_messages 方案）→ E2E 回归
```

每批完成后：`compileall` + `unittest discover -s backend/tests` + `npm run build` + 教师/学生双角色、1440/390 双视口浏览器回归。

---

## 7. 验收总标准

1. 教师可从任教班级通讯录选任意学生发起会话；学生可从"我的教师"与"同学"（跨班）通讯录选人发起会话；
2. **学生互聊跨班可见**（同一教师网络内），不同教师网络的学生互相联系返回 403；
3. **教师端任何界面不出现学生互聊内容**（会话列表/线程/未读均隔离），学生互聊仅存审计元数据；
4. 文本/图片/题目引用三类消息收发正常，图片走上传管线，引用卡片可跳转；
5. 三方消息统一走 orb 未读提醒，未读数跨端一致；
6. 建议发送（advice）迁移到统一消息表后流程不变（草稿箱 → 发送 → 学生收件箱）；
7. `scripts/test_messages_api.py` 权限矩阵全绿（含越权 403、跨网络 403、教师不可见学生互聊断言）。
