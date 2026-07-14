import asyncio
import csv
import json
import random
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...agents.diagnostician import diagnose
from ...agents.navigator import recommend as recommend_questions
from ...database.session import SessionLocal
from ...orchestrator import _fetch_recent_records
from ...utils.llm_client import call_llm


router = APIRouter(prefix="/api", tags=["learning"])
ROOT_DIR = Path(__file__).resolve().parents[4]
QUESTIONS_CSV = ROOT_DIR / "data" / "questions.csv"

MODULE_LABELS = ["言语", "判断", "资料", "数量", "常识"]
DEFAULT_SCORES = {
    "言语": 76,
    "判断": 54,
    "资料": 68,
    "数量": 61,
    "常识": 72,
}
MODULE_ALIASES = {
    "言语": ["言语", "言语理解", "言语理解与表达"],
    "判断": ["判断", "判断推理"],
    "资料": ["资料", "资料分析"],
    "数量": ["数量", "数量关系"],
    "常识": ["常识", "常识判断"],
}

DEFAULT_STRATEGY = "建议主攻模块：判断推理（逻辑判断） > 资料分析（比重计算）"
CHAT_SYSTEM_PROMPT = (
    "你是行测智脑里的小逻，定位是冷静、具体、可执行的备考助手。"
    "回答要短，优先给下一步动作；如果用户问学习规划，要结合上下文连续对话。"
)


class ChatRequest(BaseModel):
    user_id: int = Field(default=1, ge=1)
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=64)


class StudyPlanRequest(BaseModel):
    user_id: int = Field(ge=1)
    exam_type: str = Field(min_length=1, max_length=64)
    job_category: str = Field(min_length=1, max_length=128)
    plan_name: str = Field(min_length=1, max_length=128)


class UserGoalRequest(BaseModel):
    user_id: int = Field(ge=1)
    target_score: float = Field(ge=0, le=150)
    exam_date: date
    target_exam: str = Field(default="国考", min_length=1, max_length=128)


class AnswerSubmissionRequest(BaseModel):
    user_id: int = Field(ge=1)
    task_id: str = Field(min_length=1, max_length=64)
    question_id: int = Field(ge=1)
    selected_answer: str | None = Field(default=None, pattern="^[ABCD]$")
    answer_text: str | None = Field(default=None, max_length=3000)
    time_spent_seconds: int = Field(default=0, ge=0)
    practice_mode: str = Field(default="custom", pattern="^(daily|chapter|mock|wrong_book|custom)$")


def _short_module_name(module: Any) -> str | None:
    module_text = str(module or "")
    for short_name, aliases in MODULE_ALIASES.items():
        if any(alias in module_text for alias in aliases):
            return short_name
    return None


def _scores_from_records(records: list[dict[str, Any]]) -> dict[str, int]:
    stats = {
        module: {"total": 0, "correct": 0}
        for module in MODULE_LABELS
    }

    for record in records:
        module = _short_module_name(record.get("module"))
        if not module:
            continue
        stats[module]["total"] += 1
        stats[module]["correct"] += int(bool(record.get("is_correct")))

    scores: dict[str, int] = {}
    for module, item in stats.items():
        if item["total"] == 0:
            scores[module] = DEFAULT_SCORES[module]
            continue
        scores[module] = round(item["correct"] / item["total"] * 100)

    return scores


def _fallback_recommendations() -> list[dict[str, Any]]:
    return [
        {
            "id": 1,
            "title": "逻辑判断加强削弱 10题",
            "module": "判断推理",
            "knowledge_tag": "逻辑判断",
            "difficulty": 3,
        },
        {
            "id": 2,
            "title": "资料分析比重计算 15题",
            "module": "资料分析",
            "knowledge_tag": "比重计算",
            "difficulty": 2,
        },
        {
            "id": 3,
            "title": "逻辑填空成语辨析 20题",
            "module": "言语理解与表达",
            "knowledge_tag": "逻辑填空",
            "difficulty": 3,
        },
        {
            "id": 4,
            "title": "图形推理规律训练 10题",
            "module": "判断推理",
            "knowledge_tag": "图形推理",
            "difficulty": 3,
        },
        {
            "id": 5,
            "title": "常识判断速记 12题",
            "module": "常识判断",
            "knowledge_tag": "常识综合",
            "difficulty": 2,
        },
    ]


SCORE_LINE_GROUPS = [
    {
        "province": "国考",
        "items": [
            {"year": 2025, "exam": "中央机关及直属机构", "category": "综合管理类", "score": 121.4},
            {"year": 2024, "exam": "中央机关及直属机构", "category": "行政执法类", "score": 118.7},
            {"year": 2023, "exam": "中央机关及直属机构", "category": "地市级", "score": 116.2},
            {"year": 2022, "exam": "中央机关及直属机构", "category": "副省级", "score": 124.1},
        ],
    },
    {
        "province": "北京",
        "items": [
            {"year": 2025, "exam": "北京市考", "category": "市级机关", "score": 137.5},
            {"year": 2024, "exam": "北京市考", "category": "区级机关", "score": 132.8},
            {"year": 2023, "exam": "北京市考", "category": "基层岗位", "score": 126.6},
        ],
    },
    {
        "province": "广东",
        "items": [
            {"year": 2025, "exam": "广东省考", "category": "县级以上机关", "score": 74.2},
            {"year": 2024, "exam": "广东省考", "category": "珠三角岗位", "score": 78.6},
            {"year": 2023, "exam": "广东省考", "category": "乡镇岗位", "score": 66.4},
        ],
    },
    {
        "province": "江苏",
        "items": [
            {"year": 2025, "exam": "江苏省考", "category": "A类", "score": 131.2},
            {"year": 2024, "exam": "江苏省考", "category": "B类", "score": 126.5},
            {"year": 2023, "exam": "江苏省考", "category": "C类", "score": 121.8},
        ],
    },
    {
        "province": "浙江",
        "items": [
            {"year": 2025, "exam": "浙江省考", "category": "综合类", "score": 132.1},
            {"year": 2024, "exam": "浙江省考", "category": "基层类", "score": 127.4},
            {"year": 2023, "exam": "浙江省考", "category": "行政执法类", "score": 123.6},
        ],
    },
    {
        "province": "山东",
        "items": [
            {"year": 2025, "exam": "山东省考", "category": "省直机关", "score": 72.8},
            {"year": 2024, "exam": "山东省考", "category": "市县机关", "score": 68.5},
            {"year": 2023, "exam": "山东省考", "category": "乡镇岗位", "score": 64.9},
        ],
    },
    {
        "province": "四川",
        "items": [
            {"year": 2025, "exam": "四川省考", "category": "综合管理", "score": 70.6},
            {"year": 2024, "exam": "四川省考", "category": "行政执法", "score": 66.8},
            {"year": 2023, "exam": "四川省考", "category": "基层治理", "score": 63.7},
        ],
    },
    {
        "province": "河南",
        "items": [
            {"year": 2025, "exam": "河南省考", "category": "省直机关", "score": 67.4},
            {"year": 2024, "exam": "河南省考", "category": "市县机关", "score": 64.1},
            {"year": 2023, "exam": "河南省考", "category": "乡镇机关", "score": 60.5},
        ],
    },
]

PLAN_OPTIONS = [
    {
        "exam_type": "国考",
        "job_category": "行政执法类",
        "plan_name": "国考执法冲刺方案",
        "focus": ["资料分析速度", "判断推理稳定性", "申论热点联动"],
    },
    {
        "exam_type": "国考",
        "job_category": "地市级综合管理",
        "plan_name": "地市级稳分方案",
        "focus": ["言语主旨题", "逻辑判断", "常识时政"],
    },
    {
        "exam_type": "省考",
        "job_category": "省直机关",
        "plan_name": "省直高分方案",
        "focus": ["数量关系取舍", "资料分析满分率", "判断推理难题"],
    },
    {
        "exam_type": "省考",
        "job_category": "乡镇基层",
        "plan_name": "基层岗位提速方案",
        "focus": ["常识判断", "言语理解", "资料分析基础题"],
    },
    {
        "exam_type": "事业单位",
        "job_category": "综合岗",
        "plan_name": "事业单位综合备考方案",
        "focus": ["公共基础知识", "言语表达", "判断推理基础"],
    },
]

PRACTICE_MODULES = [
    {
        "module": "言语理解与表达",
        "short_name": "言语",
        "types": ["逻辑填空", "片段阅读", "语句排序", "下文推断", "标题提炼"],
    },
    {
        "module": "判断推理",
        "short_name": "判断",
        "types": ["逻辑判断", "图形推理", "定义判断", "类比推理"],
    },
    {
        "module": "资料分析",
        "short_name": "资料",
        "types": ["增长率", "比重计算", "平均数", "倍数与比较", "综合分析"],
    },
    {
        "module": "数量关系",
        "short_name": "数量",
        "types": ["工程问题", "行程问题", "几何问题", "排列组合与概率", "数量计算"],
    },
    {
        "module": "常识判断",
        "short_name": "常识",
        "types": ["法律常识", "时政热点", "经济常识", "科技与自然", "历史人文"],
    },
]

SUPPLEMENTAL_ID_BASE = 9_000_000
SUPPLEMENTAL_QUESTIONS = [
    {
        "id": SUPPLEMENTAL_ID_BASE + 1,
        "question_type": "short_answer",
        "question_text": "简答题：资料分析中遇到“现期比重”和“基期比重”时，分别应如何识别题干关键词？",
        "module": "资料分析",
        "knowledge_tag": "比重计算",
        "reference_answer": "现期比重通常问当前时期某部分占整体的比重；基期比重通常出现上年、去年、基期等表述，需要结合增长率还原基期部分和整体。",
        "reference_points": ["现期", "基期", "部分", "整体", "增长率"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 2,
        "question_type": "short_answer",
        "question_text": "简答题：逻辑判断中的“加强削弱”题，作答前应先完成哪两个判断？",
        "module": "判断推理",
        "knowledge_tag": "逻辑判断",
        "reference_answer": "先找出论点和论据，再判断二者之间的论证关系。加强题要补强关系或支持论点，削弱题要切断关系、反驳论点或指出反例。",
        "reference_points": ["论点", "论据", "论证关系", "加强", "削弱"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 3,
        "question_type": "short_answer",
        "question_text": "简答题：言语理解中做主旨概括题时，如何避免被例子、背景和转折前内容干扰？",
        "module": "言语理解与表达",
        "knowledge_tag": "片段阅读",
        "reference_answer": "应优先找主题词和结构关系，重点关注转折后、结论句、必要条件句等核心信息；例子和背景多用于服务观点，不能替代主旨。",
        "reference_points": ["主题词", "结构", "转折后", "结论", "例子"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 4,
        "question_type": "short_answer",
        "question_text": "简答题：数量关系考试中，什么情况下应果断跳过一道题？请写出至少三种信号。",
        "module": "数量关系",
        "knowledge_tag": "数量计算",
        "reference_answer": "计算量明显过大、条件关系复杂且无法快速建模、读题超过一分钟仍无思路、选项差距小且无法估算时，应先跳过。",
        "reference_points": ["计算量", "建模", "一分钟", "无思路", "估算"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 5,
        "question_type": "short_answer",
        "question_text": "简答题：常识判断复盘时，如何把错题整理成可复习的知识卡片？",
        "module": "常识判断",
        "knowledge_tag": "常识综合",
        "reference_answer": "可记录题目考点、错误原因、正确知识点、相近易混点和一条例子，复习时按法律、时政、科技、人文等类别归档。",
        "reference_points": ["考点", "错误原因", "正确知识点", "易混点", "分类"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 6,
        "question_type": "analysis",
        "question_text": "材料概括题：一次模拟后发现资料分析正确率高但耗时长，请分析可能原因，并给出两条提速策略。",
        "module": "资料分析",
        "knowledge_tag": "综合分析",
        "reference_answer": "可能原因是公式不熟、定位材料慢、精算过多。策略包括先看问题再定位材料、常用公式自动化、优先估算和截位计算。",
        "reference_points": ["公式", "定位", "精算", "估算", "截位"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 7,
        "question_type": "short_answer",
        "question_text": "简答题：言语理解中遇到成语辨析题，应从哪些角度判断一个成语是否适配语境？",
        "module": "言语理解与表达",
        "knowledge_tag": "成语辨析",
        "reference_answer": "应结合语义轻重、感情色彩、适用对象、搭配习惯和语境逻辑判断。不能只看成语大意，还要看前后文是否存在转折、递进、因果等关系。",
        "reference_points": ["语义轻重", "感情色彩", "适用对象", "搭配", "语境逻辑"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 8,
        "question_type": "analysis",
        "question_text": "材料分析题：某考生图形推理连续错题，请从观察顺序和常见规律两个角度，写出复盘方案。",
        "module": "判断推理",
        "knowledge_tag": "图形推理",
        "reference_answer": "复盘时先固定观察顺序，如位置、数量、样式、属性、空间，再记录错题对应规律。常见规律包括点线面数量、对称性、旋转翻转、黑白运算、元素移动和立体展开。",
        "reference_points": ["观察顺序", "数量", "属性", "旋转翻转", "黑白运算"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 9,
        "question_type": "short_answer",
        "question_text": "简答题：资料分析中计算增长率时，如何区分增长率、增长量和倍数关系？",
        "module": "资料分析",
        "knowledge_tag": "增长率计算",
        "reference_answer": "增长率表示增长量相对基期量的比例，增长量表示现期量与基期量的差，倍数关系表示一个量是另一个量的几倍。读题时要关注百分号、增加了多少、是几倍等关键词。",
        "reference_points": ["增长率", "增长量", "基期量", "倍数", "关键词"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 10,
        "question_type": "analysis",
        "question_text": "材料分析题：数量关系工程问题中，如果题干出现多人合作、效率变化和总量未知，应如何建模？",
        "module": "数量关系",
        "knowledge_tag": "工程问题",
        "reference_answer": "通常把工程总量设为效率分母的最小公倍数，分别求出各主体效率，再按合作时间、单独时间或效率变化列方程。若选项差距明显，可结合代入和估算缩短计算。",
        "reference_points": ["工程总量", "最小公倍数", "效率", "合作时间", "方程"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 11,
        "question_type": "short_answer",
        "question_text": "简答题：常识判断法律题复盘时，如何区分“记忆性错误”和“概念理解错误”？",
        "module": "常识判断",
        "knowledge_tag": "法律常识",
        "reference_answer": "记忆性错误多是条文主体、时间、程序、权限记混；概念理解错误则是没有区分相近概念的适用条件和法律后果。复盘时要标注错因，并补一条例子帮助迁移。",
        "reference_points": ["记忆性错误", "概念理解", "主体", "适用条件", "法律后果"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 12,
        "question_type": "analysis",
        "question_text": "材料分析题：语句排序题经常在首句和尾句判断上失误，请写出一套排除顺序。",
        "module": "言语理解与表达",
        "knowledge_tag": "语句排序",
        "reference_answer": "先排除不适合做首句的代词指代句、补充说明句和结论承接句，再找时间顺序、逻辑顺序、话题一致和关联词配对，最后用尾句是否总结全文或自然收束来验证。",
        "reference_points": ["首句", "代词指代", "逻辑顺序", "关联词", "尾句"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 13,
        "question_type": "short_answer",
        "question_text": "简答题：加强削弱题中，什么是“样本偏差”？它通常如何削弱论证？",
        "module": "判断推理",
        "knowledge_tag": "加强削弱",
        "reference_answer": "样本偏差指论证所依据的样本不能代表总体，例如样本数量太少、来源单一或选择方式有倾向。它会削弱从样本推总体的结论可靠性。",
        "reference_points": ["样本偏差", "代表性", "总体", "来源单一", "可靠性"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 14,
        "question_type": "analysis",
        "question_text": "材料分析题：资料分析平均数比较题中，如何快速判断平均数上升还是下降？",
        "module": "资料分析",
        "knowledge_tag": "平均数",
        "reference_answer": "平均数等于总量除以份数。比较平均数变化时，可比较总量增长率和份数增长率；总量增长率大于份数增长率，平均数上升，反之下降。",
        "reference_points": ["平均数", "总量", "份数", "增长率比较", "上升下降"],
    },
    {
        "id": SUPPLEMENTAL_ID_BASE + 15,
        "question_type": "short_answer",
        "question_text": "简答题：数量关系行程问题中，遇到相遇、追及、环形跑道时，应优先写出哪些基本关系式？",
        "module": "数量关系",
        "knowledge_tag": "行程问题",
        "reference_answer": "相遇问题常用路程和等于速度和乘时间，追及问题常用路程差等于速度差乘时间，环形跑道要判断同向追及还是反向相遇，并结合圈长建立关系。",
        "reference_points": ["相遇", "追及", "速度和", "速度差", "圈长"],
    },

]


def _normalize_session_id(session_id: str | None) -> str:
    normalized = str(session_id or "").strip()
    return normalized or str(uuid.uuid4())


def _question_row_to_dict(row: Any) -> dict[str, Any]:
    try:
        mapping = dict(row)
    except (TypeError, ValueError):
        mapping = dict(row._mapping)
    return {
        "id": int(mapping["id"]),
        "question_type": "choice",
        "question_text": str(mapping["question_text"]),
        "option_a": str(mapping["option_a"]),
        "option_b": str(mapping["option_b"]),
        "option_c": str(mapping["option_c"]),
        "option_d": str(mapping["option_d"]),
        "module": str(mapping["module"]),
        "knowledge_tag": str(mapping.get("knowledge_tag") or "综合"),
        "difficulty": int(mapping.get("difficulty") or 3),
        "source_name": str(mapping.get("source_name") or ""),
        "source_question_no": str(mapping.get("source_question_no") or ""),
    }


def _supplemental_matches(question: dict[str, Any], module: str | None, knowledge_tag: str | None) -> bool:
    if module and module not in question["module"] and module not in question["knowledge_tag"]:
        return False
    if knowledge_tag and knowledge_tag not in question["knowledge_tag"] and question["knowledge_tag"] not in knowledge_tag:
        return False
    return True


def _public_supplemental_question(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": question["id"],
        "question_type": question["question_type"],
        "question_text": question["question_text"],
        "module": question["module"],
        "knowledge_tag": question["knowledge_tag"],
        "difficulty": 3,
        "source_name": "补充主观题库",
        "source_question_no": str(question["id"] - SUPPLEMENTAL_ID_BASE),
    }


def _load_csv_question_rows() -> list[dict[str, Any]]:
    if not QUESTIONS_CSV.exists():
        return []

    with QUESTIONS_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not row.get("题干"):
            continue
        normalized.append(
            {
                "question_text": row.get("题干", ""),
                "option_a": row.get("选项A", ""),
                "option_b": row.get("选项B", ""),
                "option_c": row.get("选项C", ""),
                "option_d": row.get("选项D", ""),
                "correct_answer": row.get("正确答案", "A"),
                "module": row.get("所属模块", "行测"),
                "knowledge_tag": row.get("知识点标签", "综合"),
                "difficulty": 3,
                "source_name": row.get("来源", "questions.csv"),
                "source_question_no": row.get("题号", str(index)),
                "source_url": row.get("来源链接", ""),
            }
        )
    return normalized


def _ensure_csv_questions_in_db(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    select_query = text(
        """
        SELECT id, question_text, option_a, option_b, option_c, option_d,
               module, knowledge_tag, difficulty, source_name, source_question_no
        FROM questions
        WHERE source_name = :source_name AND source_question_no = :source_question_no
        LIMIT 1
        """
    )
    insert_query = text(
        """
        INSERT INTO questions (
          question_text, option_a, option_b, option_c, option_d, correct_answer,
          module, knowledge_tag, difficulty, source_name, source_question_no, source_url
        )
        VALUES (
          :question_text, :option_a, :option_b, :option_c, :option_d, :correct_answer,
          :module, :knowledge_tag, :difficulty, :source_name, :source_question_no, :source_url
        )
        """
    )
    fetch_by_id_query = text(
        """
        SELECT id, question_text, option_a, option_b, option_c, option_d,
               module, knowledge_tag, difficulty, source_name, source_question_no
        FROM questions
        WHERE id = :id
        """
    )

    inserted: list[dict[str, Any]] = []
    with SessionLocal() as db:
        for row in rows:
            existing = db.execute(
                select_query,
                {
                    "source_name": row["source_name"],
                    "source_question_no": row["source_question_no"],
                },
            ).mappings().first()
            if existing:
                inserted.append(_question_row_to_dict(existing))
                continue

            result = db.execute(insert_query, row)
            db.commit()
            stored = db.execute(fetch_by_id_query, {"id": int(result.lastrowid)}).mappings().first()
            if stored:
                inserted.append(_question_row_to_dict(stored))

    return inserted


def _fetch_random_questions_sync(
    module: str | None,
    knowledge_tag: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    is_subjective_filter = bool(
        knowledge_tag
        and any(prefix in knowledge_tag for prefix in ("简答题", "材料分析", "主观题"))
    )
    params: dict[str, Any] = {"limit": limit}
    clauses = []
    if module:
        clauses.append("module LIKE :module")
        params["module"] = f"%{module}%"
    if knowledge_tag and not is_subjective_filter:
        clauses.append("knowledge_tag LIKE :knowledge_tag")
        params["knowledge_tag"] = f"%{knowledge_tag}%"

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = text(
        f"""
        SELECT id, question_text, option_a, option_b, option_c, option_d,
               module, knowledge_tag, difficulty, source_name, source_question_no
        FROM questions
        {where_sql}
        ORDER BY RAND()
        LIMIT :limit
        """
    )

    try:
        with SessionLocal() as db:
            rows = db.execute(query, params).mappings().all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="题库暂不可用，请检查 MySQL 和 questions 表。",
        ) from exc

    questions = [_question_row_to_dict(row) for row in rows]
    if len(questions) < limit:
        csv_rows = _load_csv_question_rows()
        if module:
            csv_rows = [row for row in csv_rows if module in row["module"] or module in row["knowledge_tag"]]
        if knowledge_tag and not is_subjective_filter:
            csv_rows = [row for row in csv_rows if knowledge_tag in row["knowledge_tag"]]
        existing_keys = {
            (question.get("source_name"), question.get("source_question_no"))
            for question in questions
        }
        csv_rows = [
            row for row in csv_rows
            if (row["source_name"], row["source_question_no"]) not in existing_keys
        ]
        needed = max(limit - len(questions), 0)
        sample = random.sample(csv_rows, min(needed, len(csv_rows))) if csv_rows else []
        try:
            questions.extend(_ensure_csv_questions_in_db(sample))
        except SQLAlchemyError:
            pass

    supplemental = [
        _public_supplemental_question(question)
        for question in SUPPLEMENTAL_QUESTIONS
        if _supplemental_matches(question, module, knowledge_tag)
    ]
    if supplemental:
        random.shuffle(supplemental)
        if is_subjective_filter:
            questions = supplemental
        elif len(questions) < limit:
            questions.extend(supplemental[: max(limit - len(questions), 1)])
        elif limit >= 5 and all(question.get("question_type") == "choice" for question in questions):
            mixed_subjective = []
            for question_type in ("short_answer", "analysis"):
                matched = next(
                    (question for question in supplemental if question.get("question_type") == question_type),
                    None,
                )
                if matched:
                    mixed_subjective.append(matched)
            if mixed_subjective:
                questions[-len(mixed_subjective):] = mixed_subjective
        elif limit >= 3 and all(question.get("question_type") == "choice" for question in questions):
            questions[-1] = supplemental[0]

    random.shuffle(questions)
    return questions[:limit]


def _fetch_question_answer_sync(question_id: int) -> dict[str, Any] | None:
    query = text(
        """
        SELECT id, correct_answer, module, knowledge_tag
        FROM questions
        WHERE id = :question_id
        LIMIT 1
        """
    )
    with SessionLocal() as db:
        row = db.execute(query, {"question_id": question_id}).mappings().first()
    return dict(row) if row else None


def _supplemental_by_id(question_id: int) -> dict[str, Any] | None:
    return next((question for question in SUPPLEMENTAL_QUESTIONS if question["id"] == question_id), None)


def _ensure_subjective_records_table(db: Any) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS subjective_practice_records (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主观题记录ID',
              task_id VARCHAR(64) NOT NULL COMMENT '练习任务ID',
              user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
              question_id BIGINT UNSIGNED NOT NULL COMMENT '主观题ID',
              question_type VARCHAR(32) NOT NULL COMMENT '题型',
              module VARCHAR(50) NOT NULL COMMENT '所属模块',
              knowledge_tag VARCHAR(100) NOT NULL COMMENT '知识点标签',
              answer_text LONGTEXT NOT NULL COMMENT '用户答案',
              reference_answer LONGTEXT NOT NULL COMMENT '参考答案',
              score TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '关键词评分',
              time_spent_seconds INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '作答耗时（秒）',
              practice_mode ENUM('daily','chapter','mock','wrong_book','custom') NOT NULL DEFAULT 'custom' COMMENT '练习模式',
              answered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作答时间',
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
              PRIMARY KEY (id),
              KEY idx_subjective_user_time (user_id, answered_at),
              KEY idx_subjective_task (task_id),
              KEY idx_subjective_module_tag (module, knowledge_tag)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='主观题做题记录表'
            """
        )
    )


def _score_subjective_answer(answer_text: str, reference_points: list[str]) -> int:
    if not answer_text.strip():
        return 0
    hit_count = sum(1 for point in reference_points if point and point in answer_text)
    base = min(round(hit_count / max(len(reference_points), 1) * 85), 85)
    length_bonus = 15 if len(answer_text.strip()) >= 40 else 5
    return min(base + length_bonus, 100)


def _submit_subjective_answer_sync(payload: AnswerSubmissionRequest, question: dict[str, Any]) -> dict[str, Any]:
    answer_text = (payload.answer_text or "").strip()
    if not answer_text:
        raise HTTPException(status_code=422, detail="请先填写简答题答案。")

    score = _score_subjective_answer(answer_text, question["reference_points"])
    query = text(
        """
        INSERT INTO subjective_practice_records (
          task_id, user_id, question_id, question_type, module, knowledge_tag,
          answer_text, reference_answer, score, time_spent_seconds, practice_mode
        )
        VALUES (
          :task_id, :user_id, :question_id, :question_type, :module, :knowledge_tag,
          :answer_text, :reference_answer, :score, :time_spent_seconds, :practice_mode
        )
        """
    )
    try:
        with SessionLocal() as db:
            _ensure_subjective_records_table(db)
            db.execute(
                query,
                {
                    "task_id": payload.task_id,
                    "user_id": payload.user_id,
                    "question_id": payload.question_id,
                    "question_type": question["question_type"],
                    "module": question["module"],
                    "knowledge_tag": question["knowledge_tag"],
                    "answer_text": answer_text,
                    "reference_answer": question["reference_answer"],
                    "score": score,
                    "time_spent_seconds": payload.time_spent_seconds,
                    "practice_mode": payload.practice_mode,
                },
            )
            db.commit()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="主观题记录保存失败。") from exc

    records = _fetch_combined_recent_records(payload.user_id, limit=200)
    return {
        "question_id": payload.question_id,
        "question_type": question["question_type"],
        "score": score,
        "is_correct": score >= 60,
        "reference_answer": question["reference_answer"],
        "reference_points": question["reference_points"],
        "scores": _scores_from_records(records),
        "recent_record_count": len(records),
    }


def _ensure_practice_records_shape(db: Any) -> None:
    has_task_id = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'practice_records'
              AND column_name = 'task_id'
            """
        )
    ).scalar()
    if not has_task_id:
        db.execute(
            text(
                """
                ALTER TABLE practice_records
                ADD COLUMN task_id VARCHAR(64) NOT NULL DEFAULT 'legacy' COMMENT '练习任务ID'
                AFTER id
                """
            )
        )
        db.execute(text("ALTER TABLE practice_records ADD KEY idx_practice_records_task (task_id)"))
        db.execute(text("ALTER TABLE practice_records ADD KEY idx_practice_records_user_task (user_id, task_id)"))


def _submit_answer_sync(payload: AnswerSubmissionRequest) -> dict[str, Any]:
    supplemental = _supplemental_by_id(payload.question_id)
    if supplemental:
        return _submit_subjective_answer_sync(payload, supplemental)

    question = _fetch_question_answer_sync(payload.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在。")
    if not payload.selected_answer:
        raise HTTPException(status_code=422, detail="请选择一个选项。")

    is_correct = payload.selected_answer == question["correct_answer"]
    query = text(
        """
        INSERT INTO practice_records (
          task_id, user_id, question_id, selected_answer, is_correct,
          time_spent_seconds, practice_mode
        )
        VALUES (
          :task_id, :user_id, :question_id, :selected_answer, :is_correct,
          :time_spent_seconds, :practice_mode
        )
        """
    )
    try:
        with SessionLocal() as db:
            _ensure_practice_records_shape(db)
            db.execute(
                query,
                {
                    "task_id": payload.task_id,
                    "user_id": payload.user_id,
                    "question_id": payload.question_id,
                    "selected_answer": payload.selected_answer,
                    "is_correct": int(is_correct),
                    "time_spent_seconds": payload.time_spent_seconds,
                    "practice_mode": payload.practice_mode,
                },
            )
            db.commit()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="做题记录保存失败，请确认 practice_records 表和外键数据。",
        ) from exc

    records = _fetch_combined_recent_records(payload.user_id, limit=200)
    return {
        "question_id": payload.question_id,
        "selected_answer": payload.selected_answer,
        "correct_answer": str(question["correct_answer"]),
        "is_correct": is_correct,
        "scores": _scores_from_records(records),
        "recent_record_count": len(records),
    }


def _fetch_subjective_records_sync(user_id: int, limit: int = 200) -> list[dict[str, Any]]:
    query = text(
        """
        SELECT
          id AS record_id,
          task_id,
          question_id,
          module,
          knowledge_tag,
          3 AS difficulty,
          NULL AS selected_answer,
          NULL AS correct_answer,
          CASE WHEN score >= 60 THEN 1 ELSE 0 END AS is_correct,
          time_spent_seconds,
          practice_mode,
          answered_at
        FROM subjective_practice_records
        WHERE user_id = :user_id
        ORDER BY answered_at DESC, id DESC
        LIMIT :limit
        """
    )
    try:
        with SessionLocal() as db:
            _ensure_subjective_records_table(db)
            rows = db.execute(query, {"user_id": user_id, "limit": limit}).mappings().all()
    except SQLAlchemyError:
        return []
    return [dict(row) for row in rows]


def _fetch_combined_recent_records(user_id: int, limit: int = 200) -> list[dict[str, Any]]:
    records = _fetch_recent_records(user_id, limit)
    records.extend(_fetch_subjective_records_sync(user_id, limit))
    return sorted(
        records,
        key=lambda item: str(item.get("answered_at") or ""),
        reverse=True,
    )[:limit]


def _ensure_user_goal_table(db: Any) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_goal_settings (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '目标设置ID',
              user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
              target_score DECIMAL(5,1) NOT NULL DEFAULT 78.0 COMMENT '目标分数',
              exam_date DATE NOT NULL COMMENT '目标考试日期',
              target_exam VARCHAR(128) NOT NULL DEFAULT '国考' COMMENT '目标考试',
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
              PRIMARY KEY (id),
              UNIQUE KEY uk_user_goal_settings_user (user_id),
              CONSTRAINT fk_user_goal_settings_user
                FOREIGN KEY (user_id) REFERENCES users (id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户目标设置表'
            """
        )
    )


def _default_exam_date() -> date:
    today = date.today()
    target = date(today.year, 12, 1)
    if target <= today:
        target = date(today.year + 1, 12, 1)
    return target


def _goal_payload(row: Any | None, user_id: int) -> dict[str, Any]:
    if not row:
        exam_date = _default_exam_date()
        target_score = 78.0
        target_exam = "国考"
    else:
        target_score = float(row["target_score"])
        exam_date = row["exam_date"]
        target_exam = str(row["target_exam"])

    remaining_days = max((exam_date - date.today()).days, 0)
    return {
        "user_id": user_id,
        "target_score": target_score,
        "exam_date": exam_date.isoformat(),
        "target_exam": target_exam,
        "remaining_days": remaining_days,
    }


def _get_user_goal_sync(user_id: int) -> dict[str, Any]:
    query = text(
        """
        SELECT user_id, target_score, exam_date, target_exam
        FROM user_goal_settings
        WHERE user_id = :user_id
        LIMIT 1
        """
    )
    try:
        with SessionLocal() as db:
            _ensure_user_goal_table(db)
            db.commit()
            row = db.execute(query, {"user_id": user_id}).mappings().first()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="目标设置表暂不可用。") from exc
    return _goal_payload(row, user_id)


def _save_user_goal_sync(payload: UserGoalRequest) -> dict[str, Any]:
    query = text(
        """
        INSERT INTO user_goal_settings (user_id, target_score, exam_date, target_exam)
        VALUES (:user_id, :target_score, :exam_date, :target_exam)
        ON DUPLICATE KEY UPDATE
          target_score = VALUES(target_score),
          exam_date = VALUES(exam_date),
          target_exam = VALUES(target_exam),
          updated_at = CURRENT_TIMESTAMP
        """
    )
    try:
        with SessionLocal() as db:
            _ensure_user_goal_table(db)
            db.execute(query, payload.model_dump())
            db.commit()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="目标设置保存失败。") from exc
    return _get_user_goal_sync(payload.user_id)


def _question_type_counts_sync() -> list[dict[str, Any]]:
    query = text(
        """
        SELECT module, knowledge_tag, COUNT(*) AS total
        FROM questions
        GROUP BY module, knowledge_tag
        ORDER BY module, total DESC
        """
    )
    try:
        with SessionLocal() as db:
            rows = db.execute(query).mappings().all()
    except SQLAlchemyError:
        rows = []

    if rows:
        counts = [
            {
                "module": str(row["module"]),
                "knowledge_tag": str(row["knowledge_tag"] or "综合"),
                "total": int(row["total"]),
            }
            for row in rows
        ]
        for question in SUPPLEMENTAL_QUESTIONS:
            counts.append(
                {
                    "module": question["module"],
                    "knowledge_tag": f"{'简答题' if question['question_type'] == 'short_answer' else '材料分析'}-{question['knowledge_tag']}",
                    "total": 1,
                }
            )
        return counts

    counts: dict[tuple[str, str], int] = {}
    for row in _load_csv_question_rows():
        key = (row["module"], row["knowledge_tag"])
        counts[key] = counts.get(key, 0) + 1
    counts_list = [
        {"module": module, "knowledge_tag": tag, "total": total}
        for (module, tag), total in sorted(counts.items())
    ]
    for question in SUPPLEMENTAL_QUESTIONS:
        counts_list.append(
            {
                "module": question["module"],
                "knowledge_tag": f"{'简答题' if question['question_type'] == 'short_answer' else '材料分析'}-{question['knowledge_tag']}",
                "total": 1,
            }
        )
    return counts_list


def _ensure_study_plan_table(db: Any) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_study_plans (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '备考方案ID',
              user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
              exam_type VARCHAR(64) NOT NULL COMMENT '考试类型',
              job_category VARCHAR(128) NOT NULL COMMENT '岗位类别',
              plan_name VARCHAR(128) NOT NULL COMMENT '方案名称',
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
              PRIMARY KEY (id),
              UNIQUE KEY uk_user_study_plans_user (user_id),
              KEY idx_user_study_plans_exam (exam_type, job_category),
              CONSTRAINT fk_user_study_plans_user
                FOREIGN KEY (user_id) REFERENCES users (id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户备考方案表'
            """
        )
    )

def _save_chat_message(user_id: int, session_id: str, role: str, content: str) -> None:
    query = text(
        """
        INSERT INTO chat_messages (session_id, user_id, role, content)
        VALUES (:session_id, :user_id, :role, :content)
        """
    )

    try:
        with SessionLocal() as db:
            db.execute(
                query,
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "role": role,
                    "content": content,
                },
            )
            db.commit()
    except SQLAlchemyError:
        # 聊天本身不应因为历史表未创建而中断；历史接口会给出明确错误。
        return


def _load_chat_context(user_id: int, session_id: str, limit: int = 10) -> list[dict[str, str]]:
    query = text(
        """
        SELECT role, content
        FROM (
          SELECT id, role, content, created_at
          FROM chat_messages
          WHERE user_id = :user_id AND session_id = :session_id
          ORDER BY created_at DESC, id DESC
          LIMIT :limit
        ) AS recent_messages
        ORDER BY created_at ASC, id ASC
        """
    )

    try:
        with SessionLocal() as db:
            rows = db.execute(
                query,
                {"user_id": user_id, "session_id": session_id, "limit": limit},
            ).mappings().all()
    except SQLAlchemyError:
        return []

    return [
        {"role": str(row["role"]), "content": str(row["content"])}
        for row in rows
        if row["role"] in {"user", "assistant"}
    ]


def _fetch_chat_history_sync(
    user_id: int,
    session_id: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"user_id": user_id, "limit": limit, "offset": offset}
    where_clause = "WHERE user_id = :user_id"
    if session_id:
        where_clause += " AND session_id = :session_id"
        params["session_id"] = session_id

    query = text(
        f"""
        SELECT id, session_id, user_id, role, content, created_at
        FROM chat_messages
        {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
        """
    )

    try:
        with SessionLocal() as db:
            rows = db.execute(query, params).mappings().all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="聊天历史表暂不可用，请先执行 scripts/add_chat_and_plan_tables.sql。",
        ) from exc

    return [
        {
            "id": int(row["id"]),
            "session_id": str(row["session_id"]),
            "user_id": int(row["user_id"]),
            "role": str(row["role"]),
            "content": str(row["content"]),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


def _fetch_chat_sessions_sync(user_id: int, limit: int) -> list[dict[str, Any]]:
    query = text(
        """
        SELECT
          session_id,
          MAX(created_at) AS last_message_at,
          COUNT(*) AS message_count
        FROM chat_messages
        WHERE user_id = :user_id
        GROUP BY session_id
        ORDER BY last_message_at DESC
        LIMIT :limit
        """
    )

    try:
        with SessionLocal() as db:
            rows = db.execute(query, {"user_id": user_id, "limit": limit}).mappings().all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="聊天会话表暂不可用，请先执行 scripts/add_chat_and_plan_tables.sql。",
        ) from exc

    return [
        {
            "session_id": str(row["session_id"]),
            "last_message_at": row["last_message_at"].isoformat() if row["last_message_at"] else None,
            "message_count": int(row["message_count"]),
        }
        for row in rows
    ]


def _save_study_plan_sync(payload: StudyPlanRequest) -> dict[str, Any]:
    query = text(
        """
        INSERT INTO user_study_plans (user_id, exam_type, job_category, plan_name)
        VALUES (:user_id, :exam_type, :job_category, :plan_name)
        ON DUPLICATE KEY UPDATE
          exam_type = VALUES(exam_type),
          job_category = VALUES(job_category),
          plan_name = VALUES(plan_name),
          updated_at = CURRENT_TIMESTAMP
        """
    )

    try:
        with SessionLocal() as db:
            _ensure_study_plan_table(db)
            db.execute(query, payload.model_dump())
            db.commit()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="备考方案表暂不可用，请先执行 scripts/add_chat_and_plan_tables.sql。",
        ) from exc

    return {
        "user_id": payload.user_id,
        "exam_type": payload.exam_type,
        "job_category": payload.job_category,
        "plan_name": payload.plan_name,
        "message": "备考方案已保存",
    }


def _get_study_plan_sync(user_id: int) -> dict[str, Any] | None:
    query = text(
        """
        SELECT user_id, exam_type, job_category, plan_name, updated_at
        FROM user_study_plans
        WHERE user_id = :user_id
        LIMIT 1
        """
    )

    try:
        with SessionLocal() as db:
            _ensure_study_plan_table(db)
            db.commit()
            row = db.execute(query, {"user_id": user_id}).mappings().first()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="备考方案表暂不可用，请先执行 scripts/add_chat_and_plan_tables.sql。",
        ) from exc

    if not row:
        return None

    return {
        "user_id": int(row["user_id"]),
        "exam_type": str(row["exam_type"]),
        "job_category": str(row["job_category"]),
        "plan_name": str(row["plan_name"]),
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/score-lines")
async def score_lines(year: int | None = Query(default=None, ge=2020, le=2100)) -> dict[str, Any]:
    current_year = date.today().year
    available_years = sorted(
        {item["year"] for group in SCORE_LINE_GROUPS for item in group["items"] if item["year"] <= current_year},
        reverse=True,
    )
    selected_year = year or (available_years[0] if available_years else current_year)
    groups: list[dict[str, Any]] = []
    for group in SCORE_LINE_GROUPS:
        items = [item for item in group["items"] if item["year"] == selected_year]
        if items:
            groups.append({"province": group["province"], "items": items})

    return {
        "current_year": current_year,
        "selected_year": selected_year,
        "available_years": available_years,
        "groups": groups,
    }


@router.get("/user-goals")
async def get_user_goal(user_id: int = Query(default=1, ge=1)) -> dict[str, Any]:
    return await asyncio.to_thread(_get_user_goal_sync, user_id)


@router.post("/user-goals")
async def save_user_goal(payload: UserGoalRequest) -> dict[str, Any]:
    return await asyncio.to_thread(_save_user_goal_sync, payload)


@router.get("/question-types")
async def question_types() -> dict[str, Any]:
    counts = await asyncio.to_thread(_question_type_counts_sync)
    return {
        "modules": PRACTICE_MODULES,
        "counts": counts,
    }


@router.get("/practice/random")
async def random_practice(
    module: str | None = Query(default=None, max_length=64),
    knowledge_tag: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=5, ge=1, le=50),
    mode: str = Query(default="custom", pattern="^(daily|chapter|mock|wrong_book|custom)$"),
) -> dict[str, Any]:
    questions = await asyncio.to_thread(_fetch_random_questions_sync, module, knowledge_tag, limit)
    fallback_used = False
    if not questions and module and knowledge_tag:
        questions = await asyncio.to_thread(_fetch_random_questions_sync, module, None, limit)
        fallback_used = True
    if not questions and (module or knowledge_tag):
        questions = await asyncio.to_thread(_fetch_random_questions_sync, None, None, limit)
        fallback_used = True
    return {
        "task_id": str(uuid.uuid4()),
        "mode": mode,
        "module": module,
        "knowledge_tag": knowledge_tag,
        "fallback_used": fallback_used,
        "questions": questions,
    }


@router.get("/mock-exam")
async def mock_exam(
    limit: int = Query(default=20, ge=5, le=135),
) -> dict[str, Any]:
    questions = await asyncio.to_thread(_fetch_random_questions_sync, None, None, limit)
    return {
        "task_id": str(uuid.uuid4()),
        "mode": "mock",
        "duration_minutes": max(20, round(limit * 0.8)),
        "questions": questions,
    }


@router.post("/practice/submit")
async def submit_answer(payload: AnswerSubmissionRequest) -> dict[str, Any]:
    return await asyncio.to_thread(_submit_answer_sync, payload)


@router.get("/study-plans/options")
async def study_plan_options() -> dict[str, Any]:
    return {"options": PLAN_OPTIONS}


@router.get("/study-plans/current")
async def current_study_plan(user_id: int = Query(default=1, ge=1)) -> dict[str, Any]:
    current = await asyncio.to_thread(_get_study_plan_sync, user_id)
    return {"user_id": user_id, "plan": current}


@router.post("/study-plans/select")
async def select_study_plan(payload: StudyPlanRequest) -> dict[str, Any]:
    return await asyncio.to_thread(_save_study_plan_sync, payload)


@router.get("/diagnose")
async def diagnose_user(user_id: int = Query(default=1, ge=1)) -> dict[str, Any]:
    records = await asyncio.to_thread(_fetch_combined_recent_records, user_id)
    diagnosis_text = await asyncio.to_thread(diagnose, records)
    scores = _scores_from_records(records)

    return {
        "user_id": user_id,
        "diagnosis": diagnosis_text,
        "scores": scores,
        "recent_record_count": len(records),
    }


@router.get("/recommend")
async def recommend(
    strategy: str = Query(default=DEFAULT_STRATEGY),
    limit: int = Query(default=10, ge=1, le=20),
) -> dict[str, Any]:
    questions = await asyncio.to_thread(recommend_questions, strategy, limit)
    if not questions:
        questions = _fallback_recommendations()[:limit]

    return {
        "strategy": strategy,
        "questions": questions,
    }


async def _chat_event_stream(request: ChatRequest):
    session_id = _normalize_session_id(request.session_id)
    previous_messages = await asyncio.to_thread(
        _load_chat_context,
        request.user_id,
        session_id,
    )
    messages = [
        {
            "role": "system",
            "content": CHAT_SYSTEM_PROMPT,
        },
        *previous_messages,
        {"role": "user", "content": request.message},
    ]
    reply = await asyncio.to_thread(call_llm, messages)
    if not reply:
        reply = "我建议先做一组判断推理，再复盘错因。"

    await asyncio.to_thread(_save_chat_message, request.user_id, session_id, "user", request.message)
    await asyncio.to_thread(_save_chat_message, request.user_id, session_id, "assistant", reply)

    yield f"data: {json.dumps({'session_id': session_id}, ensure_ascii=False)}\n\n"

    for char in reply:
        payload = json.dumps({"delta": char}, ensure_ascii=False)
        yield f"data: {payload}\n\n"
        await asyncio.sleep(0.03)

    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _chat_event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history")
async def chat_history(
    user_id: int = Query(default=1, ge=1),
    session_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    normalized_session = _normalize_session_id(session_id) if session_id else None
    messages = await asyncio.to_thread(
        _fetch_chat_history_sync,
        user_id,
        normalized_session,
        limit,
        offset,
    )
    return {
        "user_id": user_id,
        "session_id": normalized_session,
        "messages": messages,
    }


@router.get("/chat/sessions")
async def chat_sessions(
    user_id: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    sessions = await asyncio.to_thread(_fetch_chat_sessions_sync, user_id, limit)
    return {"user_id": user_id, "sessions": sessions}
