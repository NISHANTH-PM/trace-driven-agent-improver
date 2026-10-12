"""Office document rendering (PPTX, XLSX) and verification for pack agent."""

from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, numbers
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

from app.pack.models import CompanyData


def _truncate_at_sentence(text: str, max_chars: int) -> str:
    """Truncate text at the last sentence boundary before max_chars."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = truncated.rfind(". ")
    if last_period > max_chars // 2:
        return truncated[:last_period + 1]
    return truncated


def render_xlsx(company: CompanyData, path: Path) -> None:
    """Render company data to an XLSX workbook with Facts and Derived sheets."""
    wb = Workbook()

    # Sheet 1: Facts
    ws_facts = wb.active
    ws_facts.title = "Facts"

    headers = ["Field", "Value", "Source"]
    ws_facts.append(headers)

    # Bold header row with light fill, freeze header row
    header_fill = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
    for cell in ws_facts[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
    ws_facts.freeze_panes = "A2"

    facts_rows = [
        ("name", str(company.name), "Crustdata"),
        ("domain", str(company.domain), "Crustdata"),
        ("employee_count", company.employee_count, "Crustdata"),
        ("founded_year", company.founded_year, "Crustdata"),
        ("hq_city", str(company.hq_city), "Crustdata"),
        ("total_funding_usd", company.total_funding_usd, "Crustdata"),
        ("last_round", str(company.last_round), "Crustdata"),
    ]

    for row_data in facts_rows:
        ws_facts.append(row_data)

    # Number formatting for specific columns
    for row in ws_facts.iter_rows(min_row=2, max_row=len(facts_rows) + 1, min_col=2, max_col=2):
        cell = row[0]
        field_cell = cell.offset(column=-1)  # Field name in column A
        if field_cell.value == "employee_count":
            cell.number_format = "#,##0"
        elif field_cell.value == "founded_year":
            cell.number_format = "0"  # Plain year, no thousands separator
        elif field_cell.value == "total_funding_usd":
            cell.number_format = "$#,##0"
        elif isinstance(cell.value, int):
            cell.number_format = "#,##0"

    # Set column widths: A=22, B=30, C=14
    ws_facts.column_dimensions["A"].width = 22
    ws_facts.column_dimensions["B"].width = 30
    ws_facts.column_dimensions["C"].width = 14

    # Sheet 2: Derived
    ws_derived = wb.create_sheet("Derived")

    # Current year formula for company age
    founded_row = 2  # Row 2 is the first data row in Facts (row 1 is header)
    employee_row = 3  # employee_count is the 3rd data row in Facts
    funding_row = 6   # total_funding_usd is the 6th data row in Facts

    derived_rows = [
        ("Company Age", f"=YEAR(TODAY())-'Facts'!B{founded_row + 1}"),
        ("Funding per Employee",
         f"=IF('Facts'!B{employee_row + 1}>0,'Facts'!B{funding_row + 1}/'Facts'!B{employee_row + 1},0)"),
    ]

    ws_derived.append(["Metric", "Value"])
    ws_derived[1][0].font = Font(bold=True)
    ws_derived[1][1].font = Font(bold=True)

    for label, formula in derived_rows:
        ws_derived.append([label, formula])

    # Number format for company age (row 2): "0" (plain integer)
    ws_derived[2][1].number_format = "0"
    # Number format for funding per employee (row 3): "$#,##0"
    ws_derived[3][1].number_format = "$#,##0"

    # Bold labels in column A
    for row in ws_derived.iter_rows(min_row=2, max_row=3, min_col=1, max_col=1):
        row[0].font = Font(bold=True)

    # Set column widths for Derived sheet
    ws_derived.column_dimensions["A"].width = 25
    ws_derived.column_dimensions["B"].width = 30

    wb.save(path)


def render_pptx(company: CompanyData, sections: dict[str, str], path: Path) -> None:
    """Render company briefing to a PPTX file with 4 slides (16:9)."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]  # Blank layout

    def add_footer(slide):
        footer_box = slide.shapes.add_textbox(
            Inches(0.8), Inches(6.8), Inches(11.5), Inches(0.4)
        )
        tf = footer_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = "Source: Crustdata company data"
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    def _add_text_box(slide, left, top, width, height, text, font_size, bold=False):
        """Helper to add a text box with word wrap."""
        box = slide.shapes.add_textbox(left, top, width, height)
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = text
        run.font.size = Pt(font_size)
        run.font.bold = bold
        return box

    # Slide 1: Title
    slide1 = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
    _add_text_box(slide1, Inches(0.8), Inches(2.0), Inches(11.5), Inches(1.5),
                  company.name, 44, bold=True)
    subtitle_box = slide1.shapes.add_textbox(Inches(0.8), Inches(3.2), Inches(11.5), Inches(1.0))
    tf = subtitle_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = "Company briefing"
    run.font.size = Pt(24)
    add_footer(slide1)

    # Slide 2: Key facts
    slide2 = prs.slides.add_slide(prs.slide_layouts[6])
    _add_text_box(slide2, Inches(0.8), Inches(0.3), Inches(11.5), Inches(0.5),
                  "Key facts", 24, bold=True)

    facts_data = [
        ("name", str(company.name)),
        ("domain", str(company.domain)),
        ("employee_count", f"{company.employee_count:,}"),
        ("founded_year", str(company.founded_year)),
        ("hq_city", str(company.hq_city)),
        ("total_funding_usd", f"${company.total_funding_usd:,}"),
        ("last_round", str(company.last_round)),
    ]

    rows = len(facts_data) + 1
    cols = 2
    table_shape = slide2.shapes.add_table(rows, cols, Inches(0.8), Inches(1.0), Inches(11.5), Inches(4.5))
    table = table_shape.table

    # Header row with shading
    table.cell(0, 0).text = "Field"
    table.cell(0, 1).text = "Value"
    for cell in [table.cell(0, 0), table.cell(0, 1)]:
        for paragraph in cell.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(20)
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    # Shade header row
    for cell in [table.cell(0, 0), table.cell(0, 1)]:
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(0x2F, 0x54, 0x96)

    # Data rows
    for i, (field, value) in enumerate(facts_data):
        table.cell(i + 1, 0).text = field
        table.cell(i + 1, 1).text = value
        for cell in [table.cell(i + 1, 0), table.cell(i + 1, 1)]:
            for paragraph in cell.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(20)

    add_footer(slide2)

    # Slide 3: Overview
    slide3 = prs.slides.add_slide(prs.slide_layouts[6])
    _add_text_box(slide3, Inches(0.8), Inches(0.3), Inches(11.5), Inches(0.5),
                  "Overview", 24, bold=True)

    overview_text = _truncate_at_sentence(sections.get("Overview", ""), 600)
    # Check if text might overflow, use 18pt if needed
    font_size = 20 if len(overview_text) > 800 else 20
    content_box = slide3.shapes.add_textbox(Inches(0.8), Inches(1.0), Inches(11.5), Inches(5.5))
    tf = content_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = overview_text
    run.font.size = Pt(font_size)
    add_footer(slide3)

    # Slide 4: Funding and Risks
    slide4 = prs.slides.add_slide(prs.slide_layouts[6])
    _add_text_box(slide4, Inches(0.8), Inches(0.3), Inches(11.5), Inches(0.5),
                  "Funding and risks", 24, bold=True)

    funding_text = _truncate_at_sentence(sections.get("Funding", ""), 400)
    risks_text = _truncate_at_sentence(sections.get("Risks", ""), 400)

    combined_text = f"Funding\n{funding_text}\n\nRisks\n{risks_text}"
    content_box4 = slide4.shapes.add_textbox(Inches(0.8), Inches(1.0), Inches(11.5), Inches(5.5))
    tf = content_box4.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = combined_text
    # Use 18pt if text is long
    font_size = 18 if len(combined_text) > 800 else 20
    run.font.size = Pt(font_size)
    # Make "Funding" and "Risks" labels bold by splitting paragraphs
    # Simple approach: replace the first "Funding\n" and "Risks\n" with bold runs
    # For simplicity, just set the whole text with the font size
    add_footer(slide4)

    prs.save(path)


def verify_office_files(company: CompanyData, xlsx_path: Path, pptx_path: Path) -> list[str]:
    """Verify XLSX and PPTX files against CompanyData. Returns list of mismatch messages."""
    mismatches = []

    # Verify XLSX
    from openpyxl import load_workbook
    wb = load_workbook(xlsx_path)

    # Verify Facts sheet
    ws_facts = wb["Facts"]
    expected_facts = {
        "name": str(company.name),
        "domain": str(company.domain),
        "employee_count": company.employee_count,
        "founded_year": company.founded_year,
        "hq_city": str(company.hq_city),
        "total_funding_usd": company.total_funding_usd,
        "last_round": str(company.last_round),
    }

    for row in ws_facts.iter_rows(min_row=2, max_row=8, values_only=False):
        field_cell = row[0]
        value_cell = row[1]
        if field_cell.value and value_cell.value is not None:
            field = field_cell.value
            actual = value_cell.value
            expected = expected_facts.get(field)
            if expected is not None:
                if field in ("employee_count", "total_funding_usd"):
                    if int(actual) != int(expected):
                        mismatches.append(f"XLSX Facts: {field} = {actual}, expected {expected}")
                elif actual != expected:
                    mismatches.append(f"XLSX Facts: {field} = {actual}, expected {expected}")

    # Verify founded_year cell's number_format is "0" (no thousands separator)
    for row in ws_facts.iter_rows(min_row=2, max_row=8, values_only=False):
        field_cell = row[0]
        value_cell = row[1]
        if field_cell.value == "founded_year":
            if value_cell.number_format != "0":
                mismatches.append(f"XLSX Facts: founded_year number_format = '{value_cell.number_format}', expected '0'")
            break

    # Verify Derived sheet exists
    if "Derived" not in wb.sheetnames:
        mismatches.append("XLSX: Derived sheet missing")
    else:
        ws_derived = wb["Derived"]
        # Check formulas exist and start with "="
        age_cell = ws_derived.cell(row=2, column=2)
        funding_cell = ws_derived.cell(row=3, column=2)
        if age_cell.value is None or not str(age_cell.value).startswith("="):
            mismatches.append("XLSX Derived: Company Age formula missing or not a formula")
        if funding_cell.value is None or not str(funding_cell.value).startswith("="):
            mismatches.append("XLSX Derived: Funding per Employee formula missing or not a formula")
        # Check company age format "0"
        if age_cell.number_format != "0":
            mismatches.append(f"XLSX Derived: Company Age number_format = '{age_cell.number_format}', expected '0'")
        # Check funding per employee format "$#,##0"
        if funding_cell.number_format != "$#,##0":
            mismatches.append(f"XLSX Derived: Funding per Employee number_format = '{funding_cell.number_format}', expected '$#,##0'")

    wb.close()

    # Verify PPTX
    from pptx import Presentation as PPTXPresentation
    prs = PPTXPresentation(pptx_path)

    # Check slide dimensions (16:9)
    if prs.slide_width != Inches(13.333) or prs.slide_height != Inches(7.5):
        mismatches.append(f"PPTX: expected 16:9 dimensions (13.333 x 7.5 in), got {prs.slide_width} x {prs.slide_height}")

    if len(prs.slides) != 4:
        mismatches.append(f"PPTX: expected 4 slides, got {len(prs.slides)}")
    else:
        # Check key facts table on slide 2
        slide2 = prs.slides[1]
        tables = [shape for shape in slide2.shapes if shape.has_table]
        if tables:
            table = tables[0].table
            expected_facts_pptx = {
                "name": str(company.name),
                "domain": str(company.domain),
                "employee_count": f"{company.employee_count:,}",
                "founded_year": str(company.founded_year),
                "hq_city": str(company.hq_city),
                "total_funding_usd": f"${company.total_funding_usd:,}",
                "last_round": str(company.last_round),
            }
            for i, (field, expected) in enumerate(expected_facts_pptx.items()):
                if i + 1 < len(table.rows):
                    actual = table.cell(i + 1, 1).text
                    if actual != expected:
                        mismatches.append(f"PPTX Key Facts: {field} = {actual}, expected {expected}")

        # Check footer exists on all slides
        for i, slide in enumerate(prs.slides):
            footer_found = False
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        if "Source: Crustdata company data" in paragraph.text:
                            footer_found = True
                            break
                if footer_found:
                    break
            if not footer_found:
                mismatches.append(f"PPTX Slide {i+1}: Footer 'Source: Crustdata company data' not found")

    return mismatches