from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

import pandas as pd
from pypdf import PdfReader


MAX_IMPORT_QUESTIONS = 500
MAX_PDF_PAGES = 200

FIELD_ALIASES = {
    "题型": "question_type",
    "question_type": "question_type",
    "type": "question_type",
    "阶段": "stage",
    "stage": "stage",
    "课程": "course",
    "course": "course",
    "知识点": "knowledge_tag",
    "knowledge_tag": "knowledge_tag",
    "细分标签": "fine_tag",
    "fine_tag": "fine_tag",
    "难度": "difficulty",
    "difficulty": "difficulty",
    "题干": "question_text",
    "question": "question_text",
    "question_text": "question_text",
    "选项a": "option_a",
    "option_a": "option_a",
    "a": "option_a",
    "选项b": "option_b",
    "option_b": "option_b",
    "b": "option_b",
    "选项c": "option_c",
    "option_c": "option_c",
    "c": "option_c",
    "选项d": "option_d",
    "option_d": "option_d",
    "d": "option_d",
    "正确答案": "correct_answer",
    "答案": "correct_answer",
    "correct_answer": "correct_answer",
    "标准答案": "standard_answer",
    "参考答案": "standard_answer",
    "standard_answer": "standard_answer",
    "解析": "analysis_text",
    "analysis": "analysis_text",
    "analysis_text": "analysis_text",
    "关键步骤": "key_steps",
    "key_steps": "key_steps",
    "常见错误": "common_errors",
    "common_errors": "common_errors",
    "错因标签": "mistake_tags",
    "mistake_tags": "mistake_tags",
    "分值": "points",
    "points": "points",
}

TYPE_ALIASES = {
    "选择题": "choice",
    "单选题": "choice",
    "choice": "choice",
    "填空题": "blank",
    "blank": "blank",
    "计算题": "calculation",
    "解答题": "calculation",
    "calculation": "calculation",
    "证明题": "proof",
    "proof": "proof",
    "综合题": "comprehensive",
    "comprehensive": "comprehensive",
}

TYPE_LABELS = {
    "choice": "选择题",
    "blank": "填空题",
    "calculation": "计算题",
    "proof": "证明题",
    "comprehensive": "综合题",
}


class QuestionDocumentError(ValueError):
    pass


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, (list, tuple, dict, set)):
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
    return str(value).replace("\u00a0", " ").replace("\u200b", "").strip()


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    if not text:
        return []
    return [item.strip() for item in re.split(r"[|;；\n]", text) if item.strip()]


def _difficulty(value: Any) -> int:
    try:
        return max(1, min(5, int(float(_clean(value) or "3"))))
    except (TypeError, ValueError):
        return 3


def _points(value: Any) -> float:
    try:
        return max(1, min(100, float(_clean(value) or "10")))
    except (TypeError, ValueError):
        return 10


def _infer_question_type(question_text: str, options: dict[str, str], explicit: str = "") -> str:
    normalized = TYPE_ALIASES.get(_clean(explicit).lower())
    if normalized:
        return normalized
    if all(options.get(key) for key in "ABCD"):
        return "choice"
    if "证明" in question_text or "证：" in question_text or "求证" in question_text:
        return "proof"
    if re.search(r"[_＿]{2,}|（\s*）|\(\s*\)", question_text):
        return "blank"
    if any(keyword in question_text for keyword in ("计算", "求解", "求出", "求值", "解方程", "求极限", "求导", "积分")):
        return "calculation"
    return "comprehensive"


def _normalized_row(raw: dict[str, Any], defaults: dict[str, Any], source_row: int) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for key, value in raw.items():
        lookup = _clean(key).lower()
        mapped[FIELD_ALIASES.get(lookup, lookup)] = value

    options = {key: _clean(mapped.get(f"option_{key.lower()}")) for key in "ABCD"}
    question_text = _clean(mapped.get("question_text"))
    question_type = _infer_question_type(question_text, options, _clean(mapped.get("question_type")))
    correct_answer = _clean(mapped.get("correct_answer")).upper()
    standard_answer = _clean(mapped.get("standard_answer"))
    warnings: list[str] = []

    if question_type == "choice":
        correct_match = re.search(r"[A-D]", correct_answer)
        correct_answer = correct_match.group(0) if correct_match else correct_answer
        standard_answer = standard_answer or correct_answer
    else:
        standard_answer = standard_answer or _clean(mapped.get("correct_answer"))
        correct_answer = ""

    analysis_text = _clean(mapped.get("analysis_text"))
    if standard_answer and not analysis_text:
        analysis_text = f"参考答案：{standard_answer}"
        warnings.append("原文件未提供解析，已用参考答案生成基础解析。")

    knowledge_tag = _clean(mapped.get("knowledge_tag")) or _clean(defaults.get("knowledge_tag"))
    fine_tag = _clean(mapped.get("fine_tag")) or _clean(defaults.get("fine_tag")) or knowledge_tag
    item = {
        "source_row": source_row,
        "question_type": question_type,
        "type_label": TYPE_LABELS[question_type],
        "stage": _clean(mapped.get("stage")) or _clean(defaults.get("stage")),
        "course": _clean(mapped.get("course")) or _clean(defaults.get("course")),
        "knowledge_tag": knowledge_tag,
        "fine_tag": fine_tag,
        "difficulty": _difficulty(mapped.get("difficulty") or defaults.get("difficulty")),
        "question_text": question_text,
        "option_a": options["A"] or None,
        "option_b": options["B"] or None,
        "option_c": options["C"] or None,
        "option_d": options["D"] or None,
        "correct_answer": correct_answer or None,
        "standard_answer": standard_answer,
        "analysis_text": analysis_text,
        "key_steps": _list_value(mapped.get("key_steps")),
        "common_errors": _list_value(mapped.get("common_errors")),
        "mistake_tags": _list_value(mapped.get("mistake_tags")),
        "points": _points(mapped.get("points")),
        "warnings": warnings,
        "errors": [],
    }
    errors = item["errors"]
    if len(question_text) < 2:
        errors.append("题干不能为空。")
    if len(item["stage"]) < 2:
        errors.append("缺少学习阶段。")
    if not item["course"]:
        errors.append("缺少课程。")
    if not item["knowledge_tag"]:
        errors.append("缺少知识点。")
    if question_type == "choice":
        if not all(options.values()):
            errors.append("选择题必须包含 A、B、C、D 四个选项。")
        if correct_answer not in {"A", "B", "C", "D"}:
            errors.append("选择题答案必须是 A、B、C 或 D。")
    if not standard_answer:
        errors.append("缺少标准答案。")
    if not analysis_text:
        errors.append("缺少题目解析。")
    item["valid"] = not errors
    return item


def parse_structured_questions(raw: bytes, suffix: str, defaults: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        if suffix in {"xlsx", "xls"}:
            frame = pd.read_excel(io.BytesIO(raw), dtype=object)
            rows = frame.where(frame.notna(), "").to_dict(orient="records")
        else:
            decoded = raw.decode("utf-8-sig")
            rows = list(csv.DictReader(io.StringIO(decoded)))
    except UnicodeDecodeError as exc:
        raise QuestionDocumentError("CSV 必须使用 UTF-8 编码。") from exc
    except Exception as exc:
        raise QuestionDocumentError("表格读取失败，请检查文件是否损坏、表头是否位于第一行。") from exc
    if not rows:
        raise QuestionDocumentError("文件中没有可读取的题目行。")
    if len(rows) > MAX_IMPORT_QUESTIONS:
        raise QuestionDocumentError(f"每次最多导入 {MAX_IMPORT_QUESTIONS} 道题。")
    return [_normalized_row(row, defaults, index) for index, row in enumerate(rows, start=2)]


_QUESTION_START = re.compile(r"(?m)^\s*(?:第\s*)?(\d{1,3})\s*[.．、)]\s*(\S.*)$")
_OPTION_START = re.compile(r"^\s*([A-D])\s*[.．、:：)]\s*(.*)$", re.I)
_ANSWER_LINE = re.compile(r"^\s*(?:正确答案|参考答案|答案|correct answer|reference answer|answer)\s*[:：]\s*(.*)$", re.I)
_ANALYSIS_LINE = re.compile(r"^\s*(?:解析|解答|说明|analysis|solution|explanation)\s*[:：]\s*(.*)$", re.I)
_STANDALONE_ANSWER_HEADING = re.compile(
    r"(?im)^\s*(?:参考答案(?:与解析)?|答案(?:与解析)?|答案及解析|answers?(?:\s+and\s+(?:analysis|solutions?))?|answer key|solutions?)\s*$"
)


def _numbered_blocks(text: str) -> list[tuple[int, str]]:
    matches = list(_QUESTION_START.finditer(text))
    blocks: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = f"{match.group(2)}\n{text[match.end():end]}".strip()
        blocks.append((int(match.group(1)), body))
    return blocks


def _split_inline_markers(body: str) -> list[str]:
    body = re.sub(r"\s+(?=[A-D]\s*[.．、:：)]\s*)", "\n", body)
    body = re.sub(
        r"\s+(?=(?:正确答案|参考答案|答案|解析|解答|说明|correct answer|reference answer|answer|analysis|solution|explanation)\s*[:：])",
        "\n",
        body,
        flags=re.I,
    )
    return [line.strip() for line in body.splitlines() if line.strip()]


def _answer_details(body: str) -> tuple[str, str]:
    lines = _split_inline_markers(body)
    answer_parts: list[str] = []
    analysis_parts: list[str] = []
    in_analysis = False
    for line in lines:
        answer_match = _ANSWER_LINE.match(line)
        analysis_match = _ANALYSIS_LINE.match(line)
        if answer_match:
            answer_parts.append(answer_match.group(1).strip())
            continue
        if analysis_match:
            in_analysis = True
            analysis_parts.append(analysis_match.group(1).strip())
            continue
        (analysis_parts if in_analysis else answer_parts).append(line)
    answer = "\n".join(answer_parts).strip()
    analysis = "\n".join(analysis_parts).strip()
    if not analysis and len(answer) > 1 and re.match(r"^[A-D](?:\s|$)", answer, re.I):
        first, _, remainder = answer.partition(" ")
        answer = first
        analysis = remainder.strip()
    return answer, analysis


def _parse_pdf_question(number: int, body: str, answer_body: str, defaults: dict[str, Any]) -> dict[str, Any]:
    lines = _split_inline_markers(body)
    stem: list[str] = []
    options: dict[str, list[str]] = {key: [] for key in "ABCD"}
    inline_answer = ""
    inline_analysis: list[str] = []
    current_option = ""
    in_analysis = False

    for line in lines:
        option_match = _OPTION_START.match(line)
        answer_match = _ANSWER_LINE.match(line)
        analysis_match = _ANALYSIS_LINE.match(line)
        if option_match:
            current_option = option_match.group(1).upper()
            options[current_option].append(option_match.group(2).strip())
            in_analysis = False
        elif answer_match:
            inline_answer = answer_match.group(1).strip()
            current_option = ""
        elif analysis_match:
            inline_analysis.append(analysis_match.group(1).strip())
            current_option = ""
            in_analysis = True
        elif in_analysis:
            inline_analysis.append(line)
        elif current_option:
            options[current_option].append(line)
        else:
            stem.append(line)

    external_answer, external_analysis = _answer_details(answer_body) if answer_body else ("", "")
    answer = inline_answer or external_answer
    analysis = "\n".join(inline_analysis).strip() or external_analysis
    question_text = "\n".join(stem).strip()
    label_match = re.match(
        r"^[【\[]?(选择题|单选题|填空题|计算题|解答题|证明题|综合题|choice|blank|calculation|proof|comprehensive)[】\]]?\s*[:：-]?\s*",
        question_text,
        flags=re.I,
    )
    explicit_type = label_match.group(1) if label_match else ""
    if label_match:
        question_text = question_text[label_match.end():].strip()
    points_match = re.search(r"[（(\[]\s*(\d+(?:\.\d+)?)\s*分\s*[）)\]]", question_text)
    row = {
        "question_type": explicit_type,
        "question_text": question_text,
        "option_a": " ".join(options["A"]).strip(),
        "option_b": " ".join(options["B"]).strip(),
        "option_c": " ".join(options["C"]).strip(),
        "option_d": " ".join(options["D"]).strip(),
        "correct_answer": answer,
        "standard_answer": answer,
        "analysis_text": analysis,
        "points": points_match.group(1) if points_match else defaults.get("points", 10),
    }
    return _normalized_row(row, defaults, number)


def parse_pdf_questions(raw: bytes, defaults: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        reader = PdfReader(io.BytesIO(raw))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise QuestionDocumentError(f"PDF 最多支持 {MAX_PDF_PAGES} 页。")
        page_texts = [(page.extract_text() or "") for page in reader.pages]
    except QuestionDocumentError:
        raise
    except Exception as exc:
        raise QuestionDocumentError("PDF 读取失败，请确认文件未加密且没有损坏。") from exc

    text = "\n".join(page_texts).replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(re.sub(r"\s", "", text)) < 20:
        raise QuestionDocumentError("这个 PDF 没有可提取文字，可能是扫描件；请先做 OCR，或改用 Excel 模板导入。")

    heading = _STANDALONE_ANSWER_HEADING.search(text)
    question_section = text[:heading.start()] if heading else text
    answer_section = text[heading.end():] if heading else ""
    question_blocks = _numbered_blocks(question_section)
    if not question_blocks:
        raise QuestionDocumentError("未识别到题号。PDF 题目请使用“1. 题干”的编号格式。")
    if len(question_blocks) > MAX_IMPORT_QUESTIONS:
        raise QuestionDocumentError(f"每次最多导入 {MAX_IMPORT_QUESTIONS} 道题。")

    answer_blocks = dict(_numbered_blocks(answer_section)) if answer_section else {}
    compact_answers = {
        int(match.group(1)): match.group(2).upper()
        for match in re.finditer(r"(?<!\d)(\d{1,3})\s*[.．、:：]\s*([A-D])(?=\s|$|[，,;；])", answer_section, re.I)
    }
    result = []
    for number, body in question_blocks:
        answer_body = answer_blocks.get(number, compact_answers.get(number, ""))
        result.append(_parse_pdf_question(number, body, answer_body, defaults))
    return result


def parse_question_document(raw: bytes, filename: str, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    defaults = defaults or {}
    if suffix in {"xlsx", "xls", "csv"}:
        questions = parse_structured_questions(raw, suffix, defaults)
        method = "structured-table"
    elif suffix == "pdf":
        questions = parse_pdf_questions(raw, defaults)
        method = "pdf-text"
    else:
        raise QuestionDocumentError("仅支持 PDF、Excel（.xlsx/.xls）和 UTF-8 CSV 文件。")

    seen: set[str] = set()
    for question in questions:
        fingerprint = re.sub(r"\s+", "", question["question_text"])
        if fingerprint in seen:
            question["warnings"].append("文件内存在重复题干，确认导入时会自动去重。")
        seen.add(fingerprint)
    return {
        "file_name": Path(filename or "未命名文件").name,
        "file_type": suffix,
        "parse_method": method,
        "total_detected": len(questions),
        "valid_count": sum(1 for item in questions if item["valid"]),
        "invalid_count": sum(1 for item in questions if not item["valid"]),
        "warning_count": sum(len(item["warnings"]) for item in questions),
        "questions": questions,
    }
