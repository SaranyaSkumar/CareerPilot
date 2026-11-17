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
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer


SECTION_FIELDS = (
    ("Professional summary", "summary"),
    ("Experience", "experience"),
    ("Skills", "skills"),
    ("Education", "education"),
)


def _paragraphs(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def build_docx(cv) -> bytes:
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(9.5)
    normal.font.color.rgb = RGBColor(38, 48, 42)
    normal.paragraph_format.space_after = Pt(4)

    name = document.add_paragraph()
    name.alignment = WD_ALIGN_PARAGRAPH.LEFT
    name.paragraph_format.space_after = Pt(2)
    run = name.add_run(cv.name.strip() or "Your Name")
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(23)
    run.font.color.rgb = RGBColor(23, 76, 58)

    headline = document.add_paragraph()
    headline.paragraph_format.space_after = Pt(12)
    run = headline.add_run(cv.headline.strip())
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(75, 91, 81)

    for title, field in SECTION_FIELDS:
        value = getattr(cv, field, "") or ""
        lines = _paragraphs(value)
        if not lines:
            continue
        heading = document.add_paragraph()
        heading.paragraph_format.space_before = Pt(9)
        heading.paragraph_format.space_after = Pt(4)
        heading_run = heading.add_run(title.upper())
        heading_run.bold = True
        heading_run.font.size = Pt(9)
        heading_run.font.color.rgb = RGBColor(23, 76, 58)
        for line in lines:
            paragraph = document.add_paragraph(line)
            paragraph.paragraph_format.keep_together = True

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
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{cv.name or 'CV'} - CV",
        author=cv.name or "",
    )
    base = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "CareerPilotName", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=21, leading=25, alignment=TA_LEFT, textColor=colors.HexColor("#174c3a"),
        spaceAfter=3,
    )
    headline_style = ParagraphStyle(
        "CareerPilotHeadline", parent=base["Normal"], fontName="Helvetica-Bold",
        fontSize=10.5, leading=14, textColor=colors.HexColor("#4b5b51"), spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "CareerPilotSection", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=9, leading=12, textColor=colors.HexColor("#174c3a"),
        spaceBefore=10, spaceAfter=4, keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "CareerPilotBody", parent=base["BodyText"], fontName="Helvetica",
        fontSize=9, leading=13, textColor=colors.HexColor("#26302a"), spaceAfter=4,
    )

    story = [
        Paragraph(escape(cv.name.strip() or "Your Name"), name_style),
        Paragraph(escape(cv.headline.strip()), headline_style),
    ]
    for title, field in SECTION_FIELDS:
        lines = _paragraphs(getattr(cv, field, "") or "")
        if not lines:
            continue
        section = [Paragraph(escape(title.upper()), heading_style)]
        section.extend(Paragraph(escape(line), body_style) for line in lines)
        story.append(KeepTogether(section[:2]))
        story.extend(section[2:])
    document.build(story)
    return output.getvalue()
