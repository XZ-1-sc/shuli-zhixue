import json

from sqlalchemy import text

from backend.app.database.session import SessionLocal


SOURCE_NAME = "数理智学中文演示题库"
TYPE_ORDER = ["choice", "blank", "calculation", "proof", "comprehensive"]
TYPE_LABEL = {
    "choice": "选择题",
    "blank": "填空题",
    "calculation": "计算题",
    "proof": "证明题",
    "comprehensive": "综合题",
}


TOPICS = [
    {
        "stage": "大一",
        "course": "高等数学上",
        "knowledge_tag": "不定积分",
        "fine_tag": "换元积分法",
        "difficulty": 2,
        "choice": ("∫2x cos(x^2) dx 的一个原函数是（ ）。", {"A": "sin(x^2)+C", "B": "cos(x^2)+C", "C": "2sin x+C", "D": "x^2 cos x+C"}, "A", "令 u=x^2，则 du=2x dx，原积分化为 ∫cos u du=sin u+C。"),
        "blank": ("若 u=g(x)，则换元积分的核心是把 g'(x)dx 改写为 ____。", "du"),
        "calculation": ("计算 ∫x e^{x^2} dx。", "1/2 e^{x^2}+C"),
        "proof": ("说明换元积分法为什么本质上来自复合函数求导法则。", "若 F'(u)=f(u)，则 [F(g(x))]'=f(g(x))g'(x)，两边反向使用即得到换元积分。"),
        "comprehensive": ("用换元法计算 ∫_0^1 2x/(1+x^2) dx，并说明换元上下限。", "令 u=1+x^2，du=2x dx；x=0 时 u=1，x=1 时 u=2，积分为 ∫_1^2 1/u du=ln2。"),
    },
    {
        "stage": "大一",
        "course": "高等数学上",
        "knowledge_tag": "定积分",
        "fine_tag": "定积分几何意义",
        "difficulty": 2,
        "choice": ("∫_0^2 x dx 的几何意义对应的面积是（ ）。", {"A": "1", "B": "2", "C": "3", "D": "4"}, "B", "y=x 在 [0,2] 下方面积是底为 2、高为 2 的直角三角形面积 2。"),
        "blank": ("定积分 ∫_a^b f(x)dx 在 f(x)>=0 时表示曲线与 x 轴围成的____。", "面积"),
        "calculation": ("计算 ∫_0^1 (3x^2+1) dx。", "2"),
        "proof": ("说明若 f(x)>=0，则 ∫_a^b f(x)dx 不小于 0。", "黎曼和中每一项 f(ξ_i)Δx_i 均非负，极限仍非负。"),
        "comprehensive": ("求 y=x^2 与 x 轴在 [0,2] 上围成的面积。", "面积为 ∫_0^2 x^2 dx=8/3。"),
    },
    {
        "stage": "大二",
        "course": "高等数学下",
        "knowledge_tag": "二重积分",
        "fine_tag": "积分区域与累次积分",
        "difficulty": 3,
        "choice": ("区域 D: 0<=x<=1, 0<=y<=x 上的二重积分顺序为（ ）。", {"A": "∫_0^1∫_0^x f dy dx", "B": "∫_0^1∫_0^y f dx dy", "C": "∫_0^x∫_0^1 f dx dy", "D": "∫_0^1∫_x^1 f dy dx"}, "A", "外层 x 从 0 到 1，内层 y 从 0 到 x。"),
        "blank": ("二重积分换序时，关键是重新描述同一个____。", "积分区域"),
        "calculation": ("计算 ∬_D 1 dA，其中 D: 0<=x<=1, 0<=y<=x。", "1/2"),
        "proof": ("说明二重积分 ∬_D 1 dA 为什么等于区域 D 的面积。", "把区域分割成小块后，函数值恒为 1，黎曼和就是小面积之和，极限为总面积。"),
        "comprehensive": ("将 ∫_0^1∫_0^x f(x,y)dy dx 改写为先对 x 积分。", "区域为 0<=y<=x<=1，换序为 ∫_0^1∫_y^1 f(x,y)dx dy。"),
    },
    {
        "stage": "大一",
        "course": "线性代数上",
        "knowledge_tag": "行列式",
        "fine_tag": "行列式性质",
        "difficulty": 2,
        "choice": ("交换行列式的两行，行列式的值会（ ）。", {"A": "不变", "B": "变为相反数", "C": "变为平方", "D": "一定为 0"}, "B", "行列式交换两行会改变符号。"),
        "blank": ("若行列式有两行完全相同，则其值为____。", "0"),
        "calculation": ("计算 |1 2; 3 4|。", "-2"),
        "proof": ("证明含有两行相同的行列式等于 0。", "交换这两行行列式变号，但矩阵不变，所以 D=-D，故 D=0。"),
        "comprehensive": ("若三阶行列式某一行乘以 2，行列式如何变化？若再加到另一行呢？", "某行乘以 2 后行列式变为 2D；把一行倍加到另一行不改变行列式。"),
    },
    {
        "stage": "大一",
        "course": "线性代数上",
        "knowledge_tag": "向量空间",
        "fine_tag": "基与维数",
        "difficulty": 3,
        "choice": ("R^3 中三个线性无关向量构成（ ）。", {"A": "一组基", "B": "一个数", "C": "零空间", "D": "空集"}, "A", "R^3 的维数为 3，三个线性无关向量张成 R^3，因此构成一组基。"),
        "blank": ("向量空间的一组基必须线性无关并且能够____整个空间。", "张成"),
        "calculation": ("判断 (1,0,0),(0,1,0),(0,0,1) 张成空间的维数。", "3"),
        "proof": ("证明基表示的唯一性。", "若同一向量有两种基表示，相减得到基向量的线性组合为零，由线性无关性知各系数相等。"),
        "comprehensive": ("判断 (1,1),(1,-1) 是否为 R^2 的一组基，并说明理由。", "行列式为 -2 不为 0，二者线性无关且数量为 2，所以是 R^2 的一组基。"),
    },
    {
        "stage": "大二",
        "course": "线性代数下",
        "knowledge_tag": "特征值",
        "fine_tag": "矩阵对角化",
        "difficulty": 3,
        "choice": ("矩阵可对角化的一个充分条件是（ ）。", {"A": "有 n 个线性无关特征向量", "B": "所有元素都为 1", "C": "行列式为 0", "D": "迹为 0"}, "A", "n 阶矩阵若有 n 个线性无关特征向量，则可相似对角化。"),
        "blank": ("特征值 λ 满足的方程 det(A-λE)=0 称为____方程。", "特征"),
        "calculation": ("求对角矩阵 diag(2,3) 的特征值。", "2 和 3"),
        "proof": ("说明不同特征值对应的特征向量线性无关的基本思路。", "可用归纳法和线性组合等于零，左乘矩阵后与原式相减，逐步推出各系数为零。"),
        "comprehensive": ("若 A=PDP^{-1}，说明 A^k 的计算方式。", "A^k=PD^kP^{-1}，其中 D^k 只需把对角线元素分别取 k 次幂。"),
    },
    {
        "stage": "大二",
        "course": "概率论与数理统计",
        "knowledge_tag": "条件概率",
        "fine_tag": "贝叶斯公式",
        "difficulty": 2,
        "choice": ("若 P(A)>0，则 P(B|A)=（ ）。", {"A": "P(AB)/P(A)", "B": "P(A)/P(B)", "C": "P(A)+P(B)", "D": "P(A)-P(B)"}, "A", "条件概率定义为 P(B|A)=P(AB)/P(A)。"),
        "blank": ("全概率公式需要一组互不相容且并为样本空间的____。", "事件组"),
        "calculation": ("若 P(A)=0.5，P(B|A)=0.4，求 P(AB)。", "0.2"),
        "proof": ("由条件概率定义推出乘法公式 P(AB)=P(A)P(B|A)。", "当 P(A)>0 时，由 P(B|A)=P(AB)/P(A)，两边乘以 P(A) 即得。"),
        "comprehensive": ("说明贝叶斯公式适合解决哪类反推问题。", "适合已知原因先验概率和各原因下结果概率时，根据结果反推某一原因发生的后验概率。"),
    },
    {
        "stage": "大二",
        "course": "概率论与数理统计",
        "knowledge_tag": "参数估计",
        "fine_tag": "样本均值与无偏性",
        "difficulty": 3,
        "choice": ("若 X_1,...,X_n 独立同分布且 E(X_i)=μ，则样本均值的期望为（ ）。", {"A": "μ", "B": "nμ", "C": "μ/n", "D": "0"}, "A", "E(样本均值)=1/n∑E(X_i)=μ。"),
        "blank": ("估计量的期望等于被估参数时，称该估计量具有____性。", "无偏"),
        "calculation": ("样本 2,4,6 的样本均值是多少？", "4"),
        "proof": ("证明样本均值是总体均值 μ 的无偏估计。", "利用期望线性性，E(1/n∑X_i)=1/n∑E(X_i)=μ。"),
        "comprehensive": ("解释样本量增大时样本均值为什么通常更稳定。", "样本均值的方差为 σ^2/n，n 增大时方差减小，波动通常变小。"),
    },
    {
        "stage": "大二",
        "course": "级数与常微分方程",
        "knowledge_tag": "幂级数",
        "fine_tag": "收敛半径",
        "difficulty": 3,
        "choice": ("幂级数 ∑x^n 的收敛半径为（ ）。", {"A": "0", "B": "1", "C": "2", "D": "无穷大"}, "B", "几何级数 ∑x^n 在 |x|<1 时收敛，收敛半径为 1。"),
        "blank": ("幂级数的端点是否收敛，需要____判断。", "单独"),
        "calculation": ("求 ∑(x/2)^n 的收敛半径。", "2"),
        "proof": ("说明比值法求收敛半径的基本依据。", "对一般项取绝对值比值，极限小于 1 时收敛，由此得到 |x-a| 的范围。"),
        "comprehensive": ("讨论 ∑x^n/n 在 x=1 与 x=-1 两端的收敛性。", "x=1 为调和级数发散；x=-1 为交错调和级数收敛。"),
    },
    {
        "stage": "大二",
        "course": "级数与常微分方程",
        "knowledge_tag": "常微分方程",
        "fine_tag": "一阶线性方程",
        "difficulty": 3,
        "choice": ("一阶线性方程 y'+p(x)y=q(x) 的常用方法是（ ）。", {"A": "积分因子法", "B": "配方法", "C": "矩阵初等变换", "D": "分部积分两次"}, "A", "一阶线性微分方程通常乘以积分因子 e^{∫p(x)dx}。"),
        "blank": ("方程 y'+p(x)y=q(x) 的积分因子可取 μ(x)=____。", "e^{∫p(x)dx}"),
        "calculation": ("求 y'+y=0 的通解。", "y=Ce^{-x}"),
        "proof": ("说明积分因子法为什么能把左边化成乘积导数。", "取 μ'=pμ，则 (μy)'=μy'+μ'y=μ(y'+py)。"),
        "comprehensive": ("求 y'+y=e^x 的通解。", "积分因子 e^x，(e^x y)'=e^{2x}，故 e^x y=1/2 e^{2x}+C，y=1/2 e^x+Ce^{-x}。"),
    },
    {
        "stage": "大三",
        "course": "实变函数",
        "knowledge_tag": "测度初步",
        "fine_tag": "零测集",
        "difficulty": 4,
        "choice": ("单点集在实数轴上的勒贝格测度为（ ）。", {"A": "0", "B": "1", "C": "无穷大", "D": "不存在"}, "A", "单点可被任意短区间覆盖，因此外测度为 0。"),
        "blank": ("可数个零测集的并仍为____测集。", "零"),
        "calculation": ("有限点集 {1,2,3} 的测度是多少？", "0"),
        "proof": ("证明单点集 {a} 是零测集。", "任取 ε>0，用长度 ε 的开区间覆盖 {a}，外测度不超过 ε，由 ε 任意得测度为 0。"),
        "comprehensive": ("说明有理数集 Q 在任意有限区间内为何是零测集。", "Q 可数，可写成单点集可数并；单点集零测，可数并仍为零测。"),
    },
    {
        "stage": "大三",
        "course": "抽象代数",
        "knowledge_tag": "群论基础",
        "fine_tag": "子群判别",
        "difficulty": 4,
        "choice": ("非空子集 H 成为群 G 的子群，一个常用判别是（ ）。", {"A": "对 ab^{-1} 封闭", "B": "元素个数为偶数", "C": "包含所有实数", "D": "没有单位元"}, "A", "子群判别法：H 非空且对任意 a,b∈H，有 ab^{-1}∈H。"),
        "blank": ("群中满足 ae=ea=a 的元素 e 称为____元。", "单位"),
        "calculation": ("整数加法群中，2Z 是否为子群？", "是"),
        "proof": ("证明整数加法群的偶数集合 2Z 是子群。", "0∈2Z；若 2m,2n∈2Z，则 2m-2n=2(m-n)∈2Z，故为子群。"),
        "comprehensive": ("说明群的单位元为什么唯一。", "若 e 与 e' 都是单位元，则 e=ee'=e'，所以唯一。"),
    },
    {
        "stage": "大三",
        "course": "数值分析",
        "knowledge_tag": "非线性方程数值解",
        "fine_tag": "牛顿迭代",
        "difficulty": 3,
        "choice": ("牛顿法迭代公式为（ ）。", {"A": "x_{n+1}=x_n-f(x_n)/f'(x_n)", "B": "x_{n+1}=x_n+1", "C": "x_{n+1}=f'(x_n)", "D": "x_{n+1}=0"}, "A", "牛顿法用切线近似函数零点，公式为 x_{n+1}=x_n-f(x_n)/f'(x_n)。"),
        "blank": ("牛顿法要求迭代点附近 f'(x) 通常不能为____。", "0"),
        "calculation": ("用牛顿法求 x^2-2=0 时的迭代公式。", "x_{n+1}=1/2(x_n+2/x_n)"),
        "proof": ("从切线方程推导牛顿迭代公式。", "在 x_n 处切线为 y=f(x_n)+f'(x_n)(x-x_n)，令 y=0 解得 x=x_n-f(x_n)/f'(x_n)。"),
        "comprehensive": ("说明牛顿法初值选择不当可能带来的问题。", "可能发散、落到导数接近 0 的区域，或收敛到非目标根。"),
    },
    {
        "stage": "大四",
        "course": "拓扑学基础",
        "knowledge_tag": "点集拓扑",
        "fine_tag": "开集与闭集",
        "difficulty": 4,
        "choice": ("在通常拓扑下，开区间 (0,1) 是（ ）。", {"A": "开集", "B": "闭集", "C": "既非开也非闭", "D": "只有一个点"}, "A", "对区间内任一点，都存在足够小的邻域仍包含在 (0,1) 中。"),
        "blank": ("集合 A 的补集为开集时，A 称为____集。", "闭"),
        "calculation": ("在 R 中，集合 [0,1] 的边界是什么？", "{0,1}"),
        "proof": ("证明任意拓扑空间中全集和空集都是开集。", "这是拓扑定义的公理之一，拓扑族必须包含全集和空集。"),
        "comprehensive": ("说明闭区间 [0,1] 在 R 中为什么是闭集。", "其补集 (-∞,0)∪(1,∞) 是开集，所以 [0,1] 是闭集。"),
    },
    {
        "stage": "大四",
        "course": "微分几何基础",
        "knowledge_tag": "曲线论",
        "fine_tag": "曲率直观",
        "difficulty": 4,
        "choice": ("平面直线的曲率为（ ）。", {"A": "0", "B": "1", "C": "无穷大", "D": "不确定"}, "A", "直线方向不发生弯曲，单位切向量不变，因此曲率为 0。"),
        "blank": ("单位圆的曲率为____。", "1"),
        "calculation": ("半径为 R 的圆的曲率是多少？", "1/R"),
        "proof": ("说明曲率可以理解为单位切向量随弧长变化的快慢。", "曲率定义为 |dT/ds|，其中 T 为单位切向量，s 为弧长参数。"),
        "comprehensive": ("比较半径 1 与半径 3 的圆，哪个弯曲更明显？", "半径 1 的圆曲率为 1，半径 3 的圆曲率为 1/3，因此半径 1 的圆更弯。"),
    },
    {
        "stage": "大四",
        "course": "数学建模与综合专题",
        "knowledge_tag": "模型评价",
        "fine_tag": "灵敏度分析",
        "difficulty": 3,
        "choice": ("灵敏度分析主要研究（ ）。", {"A": "参数变化对模型结果的影响", "B": "字体大小", "C": "文件格式", "D": "随机起名"}, "A", "灵敏度分析关注参数扰动后模型输出是否稳定。"),
        "blank": ("评价数学模型常看准确性、稳定性、可解释性和____。", "可操作性"),
        "calculation": ("模型 y=2x 中 x 增加 10%，y 将增加多少？", "10%"),
        "proof": ("说明线性模型 y=ax 对比例变化具有同比例响应。", "若 x 变为 (1+r)x，则 y 变为 a(1+r)x=(1+r)y。"),
        "comprehensive": ("设计一个简单的学习时长与成绩提升模型，并指出可能的局限。", "可设提升量 y=a ln(1+x)，表示边际收益递减；局限是忽略基础差异、题目质量和复盘效率。"),
    },
]


def key_steps(question_type: str) -> list[str]:
    if question_type == "choice":
        return ["先定位考查概念", "写出定义或核心公式", "排除不满足条件的选项"]
    if question_type == "blank":
        return ["明确空格所需对象", "检查定义条件", "用最简形式作答"]
    if question_type == "calculation":
        return ["列出已知条件", "选择合适公式", "逐步计算并检查符号"]
    if question_type == "proof":
        return ["写清要证明的结论", "展开定义或调用定理", "补齐逻辑闭环"]
    return ["拆分子问题", "建立数学表达", "解释结果的含义与限制"]


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
                "usage_note": "项目自制中文演示题，用于本科数学学习系统的普通练习、模拟测试和解析展示。",
            },
        ).lastrowid
        if not source_id:
            source_id = db.execute(
                text("SELECT id FROM source_attributions WHERE source_name = :source_name"),
                {"source_name": SOURCE_NAME},
            ).scalar_one()

        for topic_index, topic in enumerate(TOPICS, start=1):
            for question_type in TYPE_ORDER:
                payload = topic[question_type]
                if question_type == "choice":
                    question_text, options, correct_answer, standard_answer = payload
                    option_a = options["A"]
                    option_b = options["B"]
                    option_c = options["C"]
                    option_d = options["D"]
                    analysis = standard_answer
                else:
                    question_text, standard_answer = payload
                    option_a = option_b = option_c = option_d = correct_answer = None
                    analysis = f"本题考查“{topic['fine_tag']}”。参考答案：{standard_answer}"

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
                           option_a = VALUES(option_a),
                           option_b = VALUES(option_b),
                           option_c = VALUES(option_c),
                           option_d = VALUES(option_d),
                           correct_answer = VALUES(correct_answer),
                           standard_answer = VALUES(standard_answer),
                           analysis_text = VALUES(analysis_text),
                           key_steps = VALUES(key_steps),
                           common_errors = VALUES(common_errors),
                           mistake_tags = VALUES(mistake_tags)
                        """
                    ),
                    {
                        "source_id": source_id,
                        "source_question_no": f"CURATED-EXTRA-{topic_index:02d}-{question_type}",
                        "source_path": f"curated-extra/{topic['course']}/{topic['knowledge_tag']}/{question_type}",
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
                        "common_errors": json.dumps(["概念条件漏看", "公式套用不完整", "计算或符号错误"], ensure_ascii=False),
                        "mistake_tags": json.dumps(["本科数学基础", topic["knowledge_tag"]], ensure_ascii=False),
                    },
                )
        db.commit()
    print(f"seeded_or_updated={len(TOPICS) * len(TYPE_ORDER)}")


if __name__ == "__main__":
    main()
