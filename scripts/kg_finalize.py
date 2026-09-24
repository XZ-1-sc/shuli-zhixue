"""图谱收尾：清理非白名单课程残留节点 + 重建 course_relations 真实先修链。"""
import sys

sys.path.insert(0, "backend")

from sqlalchemy import text

from app.database.repositories.curriculum import GRAPH_COURSES
from app.database.session import SessionLocal

RELATIONS: list[tuple[str, str, str, str]] = [
    ("高等数学上", "高等数学下", "prerequisite", "先学极限/一元微积分再进入多元"),
    ("高等数学下", "级数与常微分方程", "prerequisite", "数项级数需建立在极限与一元微积分之上"),
    ("级数与常微分方程", "复变函数", "prerequisite", "复级数与解析函数需要实数级数基础"),
    ("高等数学下", "偏微分方程基础", "prerequisite", "PDE 需要多元微积分基础"),
    ("级数与常微分方程", "偏微分方程基础", "prerequisite", "分离变量与特征方法依赖常微分方程"),
    ("高等数学下", "实变函数", "prerequisite", "勒贝格积分需要系统的一元分析基础"),
    ("线性代数基础", "线性代数进阶", "prerequisite", "进阶特征理论基于基础矩阵/方程组"),
    ("线性代数基础", "概率论与数理统计", "prerequisite", "多元分布与协方差常用矩阵工具"),
    ("线性代数进阶", "抽象代数", "prerequisite", "群/环抽象建立在变换与结构理解上"),
    ("高等数学下", "数值分析", "prerequisite", "数值逼近需要微积分与分析基础"),
    ("线性代数基础", "数值分析", "prerequisite", "解线性方程组依赖高斯消元与矩阵"),
    ("高等数学下", "微分几何基础", "prerequisite", "曲线曲率需多元微积分工具"),
    ("线性代数基础", "微分几何基础", "prerequisite", "第一基本形式与内积空间相关"),
]

with SessionLocal.begin() as db:
    # 1) 清理残留旧节点（非图谱课程的旧 knowledge_nodes，备份表已留存）
    deleted = db.execute(
        text(f"DELETE FROM knowledge_nodes WHERE course_name NOT IN ({','.join([':c' + str(i) for i in range(len(GRAPH_COURSES))])})"),
        {f"c{i}": name for i, name in enumerate(GRAPH_COURSES)},
    ).rowcount
    # 2) 重建先修链
    db.execute(text("DELETE FROM course_relations"))
    for source, target, relation, note in RELATIONS:
        db.execute(
            text("INSERT INTO course_relations(from_course,to_course,relation,note) VALUES(:s,:t,:r,:n)"),
            {"s": source, "t": target, "r": relation, "n": note},
        )

print(f"cleaned non-graph nodes: {deleted}")
print(f"relations rebuilt: {len(RELATIONS)}")

# 3) 统计校验
with SessionLocal() as db:
    per_course = db.execute(text("SELECT course_name, COUNT(*) c FROM knowledge_nodes GROUP BY course_name ORDER BY c DESC")).all()
    for row in per_course:
        print("  ", row[0], row[1])
    bad = db.execute(text("SELECT COUNT(*) c FROM knowledge_nodes WHERE course_name NOT IN ('高等数学上','高等数学下','线性代数基础','线性代数进阶','级数与常微分方程','概率论与数理统计','复变函数','实变函数','抽象代数','数值分析','偏微分方程基础','微分几何基础')")).scalar_one()
    print("non-graph residue:", bad)
