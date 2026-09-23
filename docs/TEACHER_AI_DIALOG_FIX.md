# 教师 AI 出题弹窗修复验收

验收日期：2026-09-23。目标分支：`codex/complete-teacher-portal`；不变更 `main`。

## 原因与修复

原弹窗没有视口高度约束，1366×768 下生成按钮位于纵向 826–868 像素，超出了屏幕；五种题型均没有隐藏按钮的条件。

- 抽出 `TeacherAIQuestionDialog.vue`，标题、底部操作栏固定，中间表单和结果独立滚动。
- 桌面高度不超过视口减 48px，手机不超过视口减 24px；沿用现有浅色与青色主题，样式限定在组件中。
- 保留课程、知识点、五种题型、难度、数量和补充要求；生成期间禁止重复提交，完成后可再次生成。
- 支持 Escape、Tab 焦点约束、关闭后焦点与页面滚动恢复。
- 不更改文件导入、创建班级、删除班级弹窗样式。

## 最小 GitHub 同步范围

远端基线缺少 AI 出题能力，因此除前端外补齐：

- `POST /api/teacher/ai/generate-question`：教师身份校验、请求边界校验、线程化生成。
- 独立生成服务：结构化结果、逐题校验、批内去重、部分成功与失败原因。
- 草稿强制为 `visibility=class`、`publish_status=draft`，保留已有审核编辑及发布路径。
- 来源写入已有 `source_path=teacher-ai/<教师编号>/<题号>`，参考题编号、模型及请求记录在 `question.ai_generated` 审计中；题目和审计在同一事务保存。
- 不新增数据库字段或迁移，不依赖教学智能化迁移；不覆盖本地已有 AI 字段实现或业务数据。
- 模型不可用或无有效结果时返回零成功，不以复制参考题或占位内容冒充生成结果。

未同步语音、教学驾驶舱、知识图谱、备份、缓存或其他未提交功能。

## 验证结果

- 本地完整前端和隔离前端：`npm run lint`、`npm run build` 通过。
- 本地现有后端单元测试：11 项通过。
- 隔离版本后端测试：21 项通过，其中新增生成、权限及事务测试 11 项。
- 隔离后端完整应用导入及 OpenAPI 路由注册通过。
- 两套前端均完成 Edge 153 浏览器测试：
  - 1440×900、1366×768、1280×600、375×667、320×568。
  - 150%/200% 等效浏览器放大：缩小 CSS 视口并提高设备像素比。
  - 每个尺寸逐一切换五种题型；生成前 35 个布局检查，五道结果后再次检查各题型与滚动。
  - 必填为空、正常生成、重复点击、接口失败、零成功、五道结果、再次生成。
  - 键盘焦点、题库筛选、进入审核编辑、导入弹窗、创建班级、删除确认后取消。
  - 按钮边界、中心点命中、标题/内容/底栏无重叠、横向无溢出检查均通过。

测试边界：浏览器接口为模拟响应；后端使用一次性内存 SQL 数据库与模拟模型，验证真实仓储查询、保存与权限逻辑，不写正式业务数据库，也不调用收费模型。本轮未评估真实大模型出题的数学正确性。实际使用仍需配置已有 `LLM_API_KEY` 等模型参数并逐题人工审核。

构建仍有已有 ECharts 大包警告；测试环境有 Starlette/httpx 弃用提示，不阻断上述检查。本修复不升级依赖。

## 复测命令

在仓库根目录，先按项目说明安装现有后端依赖；浏览器测试另需 Selenium 和 Edge。

```powershell
cd frontend
npm ci
npm run lint
npm run build
cd ..
$env:DATABASE_URL = "sqlite+pysqlite:///:memory:"
$env:DOCKER_DATABASE_URL = ""
python -m unittest discover -s backend/tests -v
python scripts/test_teacher_ai_browser.py
# 或检查已部署网关（所有业务接口仍模拟）
python scripts/test_teacher_ai_browser.py --url http://localhost:8080
```

浏览器报告和截图保存在忽略的 `tmp/teacher-ai-browser/` 中，不进入 GitHub。
