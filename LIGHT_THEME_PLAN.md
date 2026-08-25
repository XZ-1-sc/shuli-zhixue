# 暖纸感浅色护眼主题整改方案（方案一）

> 版本：v1.0（2026-08-23）
> 目标：将当前"深蓝科技风"整体切换为**暖纸感浅色护眼主题**——低对比、低蓝光，适合长时间刷题学习。
> 原则：**不改变任何项目结构与布局**，纯 CSS 颜色值替换；分两层实施，逐文件覆盖，可随时回滚。

---

## 0. 背景与现状诊断

当前主题为深蓝底 + 亮青点缀：`--bg: #071015`（近黑深蓝）+ 青色光晕/网格背景 + 高亮青 `#64d7e8`。累眼原因：

1. **高对比**：近黑背景 + 亮白文字，瞳孔持续调节；
2. **蓝光刺激**：青色 `#64d7e8` 为高蓝光波段，长时间观看最伤眼；
3. **蓝色渗透深**：全项目共 **502 处**深色/半透明硬编码（`teacher.css` 62、`side-feature.css` 15、`styles.css` 15、`practice.css` 10、`StudentLayout.vue` 5、`auth.css` 5 等），需要分层替换。

**方案一**：暖纸感浅色——米白纸底 + 暖深灰文字 + 低饱和墨青点缀，模拟纸质刷题体验（微信读书/Notion 浅色同思路）。

---

## 1. 配色规范

### 1.1 `:root` 全局变量替换表（`frontend/src/styles.css`）

| 变量 | 现值（深蓝） | 改为（暖纸） | 用途 |
|---|---|---|---|
| `--bg` | `#071015` | `#f6f2e9` | 页面主背景（米白纸） |
| `--bg-2` | `#101820` | `#efe9dd` | 次级背景（暖米） |
| `--surface` | `rgba(22,33,42,.78)` | `rgba(255,255,255,.85)` | 卡片/面板表面 |
| `--surface-strong` | `rgba(246,240,226,.94)` | `rgba(255,255,255,.97)` | 强表面（输入框/弹窗） |
| `--line` | `rgba(220,213,200,.16)` | `rgba(100,90,70,.14)` | 普通边框 |
| `--line-strong` | `rgba(100,215,232,.42)` | `rgba(46,125,140,.35)` | 强调边框（墨青） |
| `--text` | `#f4f0e8` | `#33302b` | 主文字（暖深灰，非纯黑） |
| `--muted` | `#9fb0b3` | `#7d786e` | 次要文字（暖灰） |
| `--paper` | `#f7f0df` | `#fbf7ee` | 纸面强调 |
| `--ink` | `#182026` | `#3a362f` | 纸面文字 |
| `--cyan` | `#64d7e8` | `#2e7d8c` | 主色（墨青，仅点缀/按钮底） |
| `--cyan-soft` | `rgba(100,215,232,.14)` | `rgba(46,125,140,.10)` | 主色浅底 |
| `--amber` | `#f4b84e` | `#b07d1e` | 琥珀（加深保对比度） |
| `--green` | `#70e0aa` | `#3f8f66` | 成功/正确 |
| `--red` | `#f07167` | `#b4554a` | 错误/危险 |
| `--shadow` | `0 24px 90px rgba(0,0,0,.38)` | `0 24px 90px rgba(90,75,50,.14)` | 阴影（柔化） |

### 1.2 `body` 背景（`styles.css`）

现值：深色网格 + 青色光晕 + 深蓝渐变（`linear-gradient(rgba(255,255,255,.025)...)` + `radial-gradient(... #64d7e8 ...)`）。

改为：
```css
body {
  background:
    linear-gradient(rgba(120,100,70,.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(120,100,70,.05) 1px, transparent 1px),
    radial-gradient(circle at 82% 10%, rgba(46,125,140,.06), transparent 34%),
    radial-gradient(circle at 12% 88%, rgba(176,125,30,.05), transparent 26%),
    linear-gradient(135deg, #f6f2e9, #f2ecdf 52%, #f8f4ec);
  background-size: 42px 42px, 42px 42px, auto, auto, auto;
}
```
（网格与光晕大幅减淡并暖化，去除蓝光；`body::before` 装饰公式色 `rgba(244,240,232,.06)` → `rgba(60,55,45,.05)`。）

### 1.3 高频硬编码色值映射表（第二层批量替换）

| 现值（深蓝系） | 出现位置 | 改为 |
|---|---|---|
| `#07131c` `#0a1c27` `#0b1d27` `#081722` `#071722` `#0c222e` `#0d2531` `#091b27` `#0a0d10` | 卡片/面板/抽屉背景 | `#ffffff`（主表面）或 `rgba(255,255,255,.85)` |
| `#101820` `#111923` `#1a2a33` | 次级背景 | `#efe9dd` |
| `#f4f0e8` `#e9f5f5` `#edf5f4` `#dce7e8` `#f2f8f7` | 主文字（原亮白） | `#33302b` |
| `#9fb3b8` `#8da4a9` `#93a8ad` `#a3b5b9` `#7f989e` `#718b91` | 次级文字 | `#7d786e`（弱化可 `#9b948a`） |
| `rgba(145,185,194,.14~.24)` | 边框 | `rgba(100,90,70,.14~.22)` |
| `#64d7e8` `#5ed3e3` `#6ed6e3` `#75cbd8` `#58d0e1` | 青点缀/链接/按钮底 | `#2e7d8c`（hover `#1f5d69`） |
| `rgba(100,215,232,.05~.4)` | 青色光晕/浅底 | `rgba(46,125,140,.06~.35)` |
| `#f4b84e` `#f0b34f` `#f07167` `#70e0aa` | 功能色 | `#b07d1e` `#c98f2d` `#b4554a` `#3f8f66` |
| `rgba(2,8,12,.7~.9)`（modal 遮罩） | 弹窗遮罩 | `rgba(60,55,45,.35)`（浅色遮罩） |

> 原则：**语义替代而非机械替换**——深蓝背景→白色表面；亮白文字→暖深灰；青色只保留为点缀与可点击元素，降低饱和度与亮度。

---

## 2. 分层实施

### 2.1 第一层：全局变量 + body（覆盖约 70%）

1. `styles.css`：`§1.1` 变量替换 + `§1.2` body 背景；
2. 检查 `styles.css` 内部其余硬编码（约 15 处）按映射表替换；
3. 验证：仅此一层后刷新首页，大部分卡片/导航已变浅色。

### 2.2 第二层：硬编码批量替换（按文件、按值）

按出现次数从高到低逐文件处理（每个文件替换后跑一次 `npm run build` 确认）：

| 顺序 | 文件 | 重点 |
|---|---|---|
| 1 | `teacher.css`（62 处） | 教师端全部：sidebar/topbar/modal/批改/图表区 |
| 2 | `side-feature.css`（15 处） | 消息/档案/成就等侧边功能页 |
| 3 | `styles.css` 剩余 + `practice.css`（10 处） | 做题页浮层/草稿纸/alert |
| 4 | 各 view scoped（`StudentLayout.vue` 5 处、`TeacherClassesView.vue`、`knowledge.css`、`roadmap.css`、`DashboardView.vue` 等） | 学生端布局 + 知识图谱 + 规划页 |
| 5 | `auth.css`（5 处） | 登录注册页（含背景公式装饰） |
| 6 | 组件 scoped：`AICard.vue`、`XiaoluoAssistant.vue`、`Toast.vue`、`ConfirmDialog.vue`、`UserAccountButton.vue`、`QuestionImportDialog.vue` | AI 卡片/小逻抽屉/浮层——这些是"深色卡片"重灾区 |

### 2.3 联动项（不能漏）

| 项 | 处理 |
|---|---|
| **ECharts 图表** | `KnowledgeGraphChart.vue`、`RadarChart.vue` 的文字/轴线/背景色：由深色系改为浅色系（文字 `#55503f`、网格线 `rgba(100,90,70,.12)`、节点描边对应墨青）；`HeatmapCalendar.vue` 为原生 SVG 已适配 `props` 数据，仅确认底色 |
| **图片灯箱** | `teacher.css` 的 `teacher-image-lightbox` 深色遮罩 → 浅色遮罩 `rgba(60,55,45,.4)` |
| **登录页背景公式** | `auth.css` `identity-formula` 色 `rgba(177,210,214,.08)` → `rgba(90,75,50,.06)` |
| **选中/激活态** | 青色浅底 `rgba(100,215,232,.1~.14)` → `rgba(46,125,140,.10)`，保证浅底可辨识 |

---

## 3. 涉及文件

| 类型 | 文件 |
|---|---|
| 全局 | `frontend/src/styles.css`、`frontend/src/auth.css` |
| 视图样式 | `frontend/src/styles/views/*.css`（practice/side-feature/knowledge/roadmap/dashboard 等） |
| 全局样式 | `frontend/src/teacher.css` |
| 组件 | `StudentLayout.vue`、`XiaoluoAssistant.vue`、`AICard.vue`、`LightMarkdown.vue`、`Toast.vue`、`ConfirmDialog.vue`、`UserAccountButton.vue`、`QuestionImportDialog.vue`、`KnowledgeGraphChart.vue`、`RadarChart.vue`、`HeatmapCalendar.vue` 及各 view 的 scoped 样式 |
| 不改动 | 所有 `.vue` 的 template/script、路由、接口、后端——**零结构变化** |

---

## 4. 实施步骤

```
1. git 提交当前状态作为回滚点（或确认工作区干净）
2. 第一层：styles.css :root + body 背景 → npm run build → 浏览器目检首页
3. 第二层：按 §2.2 顺序逐文件替换 → 每文件后 build + 目检对应页面
4. 联动项：ECharts / 灯箱 / 登录页 / 选中态
5. 全量验证（§5）→ 提交
```

---

## 5. 验证方案

**静态检查**：
- `grep -i '#0[0-9a-f]\\{4\\}'` 高频深蓝（`#071015 #07131c #0b1d27 #081722 #0a1c27 #071722`）在全前端出现次数 → **降为 0**（或仅剩明确允许值）；
- 对比度抽检：主文字 `#33302b` on `#f6f2e9` ≈ **10.9:1**（远超 WCAG AA 4.5:1）；次要文字 `#7d786e` ≈ 5.6:1 ✅。

**运行时验证**：
- `npm run build` 通过；
- 学生端首页/做题页/知识图谱/复盘/消息中心 + 教师端工作台/班级/题库/作业/批改 + 登录注册页，**双视口 1440×1000 / 390×844** 截图：
  - 无深蓝底色残留；按钮/链接在浅底上可读；卡片层级清晰（白卡 vs 米底）；
  - 弹窗/抽屉/图表正常显示，无文字与背景同色、无对比度过低处；
  - 与改动前截图对比：**布局、间距、元素位置零变化**（纯颜色替换）。

---

## 6. 验收标准

1. 全站背景为暖纸浅色系，无深蓝底色/青色光晕残留（grep 验证）；
2. 文字对比度达标（主文字 ≥ 7:1，次要文字 ≥ 4.5:1）；
3. 所有功能色（正确绿/错误红/琥珀）在浅底上可辨识；
4. 图表（雷达/知识图谱/热力）、AI 卡片、小逻抽屉、弹窗、灯箱在浅色主题下显示正常；
5. 学生端 + 教师端 + 登录页双视口无布局变化、无溢出；
6. `npm run build`、`npm run lint` 通过。

---

## 7. 风险与回滚

- **风险**：硬编码值多（502 处），漏改个别深色块会显得突兀——用"逐文件 + 逐页面目检"控制；ECharts 主题色漏改会导致图表文字看不清——联动项单列清单；
- **回滚**：纯 CSS 改动，`git checkout` 回滚点即可恢复；第二层逐文件提交，每个文件独立回滚；
- **共存**：不引入主题切换机制（用户要求最小改动）；如后续要"深/浅双主题"，变量化改造已在本文档基础上自然扩展。
