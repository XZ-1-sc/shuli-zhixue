import csv
import re
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "tmp" / "pdfs"
OUTPUT = ROOT / "data" / "questions.csv"


SOURCES = [
    {
        "name": "2024国考副省级",
        "question_pdf": PDF_DIR / "2024_province.pdf",
        "answer_pdf": None,
        "total": 135,
        "url": "https://github.com/Yaoyuan-Zhang319/AdministrativeAptitudeTest/blob/main/国考/答案/2024年国考行测真题（副省级）-11.27.pdf",
    },
    {
        "name": "2022国考市地级",
        "question_pdf": PDF_DIR / "2022_city_questions.pdf",
        "answer_pdf": PDF_DIR / "2022_city_answers.pdf",
        "total": 130,
        "url": "https://github.com/Yaoyuan-Zhang319/AdministrativeAptitudeTest/blob/main/国考/试卷/2022%20年国家公务员考试行测真题（地市级）.pdf",
    },
    {
        "name": "2021国考市地级",
        "question_pdf": PDF_DIR / "2021_city_questions.pdf",
        "answer_pdf": PDF_DIR / "2021_city_answers.pdf",
        "total": 130,
        "url": "https://github.com/Yaoyuan-Zhang319/AdministrativeAptitudeTest/blob/main/国考/试卷/2021年国家公务员考试《行测》真题（市地级）.pdf",
    },
    {
        "name": "2021国考副省级",
        "question_pdf": PDF_DIR / "2021_province_questions.pdf",
        "answer_pdf": PDF_DIR / "2021_province_answers.pdf",
        "total": 135,
        "url": "https://github.com/Yaoyuan-Zhang319/AdministrativeAptitudeTest/blob/main/国考/试卷/2021年国家公务员考试《行测》真题（副省级）.pdf",
    },
]


FIELDNAMES = [
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


QUESTION_START_RE = re.compile(
    r"(?m)^\s*(\d{1,3})[\.．、]\s*(?![ABCD](?:\s|$|[\.．、]))"
)
OPTION_RE = re.compile(r"(?<![A-Za-z0-9])([ABCD])[\.．、]\s*")


def extract_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def clean_watermark(text: str) -> str:
    replacements = [
        "公事书舍 微信公众号：公事书舍",
        "更多免费公考资料领取请关注公众号：公事书舍",
        "微信公众号：公事书舍",
        "公众号：公事书舍",
        "第 页共 页",
    ]
    for item in replacements:
        text = text.replace(item, "")
    text = re.sub(r"(?m)^\s*[公事书舍]\s*$", "", text)
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)
    text = re.sub(r"~\s*\d+\s*~", "", text)
    text = re.sub(r"第\s*\d+\s*页\s*共\s*\d+\s*页", "", text)
    text = re.sub(r"([公事书舍])(?=[ABCD][\.．、])", "", text)
    return text


def compact(text: str) -> str:
    text = clean_watermark(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_question_blocks(text: str):
    first_part = text.find("第一部分")
    if first_part >= 0:
        text = text[first_part:]
    matches = [
        m
        for m in QUESTION_START_RE.finditer(text)
        if 1 <= int(m.group(1)) <= 150
    ]
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        yield int(match.group(1)), text[start:end]


def build_material_map(text: str, total: int) -> dict[int, str]:
    data_start = 116 if total == 135 else 111
    data_end = 135 if total == 135 else 130
    fifth_part = text.find("第五部分")
    if fifth_part < 0:
        return {}
    data_text = text[fifth_part:]
    matches = [
        m
        for m in QUESTION_START_RE.finditer(data_text)
        if data_start <= int(m.group(1)) <= data_end
    ]
    material_map: dict[int, str] = {}
    current_material = ""
    previous_start = 0
    marker_re = re.compile(r"(?:根据以下资料[^。．\n]*[。．]?|\(材料\d+\))")

    for idx, match in enumerate(matches):
        number = int(match.group(1))
        between = data_text[previous_start : match.start()]
        marker_matches = list(marker_re.finditer(between))
        if marker_matches:
            material_candidate = between[marker_matches[-1].start() :]
            current_material = compact(material_candidate)
        elif idx == 0:
            material_candidate = re.sub(r"第五部分\s*资料分析", "", between)
            material_candidate = re.sub(r"所给出的.*?请开始答题[:：]?", "", material_candidate, flags=re.S)
            current_material = compact(material_candidate)
        elif number in {data_start, data_start + 5, data_start + 10, data_start + 15}:
            current_material = ""

        if len(current_material) >= 30:
            material_map[number] = current_material
        previous_start = match.start()
    return material_map


def parse_answer_map(answer_pdf: Path) -> dict[int, str]:
    if answer_pdf is None:
        return {}
    text = extract_text(answer_pdf)
    answers: dict[int, str] = {
        int(number): answer
        for number, answer in re.findall(
            r"(?m)^\s*(\d{1,3})[\.．、]\s*正确答案[:：]\s*([ABCD])", text
        )
    }
    blocks = re.split(r"(?m)^(?=\d{1,3}[\.．、]\s*解析)", text)
    for block in blocks:
        number_match = re.match(r"\s*(\d{1,3})[\.．、]\s*解析", block)
        if not number_match:
            continue
        number = int(number_match.group(1))
        answer_match = re.search(r"选择\s*([ABCD])\s*选项", block)
        if not answer_match:
            answer_match = re.search(r"正确答案[为是：:]?\s*([ABCD])", block)
        if answer_match:
            answers[number] = answer_match.group(1)
    return answers


def answer_from_block(number: int, block: str) -> str | None:
    patterns = [
        rf"【参考答案】\s*([ABCD])",
        rf"【答案】\s*([ABCD])",
        rf"参考答案[:：]?\s*([ABCD])",
        rf"正确答案[为是：:]?\s*([ABCD])",
        rf"故正确答案为\s*([ABCD])",
        rf"(?m)^\s*{number}[\.．、]\s*([ABCD])\s*$",
        rf"(?m)^\s*([ABCD])\s*$",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, block)
        if matches:
            return matches[-1]
    return None


def truncate_explanation(block: str, number: int) -> str:
    markers = [
        "【解析】",
        "解析",
        "拓展",
        "故正确答案为",
        "【参考答案】",
        "【答案】",
        "参考答案",
        "正确答案",
    ]
    cut_positions = [block.find(marker) for marker in markers if block.find(marker) >= 0]
    answer_line = re.search(rf"(?m)^\s*{number}[\.．、]\s*[ABCD]\s*$", block)
    if answer_line:
        cut_positions.append(answer_line.start())
    standalone_answer = re.search(r"(?m)^\s*[ABCD]\s*$", block)
    if standalone_answer:
        cut_positions.append(standalone_answer.start())
    if cut_positions:
        return block[: min(cut_positions)]
    return block


def parse_question_block(number: int, block: str, answer_map: dict[int, str]) -> dict | None:
    answer = answer_map.get(number) or answer_from_block(number, block)
    if not answer:
        return None

    content = truncate_explanation(block, number)
    content = re.sub(rf"^\s*{number}[\.．、]\s*", "", content.strip())
    option_matches = list(OPTION_RE.finditer(content))
    if len(option_matches) < 4:
        return None

    # Use the first complete A/B/C/D sequence to avoid option-like letters in explanations.
    labels = [m.group(1) for m in option_matches]
    sequence_start = None
    for idx in range(0, len(labels) - 3):
        if labels[idx : idx + 4] == ["A", "B", "C", "D"]:
            sequence_start = idx
            break
    if sequence_start is None:
        return None
    option_matches = option_matches[sequence_start : sequence_start + 4]

    stem = compact(content[: option_matches[0].start()])
    options: dict[str, str] = {}
    for idx, match in enumerate(option_matches):
        label = match.group(1)
        start = match.end()
        end = option_matches[idx + 1].start() if idx + 1 < len(option_matches) else len(content)
        options[label] = compact(content[start:end])

    if not stem or any(not options.get(label) for label in "ABCD"):
        return None
    if len(stem) < 8:
        return None
    if any(len(options[label]) > 500 for label in "ABCD"):
        return None

    return {
        "number": number,
        "stem": stem,
        "options": options,
        "answer": answer,
    }


def module_for(total: int, number: int) -> str:
    if total == 135:
        if 1 <= number <= 20:
            return "常识判断"
        if 21 <= number <= 60:
            return "言语理解与表达"
        if 61 <= number <= 75:
            return "数量关系"
        if 76 <= number <= 115:
            return "判断推理"
        if 116 <= number <= 135:
            return "资料分析"
    else:
        if 1 <= number <= 20:
            return "常识判断"
        if 21 <= number <= 60:
            return "言语理解与表达"
        if 61 <= number <= 70:
            return "数量关系"
        if 71 <= number <= 110:
            return "判断推理"
        if 111 <= number <= 130:
            return "资料分析"
    return "未分类"


def knowledge_tag(module: str, stem: str, options: dict[str, str]) -> str:
    text = stem + " " + " ".join(options.values())
    if module == "常识判断":
        if re.search(r"宪法|刑法|民法|行政|诉讼|处罚|法律|法规|专利|管辖|监察", text):
            return "法律常识"
        if re.search(r"习近平|二十大|党中央|党|政府|政策|乡村振兴|现代化|共同富裕|十四五", text):
            return "时政热点"
        if re.search(r"财政|税|经济|贸易|金融|投资|市场|供给|需求", text):
            return "经济常识"
        if re.search(r"物理|化学|生物|生态|气候|航天|卫星|矿产|能源|植物|医学|科技", text):
            return "科技与自然"
        if re.search(r"历史|唐|宋|秦|汉|诗词|文化|文明|成语|古代", text):
            return "历史人文"
        return "常识综合"
    if module == "言语理解与表达":
        if re.search(r"填入|画横线|横线|空缺|依次", text):
            return "逻辑填空"
        if re.search(r"排序|重新排列|语句排序", text):
            return "语句排序"
        if re.search(r"接下来|下文", text):
            return "下文推断"
        if re.search(r"标题|题目", text):
            return "标题提炼"
        if re.search(r"意在|主旨|概括|主要说明|旨在|中心", text):
            return "片段阅读"
        return "阅读理解"
    if module == "数量关系":
        if re.search(r"利润|盈利|亏损|折扣|价格|成本|营业额|税", text):
            return "经济利润问题"
        if re.search(r"工程|效率|完成|施工|合作", text):
            return "工程问题"
        if re.search(r"行驶|速度|距离|路程|相遇|追及", text):
            return "行程问题"
        if re.search(r"三角|矩形|正方形|圆|面积|周长|体积|几何", text):
            return "几何问题"
        if re.search(r"排列|组合|概率|至少|抽取|分配", text):
            return "排列组合与概率"
        return "数量计算"
    if module == "判断推理":
        if re.search(r"定义|指的是|所谓", text):
            return "定义判断"
        if re.search(r"图形|左边|右边|立体|截面|黑块|白块", text):
            return "图形推理"
        if re.search(r"支持|削弱|质疑|推出|解释|前提|假设|必然|可能", text):
            return "逻辑判断"
        if re.search(r"和|对于|相当于|成语", " ".join(options.values())):
            return "类比推理"
        return "逻辑判断"
    if module == "资料分析":
        if re.search(r"增长率|同比|环比|增速", text):
            return "增长率"
        if re.search(r"比重|占|比例", text):
            return "比重计算"
        if re.search(r"平均|人均|每", text):
            return "平均数"
        if re.search(r"倍|超过|约为", text):
            return "倍数与比较"
        return "综合分析"
    return "综合"


def is_image_dependent(module: str, stem: str) -> bool:
    if module != "判断推理":
        return False
    return bool(re.search(r"图形|左图|右图|立体|截面|黑块|白块|拼接|展开图|折叠|六个图", stem))


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_stems: set[str] = set()
    per_source_counts: dict[str, int] = {}
    skipped_counts: dict[str, int] = {}

    for source in SOURCES:
        answer_map = parse_answer_map(source["answer_pdf"]) if source["answer_pdf"] else {}
        text = clean_watermark(extract_text(source["question_pdf"]))
        material_map = build_material_map(text, source["total"])
        source_count = 0
        skipped = 0
        for number, block in split_question_blocks(text):
            parsed = parse_question_block(number, block, answer_map)
            if not parsed:
                skipped += 1
                continue
            module = module_for(source["total"], number)
            if module == "未分类":
                skipped += 1
                continue
            if is_image_dependent(module, parsed["stem"]):
                skipped += 1
                continue
            if module == "资料分析":
                material = material_map.get(number)
                if not material:
                    skipped += 1
                    continue
                parsed["stem"] = f"资料：{material} 问题：{parsed['stem']}"
            stem_key = re.sub(r"\W+", "", parsed["stem"])
            if stem_key in seen_stems:
                skipped += 1
                continue
            seen_stems.add(stem_key)

            tag = knowledge_tag(module, parsed["stem"], parsed["options"])
            rows.append(
                {
                    "题干": parsed["stem"],
                    "选项A": parsed["options"]["A"],
                    "选项B": parsed["options"]["B"],
                    "选项C": parsed["options"]["C"],
                    "选项D": parsed["options"]["D"],
                    "正确答案": parsed["answer"],
                    "所属模块": module,
                    "知识点标签": tag,
                    "来源": source["name"],
                    "题号": str(number),
                    "来源链接": source["url"],
                }
            )
            source_count += 1
        per_source_counts[source["name"]] = source_count
        skipped_counts[source["name"]] = skipped

    print("per_source_counts:", per_source_counts)
    print("skipped_counts:", skipped_counts)
    return rows


def validate(rows: list[dict[str, str]]) -> None:
    if not 300 <= len(rows) <= 500:
        raise SystemExit(f"row count {len(rows)} is outside required 300-500 range")
    required = ["题干", "选项A", "选项B", "选项C", "选项D", "正确答案", "所属模块", "知识点标签"]
    for index, row in enumerate(rows, start=1):
        for field in required:
            if not row.get(field):
                raise SystemExit(f"row {index} missing {field}")
        if row["正确答案"] not in {"A", "B", "C", "D"}:
            raise SystemExit(f"row {index} invalid answer {row['正确答案']}")
    modules = {row["所属模块"] for row in rows}
    expected = {"常识判断", "言语理解与表达", "数量关系", "判断推理", "资料分析"}
    if modules != expected:
        raise SystemExit(f"module coverage mismatch: {modules}")


def write_csv(rows: list[dict[str, str]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = build_rows()
    validate(rows)
    write_csv(rows)
    module_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    for row in rows:
        module_counts[row["所属模块"]] = module_counts.get(row["所属模块"], 0) + 1
        tag_counts[row["知识点标签"]] = tag_counts.get(row["知识点标签"], 0) + 1
    print(f"wrote {len(rows)} rows to {OUTPUT}")
    print("module_counts:", module_counts)
    print("top_tags:", sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:15])


if __name__ == "__main__":
    main()
