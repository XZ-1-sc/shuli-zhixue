"""生成《数理智学用户操作手册》初版。

模仿 树Demo操作手册.docx 的结构与排版：
  * 封面：软件名（黑体 22 磅加粗居中）+ 副标题（Subtitle 样式）+ 版本号
  * 章节：中文数字编号（一、二、三……）
  * 图片位置留空，下方配"图N：说明"图注（居中）
  * 操作步骤用"第N步："，功能罗列用"- "，注意事项用"1. 2. 3."
  * 页面：A4，页边距 上下 1247 / 左右 1134（与 Demo 一致）

复用 Demo 的 styles.xml / theme / settings，保证字体与样式体系相同。
输出：数理智学用户操作手册.docx
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

TEMPLATE = REPO / "树Demo操作手册.docx"
TARGET = REPO / "数理智学用户操作手册.docx"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"

ET.register_namespace("w", W)
ET.register_namespace("w14", W14)
for _p, _u in (
    ("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships"),
    ("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"),
    ("a", "http://schemas.openxmlformats.org/drawingml/2006/main"),
    ("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture"),
    ("v", "urn:schemas-microsoft-com:vml"),
    ("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006"),
):
    try:
        ET.register_namespace(_p, _u)
    except ValueError:
        pass

from manual_content import SECTIONS  # noqa: E402


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def para(text: str, *, jc: str | None = None, size: int = 24, bold: bool = False,
         font: str = "宋体", line: int = 380, style: str | None = None) -> str:
    """构造一个段落。size 为半磅值，24 = 12 磅。"""
    props = []
    if style:
        props.append(f'<w:pStyle w:val="{style}"/>')
    props.append(f'<w:spacing w:line="{line}" w:lineRule="atLeast"/>')
    if jc:
        props.append(f'<w:jc w:val="{jc}"/>')
    bold_xml = "<w:b/><w:bCs/>" if bold else ""
    props.append(
        f'<w:rPr><w:rFonts w:hint="eastAsia" w:ascii="{font}" w:hAnsi="{font}" '
        f'w:eastAsia="{font}"/>{bold_xml}<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
    )
    ppr = f'<w:pPr>{"".join(props)}</w:pPr>'
    rpr = (
        f'<w:rPr><w:rFonts w:hint="eastAsia" w:ascii="{font}" w:hAnsi="{font}" '
        f'w:eastAsia="{font}"/>{bold_xml}<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
    )
    return (
        f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>'
    )


def blank() -> str:
    return para("")


def title(text: str) -> str:
    return para(text, jc="center", size=44, bold=True, font="黑体")


def subtitle(text: str) -> str:
    return para(text, jc="center", size=36, font="黑体", style="13")


def heading(text: str) -> str:
    return para(text, size=28, bold=True, font="黑体")


def figure_caption(text: str) -> str:
    return para(text, jc="center", size=21)


CN = "一二三四五六七八九十"


def cn_num(n: int) -> str:
    if n <= 10:
        return CN[n - 1]
    if n < 20:
        return "十" + CN[n - 11]
    if n == 20:
        return "二十"
    if n < 30:
        return "二十" + CN[n - 21]
    return str(n)


def build_document() -> str:
    parts: list[str] = [blank()]
    parts.append(title("数理智学"))
    parts.append(subtitle("用户操作手册"))
    parts.append(para("版本 V1.0", jc="center", size=24))
    parts.append(blank())

    fig_count = 0
    for index, (name, blocks) in enumerate(SECTIONS, start=1):
        parts.append(heading(f"{cn_num(index)}、{name}"))
        parts.append(blank())
        for kind, content in blocks:
            if kind == "f":
                fig_count += 1
                # 留出截图位置：空段落 + 图注
                parts.append(blank())
                parts.append(figure_caption(content))
            else:
                parts.append(para(content))
        parts.append(blank())

    body = "".join(parts)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:document xmlns:w="{W}" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        f'xmlns:w14="{W14}"><w:body>'
        + body
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1247" w:right="1134" w:bottom="1247" w:left="1134" '
        'w:header="851" w:footer="992" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )


def main() -> int:
    if not TEMPLATE.exists():
        print(f"模板不存在: {TEMPLATE}")
        return 1

    document = build_document()
    ET.fromstring(document)

    with zipfile.ZipFile(TEMPLATE) as z:
        keep = {
            "[Content_Types].xml",
            "_rels/.rels",
            "word/styles.xml",
            "word/settings.xml",
            "word/fontTable.xml",
            "word/theme/theme1.xml",
            "word/_rels/document.xml.rels",
            "word/header1.xml",
            "docProps/core.xml",
            "docProps/app.xml",
        }
        parts = {n: z.read(n) for n in z.namelist() if n in keep and not n.endswith("/")}

    parts["word/document.xml"] = document.encode("utf-8")

    with zipfile.ZipFile(TARGET, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)

    figures = sum(1 for _, blocks in SECTIONS for k, _ in blocks if k == "f")
    print(f"已生成 {TARGET}")
    print(f"  章节数  : {len(SECTIONS)}")
    print(f"  段落数  : {document.count('<w:p>')}")
    print(f"  图注位数: {figures}")
    print(f"  大小    : {TARGET.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
