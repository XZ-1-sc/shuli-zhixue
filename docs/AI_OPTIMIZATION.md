# AI 学习伙伴与教学助手实现说明

## 能力边界

- 学生端小逻支持题目、错题、计划、作业和诊断上下文；资源标识由客户端提交，但数据必须在后端按当前会话用户重新查询并校验归属。
- 教师端小逻只能访问当前教师名下的班级、学生和作答。评语、学情解读、组卷建议均为可编辑草稿，不会自动写成绩、创建作业或发布内容。
- 本轮没有新增运行时依赖或数据表；既有登录、评分、批改、作业和多智能体管线保持原入口。

## SSE 协议

`POST /api/chat` 返回 `text/event-stream`，事件顺序为：

1. `session`：建立或恢复会话；同时保留顶层 `session_id`。
2. `thinking`：`diagnosing/reviewing/responding` 状态。
3. `delta`：文字片段同时提供 `text` 与旧字段 `delta`。
4. `card`：复盘、错因或计划结构化卡片。
5. `action`：导航或提示动作。
6. `[DONE]`：本次流结束。

历史消息仍以纯文本保存，旧会话无需迁移。

## 新增 API

- `GET /api/negotiation/recent`：当前学生最近一次多智能体协商时间线。
- `GET /api/review/analysis`：错因分布与薄弱知识点 Top 5。
- `GET /api/learning-insights`：最近 84 天学习热力与 30 天掌握趋势。
- `POST /api/teacher/ai/grade-comment`：批改评语草稿。
- `POST /api/teacher/ai/class-insight`：班级或学生学情草稿。
- `POST /api/teacher/ai/assignment-suggestion`：组卷建议草稿。

每周学习报告在用户当周首次打开消息中心时按真实记录幂等生成，写入 `user_notifications(type='weekly_report')`；同一用户同一周只生成一条。

## 性能与索引核对

新增读取均有明确时间窗、用户/教师归属条件和结果上限。现有索引已经覆盖本轮核心访问路径：

- `practice_records`：用户 + 作答时间、复核状态 + 时间、作业关联。
- `negotiation_log`：用户 + 时间、会话、发言者 + 消息类型。
- `chat_messages`：用户 + 时间、会话 + 时间。
- `user_notifications`：用户 + 已读状态 + 时间。

本轮不新增重复索引，避免增加练习提交、聊天保存和通知写入成本。ECharts 仍使用已有独立异步 chunk；本轮新增的热力日历和趋势线使用原生 CSS/SVG，不增加包体依赖。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend scripts
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
Set-Location frontend
npm.cmd run build
Set-Location ..
docker compose config --quiet
```
