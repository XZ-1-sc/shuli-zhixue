# 删除班级功能实施方案（方案 A）

> 版本：v1.0（2026-08-23）
> 决策：方案 A——有数据班级默认拒绝删除，输入班级名二次确认后可硬删；空班级直接确认可删；与现有"归档"（保留数据）并存。
> 原则：**默认保护学习数据，仅明确二次确认后才允许物理删除**；不破坏现有归档/编辑/导出功能。

---

## 0. 需求与背景

- 现状：教师端只有"归档"（`POST /classes/{id}/archive`，软删除，数据保留），**无删除功能**；
- 外键关系（已核实）：`class_members`、`assignments` 对 `classes` 均为 **ON DELETE CASCADE**——物理删除会级联删除成员关系、作业、作答记录与成绩；
- 目标：提供"删除班级"，默认保护数据，确认后硬删。

---

## 1. 功能设计总览

### 1.1 交互流程（状态机）

```
点击"删除班级"（红色危险按钮）
  │
  ├─ 班级有【进行中作业】(published) ──▶ 409：请先结束作业再删除（与归档一致）
  │
  ├─ 班级【无数据】（0 成员 / 0 作业 / 0 作答）
  │     └─ 确认弹窗（"将永久删除该班级，不可恢复"）→ 确认 → 删除成功
  │
  └─ 班级【有数据】（成员或作业或作答 > 0）
        ├─ 默认拒绝：后端 409 + 提示"班级含 N 名学生、M 份作业、K 条作答，
        │            删除将永久丢失，建议先归档；如确认删除请输入班级名"
        └─ 输入班级名 = 班级名 → 调 DELETE?confirm=true → 级联删除 → 成功
```

### 1.2 规则摘要

| 场景 | 行为 |
|---|---|
| 有 published 作业 | 409，禁止删除 |
| 有成员/作业/作答，未确认 | 409 + 返回数据量，提示归档 |
| 有成员/作业/作答，`confirm=true` 且班级名匹配 | 级联删除 |
| 空班级，确认后 | 直接删除 |
| 非本人班级 | 404（沿用 `_owned_class`） |

---

## 2. 后端实现

### 2.1 接口定义

```python
# backend/app/api/routes/teacher.py 新增

@router.delete("/classes/{class_id}")
async def delete_class(
    class_id: int,
    confirm: bool = Query(default=False),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(_delete_class_sync, int(current["id"]), class_id, confirm)
```

### 2.2 校验顺序与返回（`_delete_class_sync`）

```python
def _delete_class_sync(teacher_id: int, class_id: int, confirm: bool) -> dict[str, Any]:
    with SessionLocal() as db:
        _owned_class(db, teacher_id, class_id)                      # 404：非本人班级

        active = db.execute(
            text("SELECT 1 FROM assignments WHERE class_id=:class_id AND status='published' LIMIT 1"),
            {"class_id": class_id},
        ).first()
        if active:
            raise HTTPException(409, "班级仍有进行中的作业，请先结束作业再删除班级。")

        # 关联数据量统计
        counts = _class_delete_counts(db, class_id)
        has_data = counts["member_count"] > 0 or counts["assignment_count"] > 0 or counts["record_count"] > 0

        if has_data and not confirm:
            raise HTTPException(
                409,
                f"班级含 {counts['member_count']} 名学生、{counts['assignment_count']} 份作业、"
                f"{counts['record_count']} 条作答记录，删除将永久丢失这些数据；建议先归档。"
                "如确认删除，请输入班级名称并再次提交。",
            )

        # 级联删除（外键 CASCADE 自动清理 class_members / assignments / attempts / answers）
        db.execute(text("DELETE FROM classes WHERE id=:class_id AND teacher_id=:teacher_id"),
                   {"class_id": class_id, "teacher_id": teacher_id})
        _audit(db, teacher_id, "class.deleted", "class", class_id, {"confirm": confirm, **counts})
        db.commit()
    return {"deleted": True, **counts}
```

### 2.3 数据量统计 SQL（`_class_delete_counts`）

```python
def _class_delete_counts(db, class_id: int) -> dict[str, int]:
    member_count = db.execute(
        text("SELECT COUNT(*) FROM class_members WHERE class_id=:class_id AND status='active'"),
        {"class_id": class_id},
    ).scalar_one()
    assignment_count = db.execute(
        text("SELECT COUNT(*) FROM assignments WHERE class_id=:class_id"),
        {"class_id": class_id},
    ).scalar_one()
    record_count = db.execute(
        text("""
            SELECT COUNT(*) FROM practice_records pr
            JOIN class_members cm ON cm.student_id = pr.user_id AND cm.status='active'
            WHERE cm.class_id = :class_id
        """),
        {"class_id": class_id},
    ).scalar_one()
    return {"member_count": int(member_count or 0),
            "assignment_count": int(assignment_count or 0),
            "record_count": int(record_count or 0)}
```

> 说明：`practice_records.assignment_id` 对 `assignments` 是 `ON DELETE SET NULL`（作答记录本身保留，仅作业关联清空）；`assignment_questions/attempts/answers` 随 `assignments` CASCADE 删除。这是 MySQL 外键已配置的行为，无需手动清理。

### 2.4 边界情况

| 情况 | 处理 |
|---|---|
| 已归档班级（`status='archived'`） | 不在活跃列表展示，本次不提供删除入口（数据保留）；后续可加"已归档班级管理"再覆盖 |
| 并发删除（两人同时操作） | `DELETE WHERE teacher_id` 幂等；第二次执行删除 0 行，`_owned_class` 先 404 |
| `confirm=true` 但班级名不匹配 | 班级名校验放**前端**（后端不存班级名二次校验，见 §3.2），后端以 `confirm` 为硬删开关；如需后端兜底，可给请求体加 `name` 字段并校验 `row["name"] == name`（可选加固） |

---

## 3. 前端实现

### 3.1 按钮入口（`frontend/src/views/TeacherClassesView.vue`）

班级详情页头部操作区（第 35 行 `teacher-row-actions`），在"归档"旁新增：

```html
<button class="danger" type="button" @click="openDeleteConfirm">删除班级</button>
```

样式沿用 `.danger`（红色）；若需更醒目可加 `.is-delete` 变体（描边红 + 红字）。

### 3.2 确认弹窗（含输入班级名）

现有 `requestConfirmation`（`services/confirm`）不支持输入框，**删除确认用页面内局部弹层**（复用 `teacher-modal` 样式）：

```html
<div v-if="deleteOpen" class="teacher-modal-backdrop" @click.self="closeDeleteConfirm">
  <form class="teacher-modal" @submit.prevent="submitDelete">
    <header><div><small>危险操作</small><h2>删除班级「{{ detail.class.name }}」</h2></div>
      <button type="button" aria-label="关闭" @click="closeDeleteConfirm">×</button></header>
    <p class="teacher-delete-warning">
      该班级含 <b>{{ deleteCounts.member_count }}</b> 名学生、<b>{{ deleteCounts.assignment_count }}</b> 份作业、
      <b>{{ deleteCounts.record_count }}</b> 条作答记录。删除后<b>永久丢失、不可恢复</b>。
    </p>
    <p v-if="deleteNeedsName" class="teacher-delete-hint">请输入班级名称「{{ detail.class.name }}」以确认删除：</p>
    <input v-if="deleteNeedsName" v-model.trim="deleteName" :placeholder="detail.class.name" required />
    <p v-if="deleteError" class="teacher-form-message is-error">{{ deleteError }}</p>
    <footer>
      <button type="button" @click="closeDeleteConfirm">取消</button>
      <button class="danger" :disabled="deleting || (deleteNeedsName && deleteName !== detail.class.name)" type="submit">
        {{ deleting ? "删除中…" : "永久删除" }}
      </button>
    </footer>
  </form>
</div>
```

### 3.3 交互逻辑（`TeacherClassesView.vue` script 新增）

```js
const deleteOpen = ref(false);
const deleteName = ref("");
const deleteNeedsName = ref(false);
const deleteCounts = ref({ member_count: 0, assignment_count: 0, record_count: 0 });
const deleteError = ref("");
const deleting = ref(false);

async function openDeleteConfirm() {
  deleteOpen.value = true; deleteError.value = ""; deleteName.value = "";
  // 先探测数据量（GET 详情已含 student_count；作业/作答量由后端 409 返回或新加探测接口）
  deleteCounts.value = { member_count: detail.value.student_count || 0, assignment_count: 0, record_count: 0 };
  deleteNeedsName.value = false;
}

async function submitDelete() {
  if (deleting.value) return;
  deleting.value = true; deleteError.value = "";
  try {
    await apiDelete(`/api/teacher/classes/${selectedClassId.value}`, { confirm: deleteNeedsName.value });
    selectedClassId.value = null; deleteOpen.value = false;
    await loadClasses();
    // toast: "班级已删除"
  } catch (error) {
    if (String(error.message).includes("请输入班级名称")) {
      // 后端 409 提示有数据 → 前端切换为"输入名称"模式，再次提交带 confirm=true
      deleteNeedsName.value = true;
      // 从错误文案解析数据量更新 deleteCounts（可选）
      deleteError.value = "";
    } else {
      deleteError.value = error.message;
    }
  } finally { deleting.value = false; }
}
```

> 交互闭环：首次点击删除 → 无 confirm 提交 → 后端 409（含数据量提示）→ 前端收到含"请输入班级名称"的错误 → 弹窗切换为输入模式 → 输入班级名 → 再次提交 `confirm=true` → 删除成功。空班级则首次提交即成功（后端 has_data=false 直接删）。

### 3.4 错误处理与成功反馈

- 409"进行中作业"：弹窗内显示错误文案，保留弹窗；
- 409"含数据"：切换输入模式（见上）；
- 404（班级已被删/非本人）：toast 错误 + 关闭弹窗 + 刷新列表；
- 成功：`loadClasses()` 刷新 + toast"班级已删除"（复用现有 `services/toast`）。

---

## 4. 涉及文件

| 域 | 文件 | 改动 |
|---|---|---|
| 后端 | `backend/app/api/routes/teacher.py` | 新增 `DELETE /classes/{id}` + `_delete_class_sync` + `_class_delete_counts` |
| 前端 | `frontend/src/views/TeacherClassesView.vue` | 删除按钮 + 确认弹窗（含输入模式）+ `submitDelete/openDeleteConfirm` 逻辑 |
| 前端 | `frontend/src/teacher.css`（或该视图 scoped） | `.teacher-delete-warning` / `.teacher-delete-hint` / 删除按钮醒目样式 |
| 测试 | `scripts/test_teacher_api_managed.py` 或新增 `scripts/test_class_delete.py` | 删除场景回归（见 §5） |

---

## 5. 验证方案

**接口级（pytest/脚本，需数据库）**：
1. 建临时班级（无数据）→ DELETE 无 confirm → 200，班级消失；
2. 建班级 + 加入学生 + 布置作业 → DELETE 无 confirm → **409** 且文案含三项数据量；
3. 同上 → DELETE?confirm=true → 200；`classes`、`class_members`、`assignments` 均无残留；`practice_records.assignment_id` 已置 NULL 且记录保留；
4. 有 published 作业 → DELETE → 409"请先结束作业"；
5. 教师 B 删教师 A 的班级 → 404；
6. 删不存在的班级 → 404。

**页面级（`scripts/test_teacher_browser.py` 扩展）**：
- 有数据班级：点删除 → 弹窗显示数据量 → 不输名字按钮禁用 → 输入正确名字 → 删除成功列表刷新；
- 输错名字 → 按钮禁用/提交被拦截；
- 空班级：直接确认删除成功；
- 1600×1000 / 430×900 双视口弹窗无溢出。

---

## 6. 验收标准

1. 教师可删除**自己创建的空班级**（确认后直接删）；
2. 有数据班级**默认拒绝**（409 + 数据量提示），输入班级名二次确认后可删；
3. 有进行中作业的班级禁止删除（提示先结束作业）；
4. 删除后级联清理成员/作业/作答关联，`practice_records` 作答记录保留（assignment_id 置 NULL）；
5. 非本人班级无法删除（404）；
6. 归档功能不受影响，归档/删除按钮并存且语义清晰（归档=保留数据，删除=永久移除）；
7. 接口与页面回归脚本全绿。
