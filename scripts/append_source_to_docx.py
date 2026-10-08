"""把源码按既定顺序写入 源码.docx。

空行规则（用户确认）：
  * **文件内部的所有空行全部删除**，每行代码紧密相连
  * **文件之间空一行**（粘贴完 main.py 空一行，再粘贴 session.py）
  * 文档末尾不留空行

格式规则（与文档既有内容一致）：
  * 宋体 / 10.5pt（w:sz=21），无段落样式
  * 仅删除空行，不改动任何代码行的内容与缩进

过滤规则（非必要 / 雷同 / 开源 / 自动生成的一律不写入）：
  * 空文件、仅 __init__ 导出的桩文件、过短的纯容器组件
  * 配置与常量文件、CSS 样式、构建配置
  * 框架通用样板（如 storage 抽象、公共小工具）
"""

from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
WQ = f"{{{W}}}"

# 注册命名空间前缀，避免序列化时产生 ns0: 前缀污染文档
ET.register_namespace("w", W)
for _prefix, _uri in (
    ("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships"),
    ("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"),
    ("a", "http://schemas.openxmlformats.org/drawingml/2006/main"),
    ("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture"),
    ("m", "http://schemas.openxmlformats.org/officeDocument/2006/math"),
    ("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006"),
    ("wps", "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"),
    ("w14", "http://schemas.microsoft.com/office/word/2010/wordml"),
    ("v", "urn:schemas-microsoft-com:vml"),
    ("o", "urn:schemas-microsoft-com:office:office"),
    ("w10", "urn:schemas-microsoft-com:office:word"),
):
    try:
        ET.register_namespace(_prefix, _uri)
    except ValueError:
        pass

DOCX = REPO / "源码.docx"
BACKUP = REPO / "源码.备份.docx"

# 追加顺序：从 learning.py 起，沿用已确认的提交排序
FILES: list[str] = [
    # ---- 数据模型 ----
    "backend/app/database/models/learning.py",
    "backend/app/database/models/teaching.py",
    "backend/app/database/models/intelligence.py",
    "backend/app/database/models/assessment.py",
    "backend/app/database/models/message.py",
    "backend/app/database/models/side.py",
    "backend/app/database/models/revamp.py",
    # ---- 结构化契约 ----
    "backend/app/api/schemas.py",
    "backend/app/api/teacher_schemas.py",
    "backend/app/api/utils.py",
    "backend/app/agents/schemas.py",
    # ---- 核心多智能体 ----
    "backend/app/agents/strategist.py",
    "backend/app/agents/evaluator.py",
    "backend/app/agents/navigator.py",
    "backend/app/agents/diagnostician.py",
    "backend/app/utils/llm_client.py",
    "backend/app/orchestrator.py",
    "backend/app/negotiator.py",
    # ---- 服务层 ----
    "backend/app/services/scoring.py",
    "backend/app/services/ai_profile_service.py",
    "backend/app/services/reminder_service.py",
    "backend/app/services/teacher_analytics_service.py",
    "backend/app/services/assignment_report_service.py",
    "backend/app/services/teacher_experience_service.py",
    "backend/app/services/chat_service.py",
    "backend/app/services/risk_service.py",
    "backend/app/services/advice_service.py",
    "backend/app/services/analytics_service.py",
    "backend/app/services/paper_service.py",
    "backend/app/services/student_ai_service.py",
    "backend/app/services/solution_service.py",
    "backend/app/services/teacher_message_service.py",
    "backend/app/services/teaching_intelligence_service.py",
    "backend/app/services/notification_service.py",
    "backend/app/services/chat_context.py",
    "backend/app/services/message_service.py",
    "backend/app/services/teacher_ai_service.py",
    "backend/app/services/scoring_policy.py",  # 不存在则自动跳过
    # ---- 数据仓储层 ----
    "backend/app/database/repositories/comments.py",
    "backend/app/database/repositories/questions.py",
    "backend/app/database/repositories/chat.py",
    "backend/app/database/repositories/teacher_students.py",
    "backend/app/database/repositories/curriculum.py",
    "backend/app/database/repositories/practice.py",
    "backend/app/database/repositories/stages.py",
    "backend/app/database/repositories/teacher_assignments.py",
    "backend/app/database/repositories/assessment.py",
    "backend/app/database/repositories/profile.py",
    "backend/app/database/repositories/teacher_questions.py",
    "backend/app/database/repositories/diagnosis.py",
    # ---- 接口路由层 ----
    "backend/app/api/routes/health.py",
    "backend/app/api/routes/teacher_analytics.py",
    "backend/app/api/routes/teacher_students.py",
    "backend/app/api/routes/teacher_review.py",
    "backend/app/api/routes/assessment.py",
    "backend/app/api/routes/solutions.py",
    "backend/app/api/routes/comments.py",
    "backend/app/api/routes/teacher_ai.py",
    "backend/app/api/routes/messages.py",
    "backend/app/api/routes/teacher_assignments.py",
    "backend/app/api/routes/teacher_advice.py",
    "backend/app/api/routes/stages.py",
    "backend/app/api/routes/teacher_messages.py",
    "backend/app/api/routes/chat.py",
    "backend/app/api/routes/practice.py",
    "backend/app/api/routes/diagnosis.py",
    "backend/app/api/routes/teaching_intelligence.py",
    "backend/app/api/routes/profile.py",
    "backend/app/api/routes/teacher_questions.py",
    "backend/app/api/routes/auth.py",
    "backend/app/api/routes/assignments.py",
    "backend/app/api/routes/uploads.py",
    "backend/app/api/routes/teacher.py",
    # ---- 前端基础设施 ----
    "frontend/src/main.js",
    "frontend/src/App.vue",
    "frontend/src/router/index.js",
    "frontend/src/api/client.js",
    "frontend/src/stores/user.js",
    # ---- 前端视图 ----
    "frontend/src/views/TeacherAssignmentsView.vue",
    "frontend/src/views/StudentAssignmentsView.vue",
    "frontend/src/views/TeacherQuestionsView.vue",
    "frontend/src/views/TeacherStudentsView.vue",
    "frontend/src/views/TeacherStudentDetailView.vue",
    "frontend/src/views/TeacherAssignmentDetailView.vue",
    "frontend/src/views/TeacherQuestionEditorView.vue",
    "frontend/src/views/StudentAssignmentView.vue",
    "frontend/src/views/KnowledgeView.vue",
    "frontend/src/views/ReviewView.vue",
    "frontend/src/views/TeacherMessagesView.vue",
    "frontend/src/views/RoadmapView.vue",
    "frontend/src/views/AuthView.vue",
    "frontend/src/views/TeacherHomeView.vue",
    "frontend/src/views/TeacherReviewView.vue",
    "frontend/src/views/DashboardView.vue",
    "frontend/src/views/TeacherAssignmentEditorView.vue",
    "frontend/src/views/TeacherClassesView.vue",
    "frontend/src/views/PracticeView.vue",
    "frontend/src/views/SideFeatureView.vue",
    # ---- 前端组件 ----
    "frontend/src/components/ui/EmptyState.vue",
    "frontend/src/components/ui/StatCard.vue",
    "frontend/src/components/ui/GlassPanel.vue",
    "frontend/src/components/messages/QuestionRefCard.vue",
    "frontend/src/components/ui/Toast.vue",
    "frontend/src/components/TeacherPageShell.vue",
    "frontend/src/components/ui/PageHeader.vue",
    "frontend/src/components/teacher/StudentTeachingIntelligence.vue",
    "frontend/src/components/teacher/QuestionInsight.vue",
    "frontend/src/components/TeacherSidebar.vue",
    "frontend/src/components/ui/ConfirmDialog.vue",
    "frontend/src/components/ui/HeatmapCalendar.vue",
    "frontend/src/components/ui/LightMarkdown.vue",
    "frontend/src/components/messages/MessageBubble.vue",
    "frontend/src/components/teacher/AssignmentIntelligence.vue",
    "frontend/src/components/messages/ContactPicker.vue",
    "frontend/src/components/UserAccountButton.vue",
    "frontend/src/components/ui/AICard.vue",
    "frontend/src/components/KnowledgeGraphChart.vue",
    "frontend/src/components/teacher/PaperDraftCard.vue",
    "frontend/src/components/teacher/TeacherIntelligenceDesk.vue",
    "frontend/src/components/student/PersonalAnalytics.vue",
    "frontend/src/components/messages/MessageComposer.vue",
    "frontend/src/components/AuthModal.vue",
    "frontend/src/components/student/StepSolution.vue",
    "frontend/src/components/teacher/AssignmentAnalytics.vue",
    "frontend/src/components/RadarChart.vue",
    "frontend/src/components/teacher/ClassDashboard.vue",
    "frontend/src/components/TeacherAIQuestionDialog.vue",
    "frontend/src/components/QuestionImportDialog.vue",
    "frontend/src/components/student/StudentLayout.vue",
    "frontend/src/components/XiaoluoAssistant.vue",
]

# 明确排除：非必要、框架样板、配置、样式
SKIP_PATTERNS = [
    r"__init__\.py$",
    r"/storage/",
    r"repositories/common\.py$",
    r"repositories/teacher_common\.py$",
    r"utils/password\.py$",
    r"services/confirm\.js$",
    r"services/toast\.js$",
]

MIN_LINES = 15


W14 = "http://schemas.microsoft.com/office/word/2010/wordml"

# 原文档每个段落自带的运行属性，逐条照抄
RPR_TEMPLATE = (
    f'<w:rPr xmlns:w="{W}" xmlns:w14="{W14}">'
    f'<w:rFonts w:hint="eastAsia" w:ascii="宋体" w:hAnsi="宋体" w:eastAsia="宋体" w:cs="宋体"/>'
    f'<w:color w:val="000000" w:themeColor="text1"/>'
    f'<w:sz w:val="21"/><w:szCs w:val="21"/>'
    f'<w14:textFill><w14:solidFill><w14:schemeClr w14:val="tx1"/></w14:solidFill></w14:textFill>'
    f"</w:rPr>"
)

# 原文档每个段落自带的段落属性，逐条照抄。
# 其中 spacing line=280 lineRule=exact 是关键：每行精确 14 磅，一页正好 50 行。
PPR_TEMPLATE = (
    f'<w:pPr xmlns:w="{W}" xmlns:w14="{W14}">'
    f'<w:keepNext w:val="0"/><w:keepLines w:val="0"/><w:pageBreakBefore w:val="0"/>'
    f'<w:widowControl w:val="0"/><w:shd w:val="clear"/>'
    f'<w:kinsoku/><w:wordWrap/><w:overflowPunct/><w:topLinePunct w:val="0"/>'
    f'<w:autoSpaceDE/><w:autoSpaceDN/><w:bidi w:val="0"/><w:adjustRightInd/><w:snapToGrid/>'
    f'<w:spacing w:line="280" w:lineRule="exact"/>'
    f'<w:textAlignment w:val="auto"/>'
    f"{RPR_TEMPLATE}"
    f"</w:pPr>"
)


def make_para(text: str) -> ET.Element:
    """构造与原文档格式完全一致的 w:p。

    刻意复刻原段的 pPr（含 spacing line=280 exact 行距）与 rPr，
    避免 Word 套用默认 1.15 倍行距，导致每页行数从 50 掉到 45。
    """
    p = ET.Element(f"{WQ}p")
    p.append(ET.fromstring(PPR_TEMPLATE))
    r = ET.SubElement(p, f"{WQ}r")
    r.append(ET.fromstring(RPR_TEMPLATE))
    t = ET.SubElement(r, f"{WQ}t")
    t.set(f"{{{XML_NS}}}space", "preserve")
    t.text = text
    return p


def read_lines(rel: str) -> list[str] | None:
    """读取源码行，**删除文件内全部空行**（仅保留非空行，缩进原样保留）。"""
    path = REPO / rel
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) < MIN_LINES:
        return None
    return lines


def main() -> int:
    # 从备份重建。基础文档（main.py ~ content.py）保留全部非空行，
    # 但其内部空行一并清除，使全文档空行只出现在文件之间。
    source = BACKUP if BACKUP.exists() else DOCX
    with zipfile.ZipFile(source) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    print(f"基础文档: {source.name}")

    root = ET.fromstring(parts["word/document.xml"])
    body = root.find(f"{WQ}body")

    # 拆出基础文档的全部段落，剔除空行后重建
    old_paras = body.findall(f"{WQ}p")
    sect = body.find(f"{WQ}sectPr")
    base_texts: list[str] = []
    removed_blanks = 0
    for p in old_paras:
        text = "".join(t.text or "" for t in p.iter(f"{WQ}t"))
        if text.strip():
            base_texts.append(text)
        else:
            removed_blanks += 1
    for p in old_paras:
        body.remove(p)
    for text in base_texts:
        body.append(make_para(text))
    print(f"基础文档: 保留 {len(base_texts)} 行，清除内部空行 {removed_blanks} 个")

    appended = 0
    skipped: list[str] = []
    total_lines = len(base_texts)

    for rel in FILES:
        if any(re.search(pat, rel) for pat in SKIP_PATTERNS):
            skipped.append(f"{rel}  (排除规则)")
            continue
        lines = read_lines(rel)
        if lines is None:
            skipped.append(f"{rel}  (不存在或过短)")
            continue

        # 类别之间恰好一个空行
        body.append(make_para(""))
        for line in lines:
            body.append(make_para(line))
        appended += 1
        total_lines += len(lines)

    # sectPr 必须留在 body 末尾
    if sect is not None:
        body.remove(sect)
        body.append(sect)

    after = len(body.findall(f"{WQ}p"))
    blanks_after = sum(
        1 for p in body.findall(f"{WQ}p")
        if not "".join(t.text or "" for t in p.iter(f"{WQ}t")).strip()
    )
    print(f"追加文件数: {appended}   总源码行数: {total_lines}")
    print(f"最终段落数: {after}   空行数: {blanks_after}（应等于文件数 {appended}）")
    print(f"\n跳过 {len(skipped)} 项:")
    for item in skipped:
        print(f"  - {item}")

    parts["word/document.xml"] = ET.tostring(
        root, xml_declaration=True, encoding="UTF-8"
    )

    with zipfile.ZipFile(DOCX, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    print(f"\n已写入 {DOCX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
