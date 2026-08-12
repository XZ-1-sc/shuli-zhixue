import json

from sqlalchemy import text

from backend.app.database.session import SessionLocal


SOURCE_NAME = "数理智学中文演示题库"


TOPICS = [
    {
        "stage": "大一",
        "course": "高等数学上",
        "knowledge_tag": "极限与连续",
        "fine_tag": "重要极限与等价无穷小",
        "difficulty": 2,
        "choice": (
            "设 x -> 0，求 lim (sin 3x)/(2x)。",
            {"A": "0", "B": "1", "C": "3/2", "D": "2/3"},
            "C",
            "因为 sin 3x ~ 3x，所以 (sin 3x)/(2x) ~ 3x/(2x)=3/2。",
        ),
        "blank": ("若 x -> 0，则 1-cos x 与 x^2 的等价关系为 1-cos x ~ ____。", "x^2/2"),
        "calculation": ("计算 lim_{x->0} (e^{2x}-1-2x)/x^2。", "2"),
        "proof": ("证明函数 f(x)=x^2 在 x=1 处连续。", "证明 lim_{x->1} x^2=1=f(1)，所以连续。"),
        "comprehensive": ("讨论 f(x)=|x|/x 在 x=0 附近的左右极限，并说明 x=0 处极限是否存在。", "左极限为 -1，右极限为 1，左右极限不相等，所以极限不存在。"),
    },
    {
        "stage": "大一",
        "course": "高等数学上",
        "knowledge_tag": "导数",
        "fine_tag": "导数定义与切线斜率",
        "difficulty": 2,
        "choice": (
            "函数 y=x^3 在 x=2 处的导数为多少？",
            {"A": "6", "B": "8", "C": "12", "D": "24"},
            "C",
            "y'=3x^2，代入 x=2 得 12。",
        ),
        "blank": ("若 f'(a)=0 且 f''(a)>0，则 a 通常是函数的____点。", "极小值"),
        "calculation": ("求函数 f(x)=x ln x 的导数。", "f'(x)=ln x+1"),
        "proof": ("用导数定义证明 f(x)=kx+b 的导数为 k。", "差商 [k(x+h)+b-(kx+b)]/h=k，令 h->0 仍为 k。"),
        "comprehensive": ("求曲线 y=x^2 在点 (1,1) 处的切线方程，并说明斜率来源。", "导数 y'=2x，x=1 处斜率为 2，切线为 y-1=2(x-1)。"),
    },
    {
        "stage": "大一",
        "course": "线性代数上",
        "knowledge_tag": "矩阵运算",
        "fine_tag": "矩阵乘法与逆矩阵",
        "difficulty": 2,
        "choice": (
            "若 A 为 2x3 矩阵，B 为 3x4 矩阵，则 AB 的阶数为？",
            {"A": "2x4", "B": "3x3", "C": "4x2", "D": "不可乘"},
            "A",
            "矩阵乘法内侧维数 3 匹配，结果取外侧维数 2x4。",
        ),
        "blank": ("单位矩阵 E 满足 AE=EA=____。", "A"),
        "calculation": ("计算 [[1,2],[3,4]] 的行列式。", "-2"),
        "proof": ("证明若 A 可逆，则齐次方程 Ax=0 只有零解。", "两边左乘 A^{-1}，得 x=A^{-1}0=0。"),
        "comprehensive": ("判断向量 (1,2) 与 (2,4) 是否线性相关，并说明原因。", "线性相关，因为 (2,4)=2(1,2)。"),
    },
    {
        "stage": "大二",
        "course": "高等数学下",
        "knowledge_tag": "多元函数微分",
        "fine_tag": "偏导数与梯度",
        "difficulty": 3,
        "choice": (
            "函数 f(x,y)=x^2y+sin y 对 x 的偏导数为？",
            {"A": "2xy", "B": "x^2+cos y", "C": "2x+y", "D": "x^2y"},
            "A",
            "对 x 求偏导时 y 看作常数，x^2y 的偏导为 2xy，sin y 的偏导为 0。",
        ),
        "blank": ("f(x,y)=x^2+y^2 的梯度为 ____。", "(2x,2y)"),
        "calculation": ("求 f(x,y)=e^{xy} 在点 (0,2) 处对 x 的偏导。", "2"),
        "proof": ("说明可微函数在一点的梯度方向为何是函数增长最快的方向。", "方向导数等于梯度与单位方向向量的内积，由柯西不等式最大值在同向时取得。"),
        "comprehensive": ("求 z=x^2+y^2 在约束 x+y=1 下的最小值。", "令 y=1-x，z=x^2+(1-x)^2，导数 4x-2=0，x=1/2，y=1/2，最小值 1/2。"),
    },
    {
        "stage": "大二",
        "course": "概率论与数理统计",
        "knowledge_tag": "随机变量",
        "fine_tag": "期望与方差",
        "difficulty": 2,
        "choice": (
            "若 X 服从参数为 p 的 0-1 分布，则 E(X)=？",
            {"A": "0", "B": "p", "C": "1-p", "D": "p(1-p)"},
            "B",
            "0-1 分布中 P(X=1)=p，P(X=0)=1-p，因此 E(X)=p。",
        ),
        "blank": ("若 X 与 Y 独立，则 E(XY)=____。", "E(X)E(Y)"),
        "calculation": ("一枚均匀骰子点数 X 的期望是多少？", "7/2"),
        "proof": ("证明任意随机变量 X 的方差 Var(X) >= 0。", "Var(X)=E[(X-E(X))^2]，平方非负，期望也非负。"),
        "comprehensive": ("某事件 A 发生概率 0.3，独立重复 10 次，求恰好发生 2 次的概率表达式。", "C(10,2)·0.3^2·0.7^8。"),
    },
    {
        "stage": "大二",
        "course": "级数与常微分方程",
        "knowledge_tag": "常微分方程",
        "fine_tag": "一阶线性微分方程",
        "difficulty": 3,
        "choice": (
            "微分方程 y'=ky 的通解形式是？",
            {"A": "y=C e^{kx}", "B": "y=kx+C", "C": "y=Cx^k", "D": "y=C sin kx"},
            "A",
            "分离变量 dy/y=k dx，积分得 ln|y|=kx+C，所以 y=C e^{kx}。",
        ),
        "blank": ("级数 sum 1/n^2 是____级数。", "收敛"),
        "calculation": ("求微分方程 y'=2y，且 y(0)=3 的特解。", "y=3e^{2x}"),
        "proof": ("说明调和级数 sum 1/n 发散的基本分组思想。", "按 1/2 +(1/3+1/4)+(1/5+...+1/8)+... 分组，每组不小于 1/2，所以部分和无界。"),
        "comprehensive": ("判断级数 sum (-1)^{n-1}/n 是否收敛，并说明是否绝对收敛。", "由交错级数判别法收敛；绝对值级数为调和级数发散，所以条件收敛。"),
    },
    {
        "stage": "大三",
        "course": "复变函数",
        "knowledge_tag": "解析函数",
        "fine_tag": "柯西-黎曼方程",
        "difficulty": 3,
        "choice": (
            "若 f(z)=u(x,y)+iv(x,y) 在区域内解析，则 u 与 v 满足什么方程？",
            {"A": "柯西-黎曼方程", "B": "牛顿方程", "C": "拉格朗日中值公式", "D": "贝叶斯公式"},
            "A",
            "解析函数的实部和虚部在适当条件下满足 u_x=v_y，u_y=-v_x。",
        ),
        "blank": ("复数 z=a+bi 的模为 ____。", "sqrt(a^2+b^2)"),
        "calculation": ("计算 (1+i)^2。", "2i"),
        "proof": ("说明常值函数一定是解析函数。", "常值函数各阶偏导为 0，柯西-黎曼方程成立，且处处可导。"),
        "comprehensive": ("将 z=1+i 写成三角形式。", "模为 sqrt2，辐角为 pi/4，所以 z=sqrt2(cos pi/4+i sin pi/4)。"),
    },
    {
        "stage": "大四",
        "course": "数学建模与综合专题",
        "knowledge_tag": "优化建模",
        "fine_tag": "线性规划约束",
        "difficulty": 3,
        "choice": (
            "在线性规划中，目标函数和约束条件的共同特点通常是？",
            {"A": "线性", "B": "指数型", "C": "三角型", "D": "随机型"},
            "A",
            "线性规划要求目标函数与约束条件均为变量的线性表达式。",
        ),
        "blank": ("建立数学模型通常包括变量、目标函数、约束条件和____。", "求解与检验"),
        "calculation": ("求 max z=2x+y，约束 x+y<=4，x>=0，y>=0，在点 (4,0) 与 (0,4) 中哪个值更大？", "(4,0) 更大，z=8；(0,4) 时 z=4。"),
        "proof": ("解释为什么线性规划最优解常出现在可行域顶点。", "线性目标函数的等值线平移接触凸多边形可行域时，极值通常在边界顶点取得。"),
        "comprehensive": ("某同学每天有 3 小时复习，计算题每套 40 分钟，证明题每套 60 分钟，至少完成 1 套证明题。建立最大化总训练套数的线性规划模型。", "设计算题 x 套、证明题 y 套，最大化 x+y，约束 40x+60y<=180，y>=1，x,y>=0 且可取整数。"),
    },
]


TYPE_ORDER = ["choice", "blank", "calculation", "proof", "comprehensive"]
TYPE_LABEL = {
    "choice": "选择题",
    "blank": "填空题",
    "calculation": "计算题",
    "proof": "证明题",
    "comprehensive": "综合题",
}


def key_steps(question_type: str) -> list[str]:
    if question_type == "choice":
        return ["识别题目所问知识点", "写出对应公式或定义", "排除干扰选项"]
    if question_type == "blank":
        return ["确定空格对应的概念或结果", "检查单位、符号和定义域", "写出最简答案"]
    if question_type == "calculation":
        return ["列出已知条件", "选择合适公式", "逐步计算并检验结果"]
    if question_type == "proof":
        return ["明确要证明的结论", "展开定义或引用定理", "补齐条件并闭合逻辑链"]
    return ["拆分子问题", "建立模型或表达式", "计算结果并解释含义"]


def main() -> None:
    with SessionLocal() as db:
        source_id = db.execute(
            text(
                """
                INSERT INTO source_attributions
                  (source_name, source_url, license_name, license_url, usage_note)
                VALUES
                  (:source_name, :source_url, :license_name, :license_url, :usage_note)
                ON DUPLICATE KEY UPDATE usage_note = VALUES(usage_note)
                """
            ),
            {
                "source_name": SOURCE_NAME,
                "source_url": "local://curated-math-demo-questions",
                "license_name": "Project curated demo content",
                "license_url": "local://project",
                "usage_note": "为产品演示和教学流程自制的中文样例题，覆盖选择、填空、计算、证明、综合题。",
            },
        ).lastrowid
        if not source_id:
            source_id = db.execute(
                text("SELECT id FROM source_attributions WHERE source_name = :source_name"),
                {"source_name": SOURCE_NAME},
            ).scalar_one()

        inserted = 0
        for topic_index, topic in enumerate(TOPICS, start=1):
            for question_type in TYPE_ORDER:
                payload = topic[question_type]
                if question_type == "choice":
                    question_text, options, correct_answer, standard_answer = payload
                    option_a = options["A"]
                    option_b = options["B"]
                    option_c = options["C"]
                    option_d = options["D"]
                else:
                    question_text, standard_answer = payload
                    option_a = option_b = option_c = option_d = correct_answer = None
                analysis = (
                    topic[question_type][3]
                    if question_type == "choice"
                    else f"本题考查「{topic['fine_tag']}」。参考答案为：{standard_answer}。"
                )
                db.execute(
                    text(
                        """
                        INSERT INTO questions
                          (source_id, source_question_no, source_path, question_type, stage, course,
                           knowledge_node_id, knowledge_tag, fine_tag, difficulty, question_text,
                           option_a, option_b, option_c, option_d, correct_answer, standard_answer,
                           analysis_text, key_steps, common_errors, mistake_tags)
                        VALUES
                          (:source_id, :source_question_no, :source_path, :question_type, :stage, :course,
                           NULL, :knowledge_tag, :fine_tag, :difficulty, :question_text,
                           :option_a, :option_b, :option_c, :option_d, :correct_answer, :standard_answer,
                           :analysis_text, :key_steps, :common_errors, :mistake_tags)
                        ON DUPLICATE KEY UPDATE
                           question_text = VALUES(question_text),
                           standard_answer = VALUES(standard_answer),
                           analysis_text = VALUES(analysis_text),
                           key_steps = VALUES(key_steps),
                           common_errors = VALUES(common_errors),
                           mistake_tags = VALUES(mistake_tags)
                        """
                    ),
                    {
                        "source_id": source_id,
                        "source_question_no": f"CURATED-{topic_index:02d}-{question_type}",
                        "source_path": f"curated/{topic['course']}/{question_type}",
                        "question_type": question_type,
                        "stage": topic["stage"],
                        "course": topic["course"],
                        "knowledge_tag": topic["knowledge_tag"],
                        "fine_tag": topic["fine_tag"],
                        "difficulty": topic["difficulty"],
                        "question_text": f"【{TYPE_LABEL[question_type]}】{question_text}",
                        "option_a": option_a,
                        "option_b": option_b,
                        "option_c": option_c,
                        "option_d": option_d,
                        "correct_answer": correct_answer,
                        "standard_answer": standard_answer,
                        "analysis_text": analysis,
                        "key_steps": json.dumps(key_steps(question_type), ensure_ascii=False),
                        "common_errors": json.dumps(["概念混淆", "公式条件漏看", "计算或符号错误"], ensure_ascii=False),
                        "mistake_tags": json.dumps(["基础概念", "步骤完整性"], ensure_ascii=False),
                    },
                )
                inserted += 1
        db.commit()
    print(f"Seeded or updated {inserted} curated questions.")


if __name__ == "__main__":
    main()
