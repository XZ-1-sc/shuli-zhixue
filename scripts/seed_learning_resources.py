from sqlalchemy import text

from backend.app.database.session import SessionLocal


RESOURCES = [
    ("大一", "高等数学上", "极限与连续速记讲义", "lecture", "梳理极限运算、等价无穷小、函数连续与间断点判断。", "/practice?course=高等数学上&knowledge_tag=极限与连续", 2),
    ("大一", "高等数学上", "导数应用专项练习", "practice", "覆盖切线、单调性、极值、微分中值定理的基础题组。", "/practice?course=高等数学上&knowledge_tag=导数", 2),
    ("大一", "线性代数上", "矩阵运算与逆矩阵", "lecture", "从矩阵乘法维度、行列式到逆矩阵条件的短讲义。", "/practice?course=线性代数上", 2),
    ("大二", "高等数学下", "多元函数微分路线", "roadmap", "偏导数、梯度、方向导数与条件极值的学习顺序。", "/roadmap", 3),
    ("大二", "概率论与数理统计", "随机变量与期望练习", "practice", "用离散分布和常见连续分布训练期望、方差与独立性。", "/practice?course=概率论与数理统计", 2),
    ("大二", "级数与常微分方程", "级数判别法清单", "lecture", "比较、比值、根值、交错级数和幂级数收敛半径。", "/practice?course=级数与常微分方程", 3),
    ("大三", "复变函数", "解析函数入门", "lecture", "复数运算、柯西-黎曼方程、解析函数与积分初步。", "/practice?course=复变函数", 3),
    ("大三", "数值分析", "误差与迭代方法", "practice", "训练舍入误差、二分法、牛顿法和线性方程组数值解法。", "/practice?course=数值分析", 3),
    ("大四", "数学建模与综合专题", "建模问题拆解模板", "project", "从变量、目标函数、约束条件到模型检验的完整框架。", "/practice?course=数学建模与综合专题", 3),
]


def main() -> None:
    inserted = 0
    with SessionLocal() as db:
        for stage, course, title, resource_type, description, url, difficulty in RESOURCES:
            result = db.execute(
                text(
                    """
                    INSERT INTO learning_resources (stage, course, title, resource_type, description, url, difficulty)
                    SELECT :stage, :course, :title, :resource_type, :description, :url, :difficulty
                    WHERE NOT EXISTS (SELECT 1 FROM learning_resources WHERE title = :title LIMIT 1)
                    """
                ),
                {
                    "stage": stage,
                    "course": course,
                    "title": title,
                    "resource_type": resource_type,
                    "description": description,
                    "url": url,
                    "difficulty": difficulty,
                },
            )
            inserted += result.rowcount
        db.commit()
    print(f"学习资源种子完成，新增 {inserted} 条。")


if __name__ == "__main__":
    main()
