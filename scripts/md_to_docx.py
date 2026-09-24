"""把本仓库的 Markdown 说明书转换为 .docx（Word）文档。

只依赖 Python 标准库（zipfile / xml / re），不引入第三方包。

设计要点
--------
* 生成合法的 Office Open XML 包：Content_Types / rels / document.xml / styles.xml / numbering.xml
* 支持标题、段落、无序与有序列表、表格、围栏代码块、引用块、水平线、行内粗体与等宽代码
* 中文字体走 eastAsia 通道，避免 Word 里中文回退成宋体
* 页脚自动插入页码域
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path


# ---------------------------------------------------------------- XML 工具


def esc(text: str) -> str:
    """XML 文本转义。"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _xml_attrs(attrs: dict[str, object]) -> str:
    return " ".join(f'{key}="{value}"' for key, value in attrs.items() if value is not None)


# 行内标记：**粗体**、`等宽`、*斜体*、[文本](链接)
INLINE_RE = re.compile(
    r"(\*\*.+?\*\*)"          # 粗体
    r"|(`[^`]+?`)"            # 行内代码
    r"|(\*[^*\n]+?\*)"        # 斜体
    r"|(\[[^\]]+?\]\([^)]+?\))"  # 链接
)

CODE_FONT = "Consolas"
CJK_FONT = "Microsoft YaHei"
LATIN_FONT = "Calibri"


def _run(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    mono: bool = False,
    color: str | None = None,
    size_half_pt: int | None = None,
) -> str:
    """构造一个 w:r 运行块。"""
    props: list[str] = [
        f'<w:rFonts w:ascii="{CODE_FONT if mono else LATIN_FONT}" '
        f'w:hAnsi="{CODE_FONT if mono else LATIN_FONT}" w:eastAsia="{CJK_FONT}"/>'
    ]
    if bold:
        props.append("<w:b/>")
    if italic:
        props.append("<w:i/>")
    if color:
        props.append(f'<w:color w:val="{color}"/>')
    if size_half_pt:
        props.append(f'<w:sz w:val="{size_half_pt}"/><w:szCs w:val="{size_half_pt}"/>')
    if mono:
        props.append('<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>')

    rpr = f"<w:rPr>{''.join(props)}</w:rPr>"
    # 保留空格
    return f'<w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r>'


def inline_runs(text: str, *, base_bold: bool = False, size_half_pt: int | None = None) -> str:
    """把一段 Markdown 行内文本转成若干运行块。"""
    out: list[str] = []
    pos = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > pos:
            out.append(_run(text[pos : match.start()], bold=base_bold, size_half_pt=size_half_pt))
        token = match.group(0)
        if token.startswith("**"):
            out.append(_run(token[2:-2], bold=True, size_half_pt=size_half_pt))
        elif token.startswith("`"):
            out.append(_run(token[1:-1], mono=True, size_half_pt=size_half_pt))
        elif token.startswith("["):
            label = re.match(r"\[([^\]]+?)\]", token)
            url = re.search(r"\(([^)]+?)\)$", token)
            out.append(_run(label.group(1) if label else token, color="1F6FEB", size_half_pt=size_half_pt))
            if url and not url.group(1).startswith("#"):
                out.append(_run(f" ({url.group(1)})", color="6E6E6E", size_half_pt=size_half_pt))
        else:
            out.append(_run(token[1:-1], italic=True, size_half_pt=size_half_pt))
        pos = match.end()
    if pos < len(text):
        out.append(_run(text[pos:], bold=base_bold, size_half_pt=size_half_pt))
    return "".join(out) or _run("")


# ---------------------------------------------------------------- 块级元素


def para(text: str, *, style: str | None = None, bold: bool = False, size_half_pt: int | None = None,
         spacing_after: int | None = None, indent_left: int | None = None, keep_next: bool = False) -> str:
    ppr: list[str] = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if keep_next:
        ppr.append("<w:keepNext/>")
    if spacing_after is not None:
        ppr.append(f'<w:spacing w:after="{spacing_after}"/>')
    if indent_left is not None:
        ppr.append(f'<w:ind w:left="{indent_left}"/>')
    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>" if ppr else ""
    return f"<w:p>{ppr_xml}{inline_runs(text, base_bold=bold, size_half_pt=size_half_pt)}</w:p>"


def list_para(text: str, *, num_id: int | None, level: int) -> str:
    """有序列表用 num_id 引用编号定义；无序列表用样式 + 项目符号字符。"""
    indent = 360 + level * 360
    if num_id is None:
        runs = _run("\u2022  ", bold=True) + inline_runs(text)
        ppr = (
            f'<w:pPr><w:spacing w:after="40"/><w:ind w:left="{indent}" w:hanging="220"/></w:pPr>'
        )
    else:
        runs = inline_runs(text)
        ppr = (
            f'<w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr>'
            f'<w:ilvl w:val="{level}"/><w:numId w:val="{num_id}"/>'
            f"</w:numPr>"
            f'<w:spacing w:after="40"/><w:ind w:left="{indent}"/></w:pPr>'
        )
    return f"<w:p>{ppr}{runs}</w:p>"


def code_block(lines: list[str]) -> str:
    """等宽、带底纹的代码块，用单格表格实现整块背景。"""
    body = "".join(
        f"<w:p><w:pPr><w:spacing w:after=\"0\"/><w:jc w:val=\"left\"/></w:pPr>"
        f'{_run(line if line else " ", mono=True, size_half_pt=17)}</w:p>'
        for line in lines
    )
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:color="D0D7DE"/>'
        '<w:left w:val="single" w:sz="4" w:color="D0D7DE"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="D0D7DE"/>'
        '<w:right w:val="single" w:sz="4" w:color="D0D7DE"/>'
        "</w:tblBorders>"
        '<w:tblCellMar><w:top w:w="72" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>'
        '<w:bottom w:w="72" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar>'
        "</w:tblPr>"
        f'<w:tr><w:tc><w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="F6F8FA"/></w:tcPr>{body}</w:tc></w:tr>'
        "</w:tbl>"
    )


def table_block(rows: list[list[str]], *, repeat_header: bool = True) -> str:
    if not rows:
        return ""
    cols = max(len(row) for row in rows)
    usable = 9360  # A4 纵向、2cm 页边距下的可用宽度（twips 近似）
    width = usable // cols

    grid = "".join(f'<w:gridCol w:w="{width}"/>' for _ in range(cols))

    def cell(text: str, *, header: bool) -> str:
        shade = '<w:shd w:val="clear" w:color="auto" w:fill="E8EEF4"/>' if header else ""
        return (
            f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}'
            '<w:vAlign w:val="center"/></w:tcPr>'
            f'{para(text, bold=header, size_half_pt=18, spacing_after=0)}</w:tc>'
        )

    trs: list[str] = []
    for index, row in enumerate(rows):
        header = index == 0
        cells = "".join(cell(row[col] if col < len(row) else "", header=header) for col in range(cols))
        trpr = ""
        if header:
            trpr = "<w:trPr>"
            if repeat_header:
                trpr += "<w:tblHeader/>"
            trpr += "<w:cantSplit/></w:trPr>"
        trs.append(f"<w:tr>{trpr}{cells}</w:tr>")

    return (
        '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
        '<w:tblLayout w:type="fixed"/>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:color="BFBFBF"/>'
        '<w:left w:val="single" w:sz="4" w:color="BFBFBF"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="BFBFBF"/>'
        '<w:right w:val="single" w:sz="4" w:color="BFBFBF"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="D9D9D9"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="D9D9D9"/>'
        "</w:tblBorders>"
        '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
        '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
        "</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{''.join(trs)}</w:tbl>"
        '<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>'
    )


def hrule() -> str:
    return (
        '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:color="C9C9C9"/></w:pBdr>'
        '<w:spacing w:before="120" w:after="120"/></w:pPr></w:p>'
    )


def bookmark(name: str, bookmark_id: int) -> str:
    return (
        f'<w:bookmarkStart w:id="{bookmark_id}" w:name="{name}"/>'
        f'<w:bookmarkEnd w:id="{bookmark_id}"/>'
    )


def internal_link(anchor: str, text: str, *, level: int, number: str = "") -> str:
    """目录条目：超链接到同名书签，按层级缩进。"""
    indent = 240 + level * 300
    label = f"{number} " if number else ""
    runs = _run(label + text)
    return (
        f"<w:p><w:pPr><w:spacing w:after=\"20\" w:line=\"240\" w:lineRule=\"auto\"/>"
        f'<w:ind w:left="{indent}" w:hanging="0"/></w:pPr>'
        f'<w:hyperlink w:anchor="{esc(anchor)}">{runs}</w:hyperlink></w:p>'
    )


def blockquote(text: str) -> str:
    return (
        '<w:p><w:pPr><w:pBdr><w:left w:val="single" w:sz="18" w:color="9CC3D5" w:space="8"/></w:pBdr>'
        '<w:shd w:val="clear" w:color="auto" w:fill="F7FAFC"/>'
        '<w:ind w:left="260"/><w:spacing w:after="60"/></w:pPr>'
        f'{inline_runs(text)}</w:p>'
    )


HEADING_LEVELS = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
HEADING_SIZES = {1: 40, 2: 32, 3: 26, 4: 23, 5: 21, 6: 20}


# ---------------------------------------------------------------- Markdown 解析


def _split_table_row(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    # 先保护转义竖线，再切分
    sentinel = "\x00"
    body = body.replace("\\|", sentinel)
    return [cell.strip().replace(sentinel, "|") for cell in body.split("|")]


def _is_table_sep(line: str) -> bool:
    stripped = line.strip().strip("|")
    return bool(stripped) and all(
        set(part.strip()) <= set("-: ") and "-" in part for part in stripped.split("|")
    )


# ---------------------------------------------------------------- 目录与书签

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
HEADING_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*\.?)\s+(.*)$")


def slugify(title: str) -> str:
    """生成与 GitHub 完全一致的标题锚点。

    规则（按 GitHub 实际行为）：
      1. 转小写；去掉行内代码/链接的外壳，只留文字
      2. 删除标点（含 `.` `-` `:` `（）` `→` 等——注意连字符也要删，
         "复核 → 再" 因此得到 `复核--再` 两个连字符）
      3. 空白（含全角空格）→ `-`
    """
    text = re.sub(r"`([^`]*)`", r"\1", title.strip().lower())
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("\u3000", " ")
    # 只保留 word 字符、CJK、空格；连字符与其余标点一律删除
    text = re.sub(r"[^\w\u4e00-\u9fff ]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-") or "section"


def collect_headings(markdown: str) -> list[tuple[int, str, str]]:
    """收集 (level, 文本, 锚点)。跳过 `## 目录` 自身与 4 级及以下（目录保持精简）。"""
    headings: list[tuple[int, str, str]] = []
    in_fence = False
    used: dict[str, int] = {}
    for line in markdown.split("\n"):
        if re.match(r"^\s*```", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if not match:
            continue
        text = match.group(2).strip()
        if text == "目录":
            continue
        anchor = slugify(text)
        if anchor in used:
            used[anchor] += 1
            anchor = f"{anchor}-{used[anchor]}"
        else:
            used[anchor] = 0
        headings.append((len(match.group(1)), text, anchor))
    return headings


def render_toc(headings: list[tuple[int, str, str]]) -> str:
    """把标题列表渲染成可点击的目录。"""
    pieces = [
        para("目录", style="Heading1", size_half_pt=40, keep_next=True),
        '<w:p><w:pPr><w:spacing w:after="120"/></w:pPr></w:p>',
    ]
    for level, text, anchor in headings:
        if level > 3:
            continue
        numbered = HEADING_NUMBER_RE.match(text)
        number = numbered.group(1) if numbered else ""
        label_text = numbered.group(2) if numbered else text
        pieces.append(internal_link(anchor, _strip_markup(label_text), level=level - 1, number=number))
    return "".join(pieces)


def _strip_markup(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text


def split_toc_region(markdown: str) -> tuple[str, str] | None:
    """把文档切成 (目录之前, 目录之后)。目录 = `## 目录` 到下一个 --- 之间。"""
    lines = markdown.split("\n")
    start = None
    for index, line in enumerate(lines):
        if line.strip() == "## 目录":
            start = index
            break
    if start is None:
        return None
    for index in range(start + 1, len(lines)):
        if re.match(r"^\s*-{3,}\s*$", lines[index]):
            return ("\n".join(lines[: start + 1]), "\n".join(lines[index:]))
    return None


def markdown_to_body(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    index = 0
    ordered_counter = 0
    headings = collect_headings(markdown)
    anchors = {anchor for _, _, anchor in headings}
    bookmark_id = 100

    while index < len(lines):
        line = lines[index]

        # ## 目录：跳过原有手写目录，改用由标题生成的可点击目录
        if line.strip() == "## 目录":
            blocks.append(render_toc(headings))
            index += 1
            while index < len(lines) and not re.match(r"^\s*-{3,}\s*$", lines[index]):
                index += 1
            ordered_counter = 0
            continue

        # 围栏代码块
        fence = re.match(r"^\s*```", line)
        if fence:
            index += 1
            code: list[str] = []
            while index < len(lines) and not re.match(r"^\s*```", lines[index]):
                code.append(lines[index])
                index += 1
            index += 1  # 跳过结束围栏
            blocks.append(code_block(code))
            ordered_counter = 0
            continue

        # 表格：当前行是 |...| 且下一行是分隔行
        if "|" in line and index + 1 < len(lines) and _is_table_sep(lines[index + 1]):
            rows = [_split_table_row(line)]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(_split_table_row(lines[index]))
                index += 1
            blocks.append(table_block(rows))
            ordered_counter = 0
            continue

        # 标题
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2).strip()
            style = f"Heading{HEADING_LEVELS[level]}"
            # 与目录锚点对应，插入书签使目录可点击跳转
            anchor = slugify(text)
            marks = ""
            if anchor in anchors and level <= 3:
                bookmark_id += 1
                marks = bookmark(anchor, bookmark_id)
            blocks.append(
                marks + para(text, style=style, size_half_pt=HEADING_SIZES[level], keep_next=True)
            )
            ordered_counter = 0
            index += 1
            continue

        # 水平线
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            blocks.append(hrule())
            ordered_counter = 0
            index += 1
            continue

        # 引用块（支持连续多行）
        if re.match(r"^\s*>", line):
            quote: list[str] = []
            while index < len(lines) and re.match(r"^\s*>", lines[index]):
                quote.append(re.sub(r"^\s*>\s?", "", lines[index]))
                index += 1
            blocks.append(blockquote(" ".join(part for part in quote if part.strip())))
            ordered_counter = 0
            continue

        # 无序列表
        bullet = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if bullet:
            level = min(len(bullet.group(1)) // 2, 3)
            blocks.append(list_para(bullet.group(2), num_id=None, level=level))
            ordered_counter = 0
            index += 1
            continue

        # 有序列表
        ordered = re.match(r"^(\s*)\d+[.)]\s+(.*)$", line)
        if ordered:
            level = min(len(ordered.group(1)) // 3, 2)
            blocks.append(list_para(ordered.group(2), num_id=1, level=level))
            ordered_counter += 1
            index += 1
            continue

        # 空行
        if not line.strip():
            ordered_counter = 0
            index += 1
            continue

        # 普通段落
        blocks.append(para(line.strip()))
        ordered_counter = 0
        index += 1

    return "".join(blocks)


# ---------------------------------------------------------------- 静态部件

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
</Relationships>"""

SETTINGS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:zoom w:percent="100"/>
<w:defaultTabStop w:val="420"/>
<w:characterSpacingControl w:val="doNotCompress"/>
<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>
</w:settings>"""

NUMBERING = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:abstractNum w:abstractNumId="10">
<w:multiLevelType w:val="hybridMultilevel"/>
<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/>
<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:b/></w:rPr></w:lvl>
<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%2)"/>
<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="1080" w:hanging="360"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/></w:rPr></w:lvl>
<w:lvl w:ilvl="2"><w:start w:val="1"/><w:numFmt w:val="lowerRoman"/><w:lvlText w:val="%3."/>
<w:lvlJc w:val="right"/><w:pPr><w:ind w:left="1440" w:hanging="360"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/></w:rPr></w:lvl>
</w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="10"/></w:num>
</w:numbering>"""

FOOTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="0"/></w:pPr>
<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:color w:val="808080"/><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">第 </w:t></w:r>
<w:r><w:fldChar w:fldCharType="begin"/></w:r>
<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>
<w:r><w:fldChar w:fldCharType="separate"/></w:r>
<w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:t>1</w:t></w:r>
<w:r><w:fldChar w:fldCharType="end"/></w:r>
<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:color w:val="808080"/><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve"> / </w:t></w:r>
<w:r><w:fldChar w:fldCharType="begin"/></w:r>
<w:r><w:instrText xml:space="preserve"> NUMPAGES </w:instrText></w:r>
<w:r><w:fldChar w:fldCharType="separate"/></w:r>
<w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:t>1</w:t></w:r>
<w:r><w:fldChar w:fldCharType="end"/></w:r>
</w:p></w:ftr>"""


def _styles() -> str:
    def heading(level: int, size: int, color: str, before: int, after: int) -> str:
        return (
            f'<w:style w:type="paragraph" w:styleId="Heading{level}">'
            f'<w:name w:val="heading {level}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
            f'<w:qFormat/>'
            f'<w:pPr><w:keepNext/><w:spacing w:before="{before}" w:after="{after}"/>'
            f'<w:outlineLvl w:val="{level - 1}"/></w:pPr>'
            f'<w:rPr><w:rFonts w:ascii="{LATIN_FONT}" w:hAnsi="{LATIN_FONT}" w:eastAsia="{CJK_FONT}"/>'
            f'<w:b/><w:color w:val="{color}"/><w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
            f"</w:style>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:docDefaults><w:rPrDefault><w:rPr>'
        f'<w:rFonts w:ascii="{LATIN_FONT}" w:hAnsi="{LATIN_FONT}" w:eastAsia="{CJK_FONT}" w:cs="{LATIN_FONT}"/>'
        '<w:sz w:val="21"/><w:szCs w:val="21"/>'
        "</w:rPr></w:rPrDefault>"
        '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
        "</w:docDefaults>"
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
        '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
        '<w:basedOn w:val="Normal"/><w:qFormat/></w:style>'
        + heading(1, 40, "14395F", 320, 200)
        + heading(2, 32, "1F4E79", 280, 160)
        + heading(3, 26, "2E5C8A", 240, 120)
        + heading(4, 23, "33587A", 200, 100)
        + heading(5, 21, "33587A", 180, 80)
        + heading(6, 20, "404040", 160, 80)
        + "</w:styles>"
    )


def _document(body: str, title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<w:body>"
        + body
        # 章节属性：A4 + 2cm 页边距 + 页脚
        + '<w:sectPr><w:footerReference w:type="default" r:id="rId4"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
        'w:header="851" w:footer="992" w:gutter="0"/>'
        '<w:docGrid w:linePitch="312"/></w:sectPr>'
        "</w:body></w:document>"
    )


def _core(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{esc(title)}</dc:title>"
        "<dc:subject>智能体建设说明书</dc:subject>"
        "<cp:revision>1</cp:revision>"
        "</cp:coreProperties>"
    )


APP_PROPS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>Markdown to Word converter (stdlib)</Application>
</Properties>"""


def convert(markdown_path: Path, docx_path: Path, *, title: str | None = None) -> dict[str, int]:
    """执行转换，返回统计信息。"""
    markdown = markdown_path.read_text(encoding="utf-8")
    doc_title = title or markdown_path.stem

    body = markdown_to_body(markdown)
    document = _document(body, doc_title)

    docx_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", ROOT_RELS)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/_rels/document.xml.rels", DOC_RELS)
        zf.writestr("word/styles.xml", _styles())
        zf.writestr("word/numbering.xml", NUMBERING)
        zf.writestr("word/settings.xml", SETTINGS)
        zf.writestr("word/footer1.xml", FOOTER)
        zf.writestr("docProps/core.xml", _core(doc_title))
        zf.writestr("docProps/app.xml", APP_PROPS)

    return {
        "paragraphs": document.count("<w:p>"),
        "tables": document.count("<w:tbl>"),
        "chars": len(markdown),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="把 Markdown 说明书转换为 Word (.docx)")
    parser.add_argument("source", type=Path, help="输入的 Markdown 文件")
    parser.add_argument("target", type=Path, nargs="?", help="输出的 .docx 文件（默认与源文件同名）")
    parser.add_argument("--title", default=None, help="文档标题（写入文档属性）")
    args = parser.parse_args(argv)

    target = args.target or args.source.with_suffix(".docx")
    stats = convert(args.source, target, title=args.title)
    print(f"OK {args.source} -> {target}")
    print(f"  段落 {stats['paragraphs']} / 表格 {stats['tables']} / 源字符 {stats['chars']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
