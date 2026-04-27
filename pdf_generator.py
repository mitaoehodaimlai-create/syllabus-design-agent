"""Convert assembled Markdown syllabus to a professional PDF using ReportLab."""

import re
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

# ── Colours ──────────────────────────────────────────────────────
C_NAVY   = colors.HexColor("#1e3a5f")
C_BLUE   = colors.HexColor("#2c5282")
C_LBLUE  = colors.HexColor("#ebf4ff")
C_STRIP  = colors.HexColor("#f7fafc")
C_GRID   = colors.HexColor("#cbd5e0")
C_WHITE  = colors.white
C_BLACK  = colors.black
C_DARK   = colors.HexColor("#2d3748")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


# ─────────────────────────────────────────────────────────────────
# Style sheet
# ─────────────────────────────────────────────────────────────────
def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    s: dict[str, Any] = {}

    s["title"] = ParagraphStyle(
        "title", parent=base["Title"],
        fontSize=20, textColor=C_NAVY, spaceAfter=6, alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    s["subtitle"] = ParagraphStyle(
        "subtitle", parent=base["Normal"],
        fontSize=10, textColor=C_BLUE, spaceAfter=12, alignment=TA_CENTER,
    )
    s["h1"] = ParagraphStyle(
        "h1", parent=base["Heading1"],
        fontSize=14, textColor=C_WHITE, backColor=C_NAVY,
        spaceAfter=6, spaceBefore=14, leftIndent=-2,
        fontName="Helvetica-Bold", leading=20,
    )
    s["h2"] = ParagraphStyle(
        "h2", parent=base["Heading2"],
        fontSize=12, textColor=C_NAVY,
        spaceAfter=4, spaceBefore=10,
        fontName="Helvetica-Bold",
        borderPad=2,
    )
    s["h3"] = ParagraphStyle(
        "h3", parent=base["Heading3"],
        fontSize=11, textColor=C_BLUE,
        spaceAfter=3, spaceBefore=8,
        fontName="Helvetica-BoldOblique",
    )
    s["normal"] = ParagraphStyle(
        "normal", parent=base["Normal"],
        fontSize=9.5, textColor=C_DARK, leading=13,
        spaceAfter=3, alignment=TA_JUSTIFY,
    )
    s["bullet"] = ParagraphStyle(
        "bullet", parent=base["Normal"],
        fontSize=9.5, textColor=C_DARK, leading=13,
        leftIndent=14, bulletIndent=6, spaceAfter=2,
    )
    s["numbered"] = ParagraphStyle(
        "numbered", parent=base["Normal"],
        fontSize=9.5, textColor=C_DARK, leading=13,
        leftIndent=18, spaceAfter=2,
    )
    s["code"] = ParagraphStyle(
        "code", parent=base["Code"],
        fontSize=8.5, textColor=colors.HexColor("#1a202c"),
        backColor=colors.HexColor("#edf2f7"),
        leftIndent=10, rightIndent=10,
        spaceBefore=4, spaceAfter=4,
    )
    s["table_header"] = ParagraphStyle(
        "table_header",
        fontName="Helvetica-Bold", fontSize=8.5,
        textColor=C_WHITE, alignment=TA_CENTER,
    )
    s["table_cell"] = ParagraphStyle(
        "table_cell",
        fontName="Helvetica", fontSize=8,
        textColor=C_DARK, leading=11, alignment=TA_LEFT,
    )
    s["blockquote"] = ParagraphStyle(
        "blockquote", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#4a5568"),
        leftIndent=20, rightIndent=10, spaceAfter=4,
        backColor=colors.HexColor("#fffde7"),
        borderPad=4,
    )
    return s


# ─────────────────────────────────────────────────────────────────
# Inline markdown → ReportLab HTML
# ─────────────────────────────────────────────────────────────────
def _inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*",     r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`",       r'<font face="Courier" size="8">\1</font>', text)
    return text


# ─────────────────────────────────────────────────────────────────
# Table builder
# ─────────────────────────────────────────────────────────────────
def _build_table(raw_lines: list[str], styles: dict) -> Table | None:
    rows: list[list[Any]] = []
    for line in raw_lines:
        # Skip separator rows like |---|---|
        if re.match(r"^\|[-:\s|]+\|?\s*$", line.strip()):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not any(cells):
            continue
        rows.append(cells)

    if not rows:
        return None

    # First row → header
    header_cells = [Paragraph(_inline(c), styles["table_header"]) for c in rows[0]]
    data: list[list[Any]] = [header_cells]
    for row in rows[1:]:
        data.append([Paragraph(_inline(c), styles["table_cell"]) for c in row])

    col_count = max(len(r) for r in data)
    usable_w  = PAGE_W - 2 * MARGIN
    col_w     = usable_w / col_count

    tbl = Table(data, colWidths=[col_w] * col_count, repeatRows=1)
    ts  = TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  C_NAVY),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  8.5),
        ("ALIGN",        (0, 0), (-1, 0),  "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE",     (0, 1), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("GRID",         (0, 0), (-1, -1), 0.4, C_GRID),
    ])
    # Alternating row colours
    for i in range(1, len(data)):
        bg = C_LBLUE if i % 2 == 0 else C_WHITE
        ts.add("BACKGROUND", (0, i), (-1, i), bg)
    tbl.setStyle(ts)
    return tbl


# ─────────────────────────────────────────────────────────────────
# Markdown → list of Flowables
# ─────────────────────────────────────────────────────────────────
def _md_to_flowables(md_text: str, styles: dict) -> list[Any]:
    flowables: list[Any] = []
    lines = md_text.split("\n")
    i = 0

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # Page-break hint: horizontal rule with 3+ dashes on its own line
        if re.match(r"^-{3,}$", stripped):
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=C_GRID, spaceAfter=4))
            i += 1
            continue

        # Headers
        if stripped.startswith("# "):
            flowables.append(Spacer(1, 4))
            flowables.append(Paragraph(_inline(stripped[2:]), styles["h1"]))
            flowables.append(Spacer(1, 2))
        elif stripped.startswith("## "):
            flowables.append(Spacer(1, 3))
            flowables.append(Paragraph(_inline(stripped[3:]), styles["h2"]))
        elif stripped.startswith("### "):
            flowables.append(Paragraph(_inline(stripped[4:]), styles["h3"]))
        elif stripped.startswith("#### "):
            flowables.append(Paragraph(f"<b>{_inline(stripped[5:])}</b>", styles["normal"]))

        # Markdown tables
        elif stripped.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            tbl = _build_table(table_lines, styles)
            if tbl:
                flowables.append(Spacer(1, 4))
                flowables.append(tbl)
                flowables.append(Spacer(1, 6))
            continue

        # Blockquotes
        elif stripped.startswith("> "):
            flowables.append(Paragraph(_inline(stripped[2:]), styles["blockquote"]))

        # Bullet lists (- or *)
        elif re.match(r"^[-*]\s+", stripped):
            text = re.sub(r"^[-*]\s+", "", stripped)
            flowables.append(Paragraph(f"• {_inline(text)}", styles["bullet"]))

        # Numbered list
        elif re.match(r"^\d+\.\s+", stripped):
            text = re.sub(r"^\d+\.\s+", "", stripped)
            num  = re.match(r"^(\d+)\.", stripped).group(1)
            flowables.append(Paragraph(f"{num}. {_inline(text)}", styles["numbered"]))

        # Empty line → small spacer
        elif stripped == "":
            flowables.append(Spacer(1, 4))

        # Normal paragraph
        else:
            flowables.append(Paragraph(_inline(stripped), styles["normal"]))

        i += 1

    return flowables


# ─────────────────────────────────────────────────────────────────
# Cover page
# ─────────────────────────────────────────────────────────────────
def _cover_page(course_title: str, meta: dict[str, str], styles: dict) -> list[Any]:
    items: list[Any] = [
        Spacer(1, 40 * mm),
        Paragraph("COURSE DESIGN DOCUMENT", styles["subtitle"]),
        Paragraph(course_title.upper(), styles["title"]),
        Spacer(1, 6 * mm),
        HRFlowable(width="80%", thickness=2, color=C_NAVY, hAlign="CENTER"),
        Spacer(1, 8 * mm),
    ]
    for k, v in meta.items():
        items.append(Paragraph(f"<b>{k}:</b>  {v}", styles["subtitle"]))
    items += [Spacer(1, 30 * mm), PageBreak()]
    return items


# ─────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────
def generate_pdf(
    markdown_text: str,
    output_path: str | Path,
    course_title: str = "",
    meta: dict[str, str] | None = None,
) -> Path:
    """Convert a full markdown syllabus string into a PDF file."""
    output_path = Path(output_path)
    styles      = _build_styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=course_title or "Course Design Document",
        author="Syllabus Design Agent",
    )

    story: list[Any] = []

    # Cover page
    if course_title:
        story += _cover_page(course_title, meta or {}, styles)

    # Body
    story += _md_to_flowables(markdown_text, styles)

    doc.build(story)
    return output_path
