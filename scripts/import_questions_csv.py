"""Import data/questions.csv into the MySQL questions table.

The script is intentionally idempotent: rows are keyed by
(source_name, source_question_no), matching the table's unique index.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
QUESTIONS_CSV = ROOT / "data" / "questions.csv"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.session import SessionLocal  # noqa: E402


REQUIRED_FIELDS = [
    "题干",
    "选项A",
    "选项B",
    "选项C",
    "选项D",
    "正确答案",
    "所属模块",
    "知识点标签",
    "来源",
    "题号",
    "来源链接",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def normalize_answer(value: str) -> str:
    answer = clean(value).upper()
    return answer if answer in {"A", "B", "C", "D"} else ""


def difficulty_for(module: str, tag: str) -> int:
    text_value = f"{module} {tag}"
    if any(word in text_value for word in ("数量关系", "排列组合", "概率", "几何", "综合分析")):
        return 4
    if any(word in text_value for word in ("资料分析", "判断推理", "图形推理", "增长率")):
        return 3
    return 2


def iter_rows() -> tuple[list[dict[str, str]], list[str]]:
    skipped: list[str] = []
    imported: list[dict[str, str]] = []

    with QUESTIONS_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = [field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise RuntimeError(f"questions.csv missing columns: {', '.join(missing)}")

        for line_no, row in enumerate(reader, start=2):
            question_text = clean(row["题干"])
            option_a = clean(row["选项A"])
            option_b = clean(row["选项B"])
            option_c = clean(row["选项C"])
            option_d = clean(row["选项D"])
            answer = normalize_answer(row["正确答案"])
            module = clean(row["所属模块"])
            tag = clean(row["知识点标签"])
            source_name = clean(row["来源"]) or "questions.csv"
            source_no = clean(row["题号"]) or str(line_no)
            source_url = clean(row["来源链接"])

            if not all([question_text, option_a, option_b, option_c, option_d, answer, module, tag]):
                skipped.append(f"line {line_no}: required field missing")
                continue

            imported.append(
                {
                    "question_text": question_text,
                    "option_a": option_a,
                    "option_b": option_b,
                    "option_c": option_c,
                    "option_d": option_d,
                    "correct_answer": answer,
                    "module": module,
                    "knowledge_tag": tag,
                    "difficulty": difficulty_for(module, tag),
                    "source_name": source_name,
                    "source_question_no": source_no,
                    "source_url": source_url,
                }
            )

    return imported, skipped


def main() -> None:
    rows, skipped = iter_rows()
    if not rows:
        print("No valid rows found.")
        return

    query = text(
        """
        INSERT INTO questions (
          question_text, option_a, option_b, option_c, option_d, correct_answer,
          module, knowledge_tag, difficulty, source_name, source_question_no, source_url
        )
        VALUES (
          :question_text, :option_a, :option_b, :option_c, :option_d, :correct_answer,
          :module, :knowledge_tag, :difficulty, :source_name, :source_question_no, :source_url
        )
        ON DUPLICATE KEY UPDATE
          question_text = VALUES(question_text),
          option_a = VALUES(option_a),
          option_b = VALUES(option_b),
          option_c = VALUES(option_c),
          option_d = VALUES(option_d),
          correct_answer = VALUES(correct_answer),
          module = VALUES(module),
          knowledge_tag = VALUES(knowledge_tag),
          difficulty = VALUES(difficulty),
          source_url = VALUES(source_url),
          updated_at = CURRENT_TIMESTAMP
        """
    )

    with SessionLocal() as db:
        before = db.execute(text("SELECT COUNT(*) FROM questions")).scalar_one()
        db.execute(query, rows)
        db.commit()
        after = db.execute(text("SELECT COUNT(*) FROM questions")).scalar_one()

    print(f"CSV rows valid: {len(rows)}")
    print(f"Skipped rows: {len(skipped)}")
    print(f"Questions before: {before}")
    print(f"Questions after: {after}")
    if skipped:
        print("First skipped rows:")
        for item in skipped[:10]:
            print(f"- {item}")


if __name__ == "__main__":
    main()
