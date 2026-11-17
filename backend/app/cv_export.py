from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer


SECTION_FIELDS = (
    ("Professional summary", "summary"),
    ("Professional experience", "experience"),
    ("Technical skills", "skills"),
    ("Education", "education"),
)

NAVY = "#172B4D"
SLATE = "#52647A"
BODY = "#263445"
RULE = "#CBD5E1"


def _paragraphs(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _is_bullet(line: str) -> bool:
    return line.startswith(("- ", "• ", "* "))


def _clean_bullet(line: str) -> str:
    return line[2:].strip() if _is_bullet(line) else line


def build_docx(cv) -> bytes:
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.62)
    section.bottom_margin = Inches(0.62)
    section.left_margin = Inches(0.72)
    section.right_margin = Inches(0.72)

    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(9.5)
    normal.font.color.rgb = RGBColor(38, 52, 69)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.08

    name = document.add_paragraph()
    name.alignment = WD_ALIGN_PARAGRAPH.LEFT
    name.paragraph_format.space_after = Pt(2)
    run = name.add_run(cv.name.strip() or "Your Name")
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(23)
    run.font.color.rgb = RGBColor(23, 43, 77)

    headline = document.add_paragraph()
    headline.paragraph_format.space_after = Pt(7)
    run = headline.add_run(cv.headline.strip())
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(10.5)
    run.font.color.rgb = RGBColor(82, 100, 122)

    rule = document.add_paragraph()
    rule.paragraph_format.space_after = Pt(7)
    rule.paragraph_format.space_before = Pt(0)
    rule_run = rule.add_run(" ")
    rule_run.font.size = Pt(2)
    rule_run.font.color.rgb = RGBColor(203, 213, 225)
    p_borders = rule._p.get_or_add_pPr()
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "CBD5E1")
    borders.append(bottom)
    p_borders.append(borders)

    for title, field in SECTION_FIELDS:
        lines = _paragraphs(getattr(cv, field, "") or "")
        if not lines:
            continue
        heading = document.add_paragraph()
        heading.paragraph_format.space_before = Pt(9)
        heading.paragraph_format.space_after = Pt(4)
        heading.paragraph_format.keep_with_next = True
        heading_run = heading.add_run(title.upper())
        heading_run.bold = True
        heading_run.font.name = "Arial"
        heading_run.font.size = Pt(8.5)
        heading_run.font.color.rgb = RGBColor(23, 43, 77)
        for line in lines:
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.keep_together = True
            if _is_bullet(line):
                paragraph.paragraph_format.left_indent = Inches(0.18)
                paragraph.paragraph_format.first_line_indent = Inches(-0.14)
                paragraph.add_run("•  ")
                paragraph.add_run(_clean_bullet(line))
            else:
                paragraph.add_run(line)

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def build_pdf(cv) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"{cv.name or 'CV'} - CV",
        author=cv.name or "",
        subject="CareerPilot ATS-friendly CV",
    )
    base = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "CareerPilotName",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        alignment=TA_LEFT,
        textColor=colors.HexColor(NAVY),
        spaceAfter=2,
    )
    headline_style = ParagraphStyle(
        "CareerPilotHeadline",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor(SLATE),
        spaceAfter=8,
    )
    heading_style = ParagraphStyle(
        "CareerPilotSection",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor(NAVY),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "CareerPilotBody",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor(BODY),
        spaceAfter=4,
        allowWidows=0,
        allowOrphans=0,
    )
    bullet_style = ParagraphStyle(
        "CareerPilotBullet",
        parent=body_style,
        leftIndent=11,
        firstLineIndent=-8,
        bulletIndent=0,
        spaceAfter=3,
    )

    story = [
        Paragraph(escape(cv.name.strip() or "Your Name"), name_style),
        Paragraph(escape(cv.headline.strip()), headline_style),
        HRFlowable(width="100%", thickness=0.7, color=colors.HexColor(RULE), spaceAfter=5),
    ]
    for title, field in SECTION_FIELDS:
        lines = _paragraphs(getattr(cv, field, "") or "")
        if not lines:
            continue
        section_story = [Paragraph(escape(title.upper()), heading_style)]
        for line in lines:
            if _is_bullet(line):
                section_story.append(
                    Paragraph(escape(_clean_bullet(line)), bullet_style, bulletText="•")
                )
            else:
                section_story.append(Paragraph(escape(line), body_style))
        story.append(KeepTogether(section_story[:2]))
        story.extend(section_story[2:])

    document.build(story)
    return output.getvalue()
