"""Build demo data for the undergraduate math tutor system.

The generated questions are original demonstration items. Public learning
resources are used only as topic-structure references, not copied as a bank.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
QUESTIONS_PATH = DATA_DIR / "math_questions.csv"
GRAPH_PATH = DATA_DIR / "math_knowledge_graph.json"


STAGES = [
    {
        "stage": "大一",
        "title": "基础建模期",
        "goal": "建立极限、导数、矩阵和证明语言的底层直觉。",
        "courses": [
            {
                "course": "高等数学上",
                "group": "高等数学",
                "topics": [
                    ("极限与连续", ["等价无穷小", "夹逼定理", "间断点分类"]),
                    ("一元微分学", ["导数定义", "隐函数求导", "中值定理"]),
                    ("一元积分学", ["换元积分", "分部积分", "定积分应用"]),
                ],
            },
            {
                "course": "线性代数基础",
                "group": "线性代数",
                "topics": [
                    ("矩阵运算", ["矩阵乘法", "逆矩阵", "初等变换"]),
                    ("行列式", ["按行展开", "性质化简", "克拉默法则"]),
                    ("线性方程组", ["秩判定", "齐次方程", "非齐次方程"]),
                ],
            },
            {
                "course": "证明方法入门",
                "group": "数学分析",
                "topics": [
                    ("命题与量词", ["必要充分条件", "否命题", "全称存在量词"]),
                    ("常用证明法", ["反证法", "数学归纳法", "构造法"]),
                ],
            },
        ],
    },
    {
        "stage": "大二",
        "title": "多变量与概率期",
        "goal": "掌握多元微积分、级数、微分方程和概率统计的核心工具。",
        "courses": [
            {
                "course": "高等数学下",
                "group": "高等数学",
                "topics": [
                    ("多元微分学", ["偏导数", "方向导数", "条件极值"]),
                    ("重积分", ["二重积分", "极坐标变换", "换元雅可比"]),
                    ("曲线曲面积分", ["第一型曲线积分", "格林公式", "高斯公式"]),
                ],
            },
            {
                "course": "级数与常微分方程",
                "group": "高等数学",
                "topics": [
                    ("数项级数", ["比较判别法", "比值判别法", "交错级数"]),
                    ("幂级数", ["收敛半径", "泰勒展开", "逐项积分"]),
                    ("常微分方程", ["一阶线性方程", "可分离变量", "二阶常系数"]),
                ],
            },
            {
                "course": "概率论与数理统计",
                "group": "概率统计",
                "topics": [
                    ("随机事件", ["条件概率", "全概率公式", "贝叶斯公式"]),
                    ("随机变量", ["分布函数", "数学期望", "方差"]),
                    ("统计推断", ["参数估计", "置信区间", "假设检验"]),
                ],
            },
        ],
    },
    {
        "stage": "大三",
        "title": "专业核心期",
        "goal": "进入数学专业主干课程，训练抽象结构、严格分析和数值算法。",
        "courses": [
            {
                "course": "复变函数",
                "group": "专业核心",
                "topics": [
                    ("解析函数", ["柯西-黎曼方程", "调和函数", "初等函数"]),
                    ("留数理论", ["孤立奇点", "留数计算", "围道积分"]),
                ],
            },
            {
                "course": "实变函数",
                "group": "数学分析",
                "topics": [
                    ("测度基础", ["可测集", "零测集", "外测度"]),
                    ("勒贝格积分", ["简单函数", "控制收敛", "单调收敛"]),
                ],
            },
            {
                "course": "抽象代数",
                "group": "专业核心",
                "topics": [
                    ("群论基础", ["子群判定", "陪集", "拉格朗日定理"]),
                    ("环与域", ["理想", "商环", "域扩张入门"]),
                ],
            },
            {
                "course": "数值分析",
                "group": "专业核心",
                "topics": [
                    ("插值与逼近", ["拉格朗日插值", "误差估计", "最小二乘"]),
                    ("数值线性代数", ["高斯消元", "迭代法", "条件数"]),
                ],
            },
        ],
    },
    {
        "stage": "大四",
        "title": "综合提升期",
        "goal": "将高阶课程、建模和综合应用连接成可复用的问题解决框架。",
        "courses": [
            {
                "course": "拓扑学基础",
                "group": "专业核心",
                "topics": [
                    ("点集拓扑", ["开集闭集", "连续映射", "紧致性"]),
                    ("连通性", ["连通空间", "道路连通", "分离公理"]),
                ],
            },
            {
                "course": "微分几何基础",
                "group": "专业核心",
                "topics": [
                    ("曲线论", ["弧长参数", "曲率", "挠率"]),
                    ("曲面论", ["第一基本形式", "第二基本形式", "高斯曲率"]),
                ],
            },
            {
                "course": "泛函分析入门",
                "group": "专业核心",
                "topics": [
                    ("赋范空间", ["范数", "完备性", "线性算子"]),
                    ("内积空间", ["正交投影", "希尔伯特空间", "有界泛函"]),
                ],
            },
            {
                "course": "数学建模与综合专题",
                "group": "综合应用",
                "topics": [
                    ("建模流程", ["变量定义", "假设检验", "模型评价"]),
                    ("优化模型", ["线性规划", "整数规划", "灵敏度分析"]),
                ],
            },
        ],
    },
]

QUESTION_TYPES = ["choice", "blank", "calculation", "proof", "comprehensive"]
TYPE_LABELS = {
    "choice": "选择题",
    "blank": "填空题",
    "calculation": "计算题",
    "proof": "证明题",
    "comprehensive": "综合题",
}


def build_graph() -> dict[str, object]:
    return {
        "name": "本科数学知识图谱",
        "description": "覆盖高等数学与数学专业本科四年核心课程，不含研究生及以上内容。",
        "sources": [
            {
                "name": "MIT OCW 18.01SC Single Variable Calculus",
                "url": "https://ocw.mit.edu/courses/18-01sc-single-variable-calculus-fall-2010/",
                "usage": "参考单变量微积分主题顺序",
            },
            {
                "name": "OpenStax Calculus Volume 1",
                "url": "https://openstax.org/details/books/calculus-volume-1",
                "usage": "参考开放教材章节覆盖范围",
            },
            {
                "name": "Paul's Online Math Notes",
                "url": "https://tutorial.math.lamar.edu/problems/calci/calci.aspx",
                "usage": "参考练习分类粒度",
            },
        ],
        "stages": [
            {
                "name": stage["stage"],
                "title": stage["title"],
                "goal": stage["goal"],
                "children": [
                    {
                        "name": course["course"],
                        "group": course["group"],
                        "children": [
                            {
                                "name": topic,
                                "children": [{"name": leaf} for leaf in leaves],
                            }
                            for topic, leaves in course["topics"]
                        ],
                    }
                    for course in stage["courses"]
                ],
            }
            for stage in STAGES
        ],
    }


def choice_question(index: int, stage: str, course: str, topic: str, leaf: str, difficulty: int) -> dict[str, str]:
    variants = [
        (
            f"关于“{leaf}”在{course}中的作用，下列说法最准确的是哪一项？",
            "只需要记住公式，不需要理解条件",
            "先判断适用条件，再选择相应定理或方法",
            "遇到该知识点时都可以直接套用同一个模板",
            "该知识点只会出现在选择题中",
            "B",
        ),
        (
            f"学习{topic}时，处理“{leaf}”类题目的第一步通常应当是：",
            "直接化简最终答案",
            "先写出定义、条件或对象之间的关系",
            "跳过题干中的限制条件",
            "只比较选项长短",
            "B",
        ),
        (
            f"如果一道题考查{leaf}，最容易导致失分的做法是：",
            "检查定义域、条件和符号",
            "把关键步骤写成等价变形",
            "忽略定理成立条件直接使用结论",
            "做完后回代验证",
            "C",
        ),
    ]
    stem, a, b, c, d, answer = variants[index % len(variants)]
    analysis = f"本题考查{stage}{course}中的{topic}。{leaf}类题目的核心不是背单个结论，而是先确认对象、条件和可用工具。"
    return {
        "question_type": "choice",
        "stage": stage,
        "course": course,
        "knowledge_tag": topic,
        "fine_tag": leaf,
        "difficulty": str(difficulty),
        "question_text": stem,
        "option_a": a,
        "option_b": b,
        "option_c": c,
        "option_d": d,
        "correct_answer": answer,
        "standard_answer": answer,
        "analysis": analysis,
        "key_steps": json.dumps(["识别知识点", "核对适用条件", "排除错误表述"], ensure_ascii=False),
        "common_errors": json.dumps(["只记结论", "忽略条件", "把相近概念混用"], ensure_ascii=False),
        "mistake_tags": json.dumps(["概念不清", "条件遗漏"], ensure_ascii=False),
    }


def subjective_question(
    qtype: str,
    stage: str,
    course: str,
    topic: str,
    leaf: str,
    difficulty: int,
) -> dict[str, str]:
    if qtype == "blank":
        text = f"填空题：在{course}的{topic}中，处理“{leaf}”问题时，必须先写清楚的两个要素是____和____。"
        answer = "对象；适用条件"
        analysis = f"{leaf}题目容易因为对象不明或条件遗漏而失分。先写对象，再写定理或公式成立条件。"
        steps = ["确定题目对象", "列出适用条件", "再进行计算或证明"]
        errors = ["把结论当定义", "条件没有写全"]
        tags = ["概念不清", "条件遗漏"]
    elif qtype == "calculation":
        text = f"计算题：围绕{course}中的“{leaf}”，给出一个标准解题流程，并说明每一步为什么必要。"
        answer = f"先确定{leaf}的适用范围，再把题目转化为{topic}中的标准形式，最后计算并回代检查。"
        analysis = f"计算题的评分点通常分布在建模、变形、计算和检验四步，只有最终数值没有过程会丢分。"
        steps = ["写出已知条件", "转化为标准形式", "逐步计算", "回代或检验"]
        errors = ["跳步严重", "符号混乱", "没有检查结果"]
        tags = ["计算失误", "步骤缺失"]
    elif qtype == "proof":
        text = f"证明题：请证明或说明{topic}中“{leaf}”相关结论时，应如何组织证明结构。"
        answer = f"可按定义展开、关键条件验证、推出目标结论三段组织；必要时使用反证法、归纳法或构造辅助对象。"
        analysis = f"证明题强调逻辑链完整。{leaf}相关证明要避免只写直觉，应明确每一步依赖的定义或定理。"
        steps = ["写出目标命题", "展开定义", "引用定理并说明条件", "得到结论"]
        errors = ["把例子当证明", "缺少量词说明", "没有说明定理条件"]
        tags = ["证明断链", "定义不熟"]
    else:
        text = f"综合题：某同学在{course}的{topic}训练中，连续错在“{leaf}”。请分析可能薄弱点，并给出三天补救计划。"
        answer = f"薄弱点可能是概念条件、基本运算和题型识别。第1天回看定义并做基础题，第2天做中档题并整理错因，第3天混合测试并复盘。"
        analysis = f"综合题要求把诊断和学习计划连起来。{leaf}连续出错时，先区分是不会、算慢还是证明表达不完整。"
        steps = ["归因错误类型", "安排基础回炉", "安排专项训练", "设置复测"]
        errors = ["只加题量不复盘", "计划没有优先级"]
        tags = ["规划不足", "错因未归类"]

    return {
        "question_type": qtype,
        "stage": stage,
        "course": course,
        "knowledge_tag": topic,
        "fine_tag": leaf,
        "difficulty": str(difficulty),
        "question_text": text,
        "option_a": "",
        "option_b": "",
        "option_c": "",
        "option_d": "",
        "correct_answer": "",
        "standard_answer": answer,
        "analysis": analysis,
        "key_steps": json.dumps(steps, ensure_ascii=False),
        "common_errors": json.dumps(errors, ensure_ascii=False),
        "mistake_tags": json.dumps(tags, ensure_ascii=False),
    }


def iter_questions() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    serial = 1
    for stage_index, stage in enumerate(STAGES, start=1):
        for course in stage["courses"]:
            for topic, leaves in course["topics"]:
                for leaf_index, leaf in enumerate(leaves):
                    qtype = QUESTION_TYPES[(serial + leaf_index) % len(QUESTION_TYPES)]
                    difficulty = min(5, max(1, stage_index + (leaf_index % 2)))
                    if qtype == "choice":
                        row = choice_question(serial, stage["stage"], course["course"], topic, leaf, difficulty)
                    else:
                        row = subjective_question(qtype, stage["stage"], course["course"], topic, leaf, difficulty)
                    row.update(
                        {
                            "id": str(serial),
                            "source_name": "原创演示题库",
                            "source_question_no": f"MATH-{serial:04d}",
                            "source_url": "",
                        }
                    )
                    rows.append(row)
                    serial += 1

                # Add one extra choice item per topic to keep objective practice plentiful.
                row = choice_question(serial, stage["stage"], course["course"], topic, leaves[0], min(5, stage_index + 1))
                row.update(
                    {
                        "id": str(serial),
                        "source_name": "原创演示题库",
                        "source_question_no": f"MATH-{serial:04d}",
                        "source_url": "",
                    }
                )
                rows.append(row)
                serial += 1
    return rows


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    graph = build_graph()
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = iter_questions()
    fieldnames = [
        "id",
        "question_type",
        "stage",
        "course",
        "knowledge_tag",
        "fine_tag",
        "difficulty",
        "question_text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "correct_answer",
        "standard_answer",
        "analysis",
        "key_steps",
        "common_errors",
        "mistake_tags",
        "source_name",
        "source_question_no",
        "source_url",
    ]
    with QUESTIONS_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {GRAPH_PATH}")
    print(f"Wrote {QUESTIONS_PATH} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
