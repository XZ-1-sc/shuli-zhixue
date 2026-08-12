# 大学数学智能学习系统迁移计划书

## 1. 迁移目标

将当前项目从“行测智脑”整体迁移为“大学数学智能学习系统”。项目核心目标不变：通过教学辅助智能体完成学习诊断、阶段规划、练习推荐、做题解析、错题复盘和连续对话辅导。

本轮迁移采用整体替换路线：旧的行测、公考、岗位、分数线、备考方案等业务内容全部下线，保留登录、注册、聊天历史、Docker 网关、GitHub Actions 等通用基础能力。

## 2. 框架路线

首轮不迁移 Vue，不引入 Django 或新的复杂框架。

继续使用当前技术栈：

- 后端：FastAPI + SQLAlchemy + MySQL
- 前端：静态 HTML + CSS + JavaScript + ECharts
- 数据库：MySQL，建议新库名 `math_brain`
- 容器：现有 Docker Compose + Nginx gateway + Cloudflare Tunnel
- 代码仓库：继续使用 GitHub 仓库 `xingce-smartbrain`

选择原因：当前项目已经能通过 Docker 对外访问，登录、注册、小逻对话、做题记录等基础链路已存在。先在原架构上完成数学版可用系统，可以降低改动风险。

## 3. 数据库迁移计划

### 3.1 旧库处理策略

当前旧数据库大概率为 `xingce`。不直接裸删，先备份再替换。

推荐顺序：

1. 导出旧库备份：
   `mysqldump -u root -p xingce > backups/xingce_backup_YYYYMMDD.sql`
2. 新建数学库：
   `CREATE DATABASE math_brain DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;`
3. 在 `math_brain` 中创建新表结构。
4. 更新 `backend/.env` 的 `DATABASE_URL` 指向 `math_brain`。
5. 导入数学知识图谱和数学题库。
6. 后端、前端、Docker 全部验证通过后，再决定是否执行：
   `DROP DATABASE xingce;`

如果你明确要求物理删除旧库，删除动作必须放在备份和验证之后。

### 3.2 新数据库表

保留或重建通用表：

- `users`：用户表，保留注册登录能力
- `chat_messages`：小逻对话历史
- `user_goal_settings`：用户学习目标，例如目标课程、考试日期、每周学习时长

新增或重建数学业务表：

- `math_stages`：学习阶段表，大一到大四
- `math_courses`：课程表，例如高等数学、线性代数、数学分析、概率统计、复变函数等
- `knowledge_nodes`：知识节点表，支持阶段、课程、知识点、细颗粒度标签
- `questions`：数学题目表，支持选择题、填空题、计算题、证明题、综合题
- `practice_records`：做题记录表，记录客观题和主观题提交结果
- `learning_plans`：阶段学习规划表
- `mistake_tags`：错因标签表，例如概念不清、计算失误、证明断链、条件遗漏

### 3.3 数学题库字段

每道题至少包含：

- `id`
- `question_type`：choice / blank / calculation / proof / comprehensive
- `stage`：大一 / 大二 / 大三 / 大四
- `course`
- `knowledge_tag`
- `fine_tag`
- `difficulty`
- `question_text`
- `option_a` / `option_b` / `option_c` / `option_d`
- `correct_answer`
- `standard_answer`
- `analysis`
- `key_steps`
- `common_errors`
- `mistake_tags`
- `source_name`

首批演示题库规模建议 150 到 300 题，题目采用原创样例，开放教育资源只作为课程结构参考。

## 4. 知识体系设计

范围限定：本科阶段高等数学和数学专业四年内课程，不包含研究生及以上内容。

阶段划分：

- 大一：高等数学上、线性代数基础、解析几何、证明方法入门
- 大二：高等数学下、级数、常微分方程、概率论与数理统计
- 大三：复变函数、实变函数、抽象代数、数值分析、偏微分方程基础
- 大四：拓扑学基础、微分几何基础、泛函分析入门、数学建模与综合专题

知识图谱结构：

- 一级：学习阶段
- 二级：课程
- 三级：知识点
- 四级：细颗粒度标签

示例：

```text
大一
  高等数学上
    极限与连续
      等价无穷小
      夹逼定理
      间断点分类
```

## 5. 后端改造计划

### 5.1 需要替换的接口语义

保留路径但替换业务含义：

- `/api/diagnose`：返回数学维度诊断、雷达图分数、薄弱知识点
- `/api/recommend`：返回数学练习任务
- `/api/question-types`：返回数学课程、知识点、题型数量
- `/api/practice/random`：按阶段、课程、知识点、题型随机抽题
- `/api/practice/submit`：提交答案并返回解析、错因、得分、下一步建议
- `/api/chat`：小逻改为数学学习助教

新增接口：

- `/api/study-roadmap`：获取完整阶段学习规划
- `/api/knowledge-graph`：获取数学知识图谱
- `/api/review/wrong-questions`：获取错题复盘列表
- `/api/learning-plans/current`：获取当前用户学习计划
- `/api/learning-plans/select`：保存用户选择的阶段计划

### 5.2 智能体改造

诊断体：

- 输入：用户做题记录
- 输出：薄弱课程、薄弱知识点、错误类型、建议优先级

策略体：

- 输入：诊断结果和当前学习阶段
- 输出：一周学习计划、每日任务、放弃或延后内容

推荐体：

- 输入：策略和薄弱点
- 输出：下一组练习题、错题回炉任务、复习材料方向

小逻：

- 定位：数学学习助教
- 能力：解释错题、提示证明思路、生成学习规划、复盘薄弱点

## 6. 前端页面结构

首页只做入口和概览，所有具体功能进入独立页面。

必须保留的独立页面：

- `index.html`：首页中控台
- `practice.html`：独立做题与解析页
- `roadmap.html`：完整学习规划页
- `review.html`：错题复盘页
- `knowledge.html`：知识图谱页
- `plan.html`：阶段/课程专属训练页

首页内容：

- 顶部导航：用户、当前阶段、目标课程、剩余天数
- 学习阶段选择
- 课程知识图谱概览
- 今日练习入口
- 薄弱板块摘要
- 小逻固定入口

做题页内容：

- 题目区
- 答案输入区
- 提交按钮
- 正确答案
- 详细解析
- 关键步骤
- 常见错误
- 错因标签
- 下一步推荐

规划页内容：

- 大一到大四阶段路线
- 当前阶段周计划
- 每日任务
- 课程优先级
- 已完成任务查看

错题页内容：

- 按阶段、课程、知识点、错因筛选
- 错题详情
- 解析回看
- 重新练习入口

知识图谱页内容：

- 数学知识树
- ECharts 图谱或树图
- 每个节点显示掌握度、题量、错题数

## 7. 执行顺序

第一阶段：计划和准备

- 完成迁移计划书
- 初始化项目迁移交接文档
- 确认数据库删除策略和新库名
- 确认页面样图方向

第二阶段：数据层

- 生成 `data/math_knowledge_graph.json`
- 生成 `data/math_questions.csv`
- 编写 `scripts/create_math_schema.sql`
- 编写 `scripts/import_math_questions.py`
- 备份旧库
- 创建 `math_brain`
- 导入数学数据

第三阶段：后端

- 替换行测业务常量和提示词
- 改造学习接口
- 新增知识图谱、学习规划、错题复盘接口
- 保留登录、注册、聊天历史

第四阶段：前端

- 重写首页为数学学习中控台
- 重写做题页为题目加解析结构
- 重写阶段规划页
- 新增完整规划页、错题页、知识图谱页
- 小逻文案改为数学助教

第五阶段：联调验证

- 本地启动后端
- 浏览器打开前端
- 注册、登录测试
- 随机抽题测试
- 做题提交测试
- 解析展示测试
- 雷达图随记录更新测试
- 小逻对话和历史记录测试

第六阶段：Docker 和 GitHub

- 更新 Docker 配置里的项目名称和文档
- `docker compose config --quiet`
- `docker compose up --build`
- 本机访问 `http://localhost:8080`
- Cloudflare Tunnel 外网访问测试
- 提交 GitHub
- 确认 GitHub Actions 通过

## 8. 测试清单

后端：

- `python -m compileall -q backend scripts`
- `/api/health`
- `/api/login`
- `/api/register`
- `/api/diagnose`
- `/api/recommend`
- `/api/question-types`
- `/api/practice/random`
- `/api/practice/submit`
- `/api/study-roadmap`
- `/api/knowledge-graph`

前端：

- `node --check frontend/static/js/main.js`
- `node --check frontend/static/js/practice.js`
- `node --check frontend/static/js/plan.js`
- 新增页面 JS 全部通过 `node --check`
- 浏览器控制台无 JS error

数据：

- 数学题库字段完整
- 每题有解析
- 每题有阶段、课程、知识点
- 随机抽题能按条件过滤
- 做题记录能写入数据库

Docker：

- `docker compose config --quiet`
- `docker compose ps`
- `http://localhost:8080/api/health`
- 外网临时链接可访问首页

## 9. 风险和处理

旧库删除风险：

- 必须先备份，验证数学库可用后再删除。

乱码风险：

- 所有新文件统一 UTF-8。
- 旧乱码文件重写，不做局部修补。

题库版权风险：

- 不直接抓取商业题库。
- 开放资源只参考课程结构。
- 首批题目以原创演示题为主。

前端迁移风险：

- 首轮不切 Vue，避免框架迁移扩大范围。
- 后续如果需要更复杂状态管理，再单独升级 Vue。

## 10. 当前已发生的改动记录

当前已经新增一个草稿脚本：

- `scripts/build_math_data.py`

该脚本用于生成数学知识图谱和原创演示题库。它尚未接入数据库，也没有执行数据库删除或导入动作。
