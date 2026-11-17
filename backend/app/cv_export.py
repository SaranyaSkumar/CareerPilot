"""ATS-friendly CV rendering.

Single column, standard fonts, and selectable text. Contact details are plain
visible text. Role dates are right-aligned on the title line and still extract
in reading order: title, then dates, then employer. The PDF draws that line as
a tab stop. Word uses a borderless two-cell table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

BRAND = colors.HexColor("#174c3a")
INK = colors.HexColor("#26302a")
MUTED = colors.HexColor("#4b5b51")
BRAND_RGB = RGBColor(0x17, 0x4C, 0x3A)
INK_RGB = RGBColor(0x26, 0x30, 0x2A)
MUTED_RGB = RGBColor(0x4B, 0x5B, 0x51)

SECTIONS = (
    ("Professional Summary", "summary"),
    ("Experience", "experience"),
    ("Skills", "skills"),
    ("Education", "education"),
)

_BULLET = re.compile(r"^[-*•·–—]\s+")
_DATE = re.compile(
    r"^(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?"
    r"(?:19|20)\d{2}"
    r"(?:\s*(?:[-–—/]|to)\s*"
    r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?"
    r"(?:(?:19|20)\d{2}|present|current)"
    r")?$",
    re.IGNORECASE,
)
_CONTENT_WIDTH = A4[0] - 36 * mm


@dataclass(frozen=True)
class CvContact:
    email: str = ""
    phone: str = ""
    location: str = ""
    website_url: str = ""
    linkedin_url: str = ""
    github_url: str = ""


@dataclass
class Entry:
    title: str = ""
    dates: str = ""
    company: str = ""
    location: str = ""
    bullets: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    expect_company: bool = False

    @property
    def company_line(self) -> str:
        if self.company and self.location:
            return f"{self.company}, {self.location}"
        return self.company or self.location


def format_contact_line(contact: CvContact | None) -> str:
    if contact is None:
        return ""
    parts = (
        contact.email,
        contact.phone,
        contact.location,
        contact.website_url,
        contact.linkedin_url,
        contact.github_url,
    )
    return " | ".join(part.strip() for part in parts if part and part.strip())


def format_skill_lines(value: str) -> list[str]:
    raw_lines = [_BULLET.sub("", line.strip()) for line in _lines(value)]
    raw_lines = [line for line in raw_lines if line]
    grouped: list[str] = []
    loose: list[str] = []

    def flush() -> None:
        if not loose:
            return
        items: list[str] = []
        for chunk in loose:
            items.extend(part.strip() for part in re.split(r"[,;]", chunk) if part.strip())
        seen: set[str] = set()
        unique: list[str] = []
        for item in items:
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        if unique:
            grouped.append(", ".join(unique))
        loose.clear()

    for line in raw_lines:
        if ":" in line:
            flush()
            label, _, rest = line.partition(":")
            parts = [part.strip() for part in re.split(r"[,;]", rest) if part.strip()]
            grouped.append(f"{label.strip()}: {', '.join(parts)}" if parts else label.strip())
        else:
            loose.append(line)
    flush()
    return grouped


def parse_entries(value: str) -> list[Entry]:
    entries: list[Entry] = []
    current: Entry | None = None

    def close() -> None:
        nonlocal current
        if current is not None:
            entries.append(current)
            current = None

    for raw in _lines(value):
        line = raw.strip()
        if not line:
            close()
            continue
        if _BULLET.match(line):
            if current is None:
                current = Entry()
            current.bullets.append(_BULLET.sub("", line).strip())
            current.expect_company = False
            continue
        dated = _dated_header(line)
        if dated is not None and current is not None:
            close()
            current = dated
            continue
        if current is not None and current.expect_company:
            if _looks_like_prose(line):
                current.paragraphs.append(line)
            else:
                company, location = _split_company(line)
                current.company = company
                current.location = location
            current.expect_company = False
            continue
        if current is None:
            current = dated or _undated_header(line) or Entry(paragraphs=[line])
            continue
        current.paragraphs.append(line)
    close()
    return entries


def build_pdf(cv, contact: CvContact | None = None) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{(cv.name or 'CV').strip() or 'CV'} - CV",
        author=(cv.name or "").strip(),
    )
    styles = _pdf_styles()
    story: list = []
    name = (cv.name or "").strip() or "Your Name"
    story.append(Paragraph(_pdf_text(name), styles["name"]))
    headline = (cv.headline or "").strip()
    if headline:
        story.append(Paragraph(_pdf_text(headline), styles["headline"]))
    contact_line = format_contact_line(contact)
    if contact_line:
        story.append(Paragraph(_pdf_text(contact_line), styles["contact"]))

    for title, field_name in SECTIONS:
        flowables = _section_flowables(field_name, getattr(cv, field_name, "") or "", styles)
        if not flowables:
            continue
        heading = Paragraph(_pdf_text(title.upper()), styles["heading"])
        rule = HRFlowable(
            width="100%",
            thickness=0.6,
            color=BRAND,
            spaceBefore=1,
            spaceAfter=6,
            hAlign="LEFT",
        )
        story.append(KeepTogether([heading, rule, flowables[0]]))
        story.extend(flowables[1:])

    document.build(story)
    return output.getvalue()


def build_docx(cv, contact: CvContact | None = None) -> bytes:
    document = Document()
    section = document.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(16)
    section.bottom_margin = Mm(16)
    section.left_margin = Mm(18)
    section.right_margin = Mm(18)
    content_width = section.page_width - section.left_margin - section.right_margin
    _prepare_docx_styles(document)

    name = document.add_heading((cv.name or "").strip() or "Your Name", level=0)
    name.alignment = WD_ALIGN_PARAGRAPH.LEFT
    name.paragraph_format.space_before = Pt(0)
    name.paragraph_format.space_after = Pt(2)
    _paint_runs(name, "Arial", 22, BRAND_RGB, bold=True)

    headline = (cv.headline or "").strip()
    if headline:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(2)
        _add_run(paragraph, headline, "Arial", 11, MUTED_RGB, bold=True)

    contact_line = format_contact_line(contact)
    if contact_line:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(8)
        _add_run(paragraph, contact_line, "Arial", 9, MUTED_RGB)

    for title, field_name in SECTIONS:
        blocks = _section_blocks(field_name, getattr(cv, field_name, "") or "")
        if not blocks:
            continue
        heading = document.add_heading(title.upper(), level=1)
        heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
        heading.paragraph_format.space_before = Pt(12)
        heading.paragraph_format.space_after = Pt(2)
        heading.paragraph_format.keep_with_next = True
        _paint_runs(heading, "Arial", 11, BRAND_RGB, bold=True)
        _rule_under(heading)
        _write_docx_blocks(document, blocks, content_width)

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def _lines(value: str) -> list[str]:
    return value.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _looks_like_dates(value: str) -> bool:
    text = re.sub(r"\s+", " ", value.strip())
    if re.fullmatch(r"present|current", text, re.IGNORECASE):
        return True
    return _DATE.fullmatch(text) is not None


def _looks_like_prose(value: str) -> bool:
    words = value.split()
    if len(words) >= 8:
        return True
    return bool(re.search(r"[.!?]", value) and len(words) >= 4)


def _parts(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


def _dated_header(value: str) -> Entry | None:
    parts = _parts(value)
    if len(parts) < 2 or not _looks_like_dates(parts[-1]):
        return None
    middle = parts[1:-1]
    return Entry(
        title=parts[0],
        dates=parts[-1],
        company=middle[0] if middle else "",
        location=", ".join(middle[1:]) if len(middle) > 1 else "",
        expect_company=not middle,
    )


def _undated_header(value: str) -> Entry | None:
    parts = _parts(value)
    if len(parts) < 2 or _looks_like_dates(parts[-1]):
        return None
    return Entry(
        title=parts[0],
        company=parts[1],
        location=", ".join(parts[2:]),
        expect_company=False,
    )


def _split_company(value: str) -> tuple[str, str]:
    parts = _parts(value)
    if len(parts) >= 2 and not _looks_like_dates(parts[-1]):
        return parts[0], ", ".join(parts[1:])
    if "," in value and not _looks_like_prose(value):
        company, location = value.split(",", 1)
        return company.strip(), location.strip()
    return value.strip(), ""


def _pdf_text(value: str) -> str:
    return escape(value).replace("\n", "<br/>")


def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "CareerPilotName",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            alignment=TA_LEFT,
            textColor=BRAND,
            spaceBefore=0,
            spaceAfter=2,
        ),
        "headline": ParagraphStyle(
            "CareerPilotHeadline",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=MUTED,
            spaceBefore=0,
            spaceAfter=2,
        ),
        "contact": ParagraphStyle(
            "CareerPilotContact",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=MUTED,
            spaceBefore=0,
            spaceAfter=8,
        ),
        "heading": ParagraphStyle(
            "CareerPilotSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=BRAND,
            spaceBefore=11,
            spaceAfter=1,
            keepWithNext=True,
        ),
        "role": ParagraphStyle(
            "CareerPilotRole",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=INK,
            spaceBefore=0,
            spaceAfter=0,
        ),
        "company": ParagraphStyle(
            "CareerPilotCompany",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=12,
            textColor=MUTED,
            spaceBefore=1,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "CareerPilotBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceBefore=0,
            spaceAfter=3,
        ),
        "bullet": ParagraphStyle(
            "CareerPilotBullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=INK,
            leftIndent=14,
            bulletIndent=2,
            bulletFontName="Helvetica",
            bulletFontSize=10,
            spaceBefore=0,
            spaceAfter=1,
        ),
        "skills": ParagraphStyle(
            "CareerPilotSkills",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceBefore=0,
            spaceAfter=2,
        ),
    }


def _section_flowables(field_name: str, value: str, styles: dict[str, ParagraphStyle]) -> list:
    if field_name == "skills":
        return [Paragraph(_pdf_text(line), styles["skills"]) for line in format_skill_lines(value)]
    if field_name == "summary":
        paragraphs = [line.strip() for line in _lines(value) if line.strip()]
        return [Paragraph(_pdf_text(line), styles["body"]) for line in paragraphs]
    flowables: list = []
    for index, entry in enumerate(parse_entries(value)):
        flowables.extend(_entry_flowables(entry, styles, first=index == 0))
    return flowables


def _entry_flowables(entry: Entry, styles: dict[str, ParagraphStyle], first: bool) -> list:
    flows: list = []
    if not first:
        flows.append(Spacer(1, 8))
    if entry.title:
        if entry.dates:
            flows.append(TitleDatesLine(entry.title, entry.dates))
        else:
            flows.append(Paragraph(_pdf_text(entry.title), styles["role"]))
        if entry.company_line:
            flows.append(Paragraph(_pdf_text(entry.company_line), styles["company"]))
    flows.extend(Paragraph(_pdf_text(line), styles["body"]) for line in entry.paragraphs)
    flows.extend(
        Paragraph(_pdf_text(line), styles["bullet"], bulletText="•") for line in entry.bullets
    )
    return flows


class TitleDatesLine(Flowable):
    """One baseline: bold title on the left, dates on the right.

    Drawn as ordinary text operators, title first, so pdftotext -raw reads
    "Title ... Dates". A borderless table made the dates look like a second
    column and layout-mode extractors moved them below the role.
    """

    def __init__(self, title: str, dates: str):
        super().__init__()
        self.title = title
        self.dates = dates
        self._width = _CONTENT_WIDTH
        self._stacked = False
        self.height = 14

    def wrap(self, availWidth, availHeight):
        self._width = availWidth
        title_width = stringWidth(self.title, "Helvetica-Bold", 10.5)
        date_width = stringWidth(self.dates, "Helvetica", 9.5)
        self._stacked = title_width + date_width + 16 > availWidth
        self.height = 28 if self._stacked else 14
        return availWidth, self.height

    def draw(self):
        if self._stacked:
            self.canv.setFillColor(INK)
            self.canv.setFont("Helvetica-Bold", 10.5)
            self.canv.drawString(0, 14, self.title)
            self.canv.setFillColor(MUTED)
            self.canv.setFont("Helvetica", 9.5)
            self.canv.drawRightString(self._width, 1, self.dates)
            return
        self.canv.setFillColor(INK)
        self.canv.setFont("Helvetica-Bold", 10.5)
        self.canv.drawString(0, 2, self.title)
        self.canv.setFillColor(MUTED)
        self.canv.setFont("Helvetica", 9.5)
        self.canv.drawRightString(self._width, 2, self.dates)


def _section_blocks(field_name: str, value: str) -> list:
    if field_name == "skills":
        return [("skills", line) for line in format_skill_lines(value)]
    if field_name == "summary":
        return [("body", line.strip()) for line in _lines(value) if line.strip()]
    return [("entry", entry) for entry in parse_entries(value)]


def _write_docx_blocks(document: Document, blocks: list, content_width) -> None:
    first_entry = True
    for kind, payload in blocks:
        if kind == "skills":
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(1)
            paragraph.paragraph_format.space_after = Pt(1)
            _add_run(paragraph, payload, "Arial", 10.5, INK_RGB)
            continue
        if kind == "body":
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(1)
            paragraph.paragraph_format.space_after = Pt(2)
            _add_run(paragraph, payload, "Arial", 10.5, INK_RGB)
            continue
        entry: Entry = payload
        if entry.title:
            if entry.dates:
                _add_role_table(document, entry.title, entry.dates, content_width, first=first_entry)
            else:
                paragraph = document.add_paragraph()
                paragraph.paragraph_format.space_before = Pt(2 if first_entry else 10)
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.keep_with_next = True
                _add_run(paragraph, entry.title, "Arial", 11, INK_RGB, bold=True)
            if entry.company_line:
                paragraph = document.add_paragraph()
                paragraph.paragraph_format.space_before = Pt(0)
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.paragraph_format.keep_with_next = bool(entry.bullets or entry.paragraphs)
                _add_run(paragraph, entry.company_line, "Arial", 10.5, MUTED_RGB, italic=True)
        for line in entry.paragraphs:
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(1)
            paragraph.paragraph_format.space_after = Pt(2)
            _add_run(paragraph, line, "Arial", 10.5, INK_RGB)
        for line in entry.bullets:
            paragraph = document.add_paragraph(line, style="List Bullet")
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(1)
            paragraph.paragraph_format.line_spacing = 1.08
            _paint_runs(paragraph, "Arial", 10.5, INK_RGB)
        first_entry = False


def _add_role_table(document: Document, title: str, dates: str, content_width, first: bool) -> None:
    table = document.add_table(rows=1, cols=2)
    table.autofit = False
    table.allow_autofit = False
    _clear_table_borders(table)
    dates_width = int(content_width * 0.32)
    title_width = int(content_width) - dates_width
    _set_table_geometry(table, [title_width, dates_width])
    left = table.cell(0, 0).paragraphs[0]
    right = table.cell(0, 1).paragraphs[0]
    left.alignment = WD_ALIGN_PARAGRAPH.LEFT
    right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    left.paragraph_format.space_before = Pt(2 if first else 10)
    left.paragraph_format.space_after = Pt(0)
    right.paragraph_format.space_before = Pt(2 if first else 10)
    right.paragraph_format.space_after = Pt(0)
    left.paragraph_format.keep_together = True
    _add_run(left, title, "Arial", 11, INK_RGB, bold=True)
    _add_run(right, dates, "Arial", 10.5, MUTED_RGB)


def _prepare_docx_styles(document: Document) -> None:
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = INK_RGB
    normal.paragraph_format.space_after = Pt(2)
    _set_style_font(normal, "Arial")

    title = document.styles["Title"]
    title.font.name = "Arial"
    title.font.size = Pt(22)
    title.font.bold = True
    title.font.color.rgb = BRAND_RGB
    title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    title.paragraph_format.space_after = Pt(2)
    _set_style_font(title, "Arial")

    heading = document.styles["Heading 1"]
    heading.font.name = "Arial"
    heading.font.size = Pt(11)
    heading.font.bold = True
    heading.font.color.rgb = BRAND_RGB
    heading.paragraph_format.space_before = Pt(12)
    heading.paragraph_format.space_after = Pt(2)
    _set_style_font(heading, "Arial")

    bullet = document.styles["List Bullet"]
    bullet.font.name = "Arial"
    bullet.font.size = Pt(10.5)
    bullet.font.color.rgb = INK_RGB
    bullet.paragraph_format.space_before = Pt(0)
    bullet.paragraph_format.space_after = Pt(1)
    _set_style_font(bullet, "Arial")


def _set_style_font(style, name: str) -> None:
    font = style.element.find(qn("w:rPr"))
    if font is None:
        font = OxmlElement("w:rPr")
        style.element.append(font)
    fonts = font.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        font.append(fonts)
    for attribute in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(attribute), name)


def _add_run(paragraph, text: str, name: str, size: float, color: RGBColor, bold=False, italic=False):
    run = paragraph.add_run(text)
    _paint_run(run, name, size, color, bold=bold, italic=italic)
    return run


def _paint_runs(paragraph, name: str, size: float, color: RGBColor, bold=False) -> None:
    for run in paragraph.runs:
        _paint_run(run, name, size, color, bold=bold or bool(run.bold))


def _paint_run(run, name: str, size: float, color: RGBColor, bold=False, italic=False) -> None:
    run.bold = bold
    run.italic = italic
    run.font.name = name
    run.font.size = Pt(size)
    run.font.color.rgb = color
    fonts = run._element.get_or_add_rPr().find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        run._element.get_or_add_rPr().append(fonts)
    for attribute in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(attribute), name)


def _rule_under(paragraph) -> None:
    properties = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "174C3A")
    borders.append(bottom)
    properties.append(borders)


def _clear_table_borders(table) -> None:
    properties = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        element.set(qn("w:sz"), "0")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "auto")
        borders.append(element)
    properties.append(borders)


def _twips(length: int) -> int:
    # python-docx lengths are English Metric Units. Word table widths are twips.
    return int(round(int(length) / 635))


def _set_table_geometry(table, widths: list[int]) -> None:
    properties = table._tbl.tblPr
    table_width = properties.find(qn("w:tblW"))
    if table_width is None:
        table_width = OxmlElement("w:tblW")
        properties.append(table_width)
    table_width.set(qn("w:w"), str(_twips(sum(widths))))
    table_width.set(qn("w:type"), "dxa")
    layout = properties.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        properties.append(layout)
    layout.set(qn("w:type"), "fixed")

    grid = table._tbl.find(qn("w:tblGrid"))
    if grid is None:
        grid = OxmlElement("w:tblGrid")
        properties.addnext(grid)
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        column = OxmlElement("w:gridCol")
        column.set(qn("w:w"), str(_twips(width)))
        grid.append(column)

    for cell, width in zip(table.rows[0].cells, widths):
        cell.width = width
        cell_properties = cell._tc.get_or_add_tcPr()
        cell_width = cell_properties.find(qn("w:tcW"))
        if cell_width is None:
            cell_width = OxmlElement("w:tcW")
            cell_properties.append(cell_width)
        cell_width.set(qn("w:w"), str(_twips(width)))
        cell_width.set(qn("w:type"), "dxa")

