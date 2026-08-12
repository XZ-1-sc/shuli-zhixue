"""Offline regression checks for teacher PDF and spreadsheet imports."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.utils.question_document_parser import QuestionDocumentError, parse_question_document  # noqa: E402


DEFAULTS = {
    "stage": "大一",
    "course": "高等数学（上）",
    "knowledge_tag": "函数极限",
    "fine_tag": "文件导入",
    "difficulty": 3,
}


def spreadsheet_bytes() -> bytes:
    rows = [
        {
            "题型": "选择题",
            "阶段": "大一",
            "课程": "高等数学（上）",
            "知识点": "函数极限",
            "细分标签": "重要极限",
            "难度": 2,
            "题干": "当 x 趋于 0 时，sin(x)/x 的极限是（ ）。",
            "选项A": "0",
            "选项B": "1",
            "选项C": "不存在",
            "选项D": "无穷大",
            "正确答案": "B",
            "标准答案": "B",
            "解析": "利用重要极限可得 1。",
            "分值": 5,
        },
        {
            "题型": "计算题",
            "题干": "求函数 y=sin(x²) 的导数。",
            "标准答案": "y'=2x cos(x²)",
            "解析": "使用复合函数链式法则。",
            "分值": 10,
        },
    ]
    output = io.BytesIO()
    pd.DataFrame(rows).to_excel(output, index=False)
    return output.getvalue()


def text_pdf_bytes() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
    )
    lines = [
        "1. [choice] The limit of sin(x)/x as x approaches zero is ( ).",
        "A. 0",
        "B. 1",
        "C. Does not exist",
        "D. Infinity",
        "2. [calculation] Differentiate y=sin(x^2).",
        "Answers and Analysis",
        "1. B",
        "Analysis: Apply the standard trigonometric limit.",
        "2. y'=2x cos(x^2)",
        "Analysis: Apply the chain rule.",
    ]
    commands = ["BT", "/F1 12 Tf", "50 790 Td"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            commands.append("0 -24 Td")
        commands.append(f"({escaped}) Tj")
    commands.append("ET")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def main() -> None:
    spreadsheet = parse_question_document(spreadsheet_bytes(), "questions.xlsx", DEFAULTS)
    assert spreadsheet["valid_count"] == 2, spreadsheet
    assert spreadsheet["questions"][0]["correct_answer"] == "B"
    assert spreadsheet["questions"][1]["question_type"] == "calculation"

    pdf = parse_question_document(text_pdf_bytes(), "questions.pdf", DEFAULTS)
    assert pdf["valid_count"] == 2, pdf
    assert pdf["questions"][0]["correct_answer"] == "B"
    assert pdf["questions"][1]["question_type"] == "calculation"

    blank_pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(blank_pdf)
    try:
        parse_question_document(blank_pdf.getvalue(), "scan.pdf", DEFAULTS)
    except QuestionDocumentError as exc:
        assert "OCR" in str(exc)
    else:
        raise AssertionError("A blank/scanned PDF must not be accepted as parsed questions.")

    print("QUESTION_DOCUMENT_PARSER_OK")


if __name__ == "__main__":
    main()
