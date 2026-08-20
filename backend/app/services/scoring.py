import math
import re
from typing import Any


def _tokenize_answer(text_value: str) -> set[str]:
    return {
        token.lower()
        for token in re.split(r"[\s,.;:，。；：、()（）\\[\\]{}<>《》\"'“”]+", text_value)
        if len(token.strip()) >= 2
    }

def _normalize_math_answer(text_value: str) -> str:
    normalized = str(text_value or "").strip().lower()
    normalized = re.sub(r"^(?:答案|答)\s*[:：]\s*", "", normalized)
    replacements = {
        "，": ",",
        "；": ";",
        "（": "(",
        "）": ")",
        "−": "-",
        "－": "-",
        "×": "*",
        "π": "pi",
        "√": "sqrt",
        "\\left": "",
        "\\right": "",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return re.sub(r"[\s。.;；]+", "", normalized)

def _score_subjective(
    answer_text: str,
    question: dict[str, Any],
    question_type: str,
) -> tuple[bool, float]:
    answer_text = answer_text.strip()
    if not answer_text:
        return False, 0.0

    normalized_answer = _normalize_math_answer(answer_text)
    normalized_standard = _normalize_math_answer(question.get("standard_answer") or "")
    if normalized_answer and normalized_standard and normalized_answer == normalized_standard:
        return True, 100.0

    if question_type == "blank":
        return False, 0.0

    key_text = " ".join(
        [
            question.get("standard_answer") or "",
            " ".join(question.get("key_steps") or []),
            question.get("knowledge_tag") or "",
            question.get("fine_tag") or "",
        ]
    )
    expected = _tokenize_answer(key_text)
    actual = _tokenize_answer(answer_text)
    if not expected:
        score = 70.0 if len(answer_text) >= 20 else 0.0
        return score >= 60, score

    overlap = len(expected & actual)
    ratio = overlap / max(len(expected), 1)
    length_bonus = min(len(answer_text) / 180, 0.25)
    score = max(30.0, min(100.0, (ratio * 90) + (length_bonus * 100)))
    return score >= 60, round(score, 2)

