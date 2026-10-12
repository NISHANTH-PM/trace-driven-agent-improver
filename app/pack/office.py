"""Office document rendering (PPTX, XLSX) and verification for pack agent."""

from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, numbers
from pptx import Presentation
from pptx.util import Inches, Pt

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

    # Bold headers
    for cell in ws_facts[1]:
        cell.font = Font(bold=True)

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

    # Number formatting for employee_count and total_funding_usd
    for row in ws_facts.iter_rows(min_row=2, max_row=len(facts_rows) + 1, min_col=2, max_col=2):
        cell = row[0]
        if isinstance(cell.value, int):
            cell.number_format = "#,##0"

    # Auto-fit columns
    for col in ws_facts.columns:
        max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
        ws_facts.column_dimensions[col[0].column_letter].width = max_length + 2

    # Sheet 2: Derived
    ws_derived = wb.create_sheet("Derived")

    # Current year formula for company age
    current_year = datetime.now().year
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

    # Number format for funding per employee (row 3)
    ws_derived[3][1].number_format = "#,##0.00"

    wb.save(path)


def render_pptx(company: CompanyData, sections: dict[str, str], path: Path) -> None:
    """Render company briefing to a PPTX file with 4 slides."""
    prs = Presentation()
    blank_layout = prs.slide_layouts[6]  # Blank layout

    def add_footer(slide):
        footer_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(7.0), Inches(9.0), Inches(0.4)
        )
        tf = footer_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = "Source: Crustdata company data"
        run.font.size = Pt(8)

    # Slide 1: Title
    slide1 = prs.slides.add_slide(blank_layout)
    title_box = slide1.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(1.5))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = company.name
    run.font.size = Pt(32)
    run.font.bold = True
    p2 = tf.add_paragraph()
    run2 = p2.add_run()
    run2.text = "Company briefing"
    run2.font.size = Pt(18)
    add_footer(slide1)

    # Slide 2: Key facts table
    slide2 = prs.slides.add_slide(blank_layout)
    title_box2 = slide2.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.5))
    tf2 = title_box2.text_frame
    p = tf2.paragraphs[0]
    run = p.add_run()
    run.text = "Key facts"
    run.font.size = Pt(24)
    run.font.bold = True

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
    table_shape = slide2.shapes.add_table(rows, cols, Inches(0.5), Inches(1.0), Inches(9), Inches(4.5))
    table = table_shape.table

    # Header row
    table.cell(0, 0).text = "Field"
    table.cell(0, 1).text = "Value"
    for cell in [table.cell(0, 0), table.cell(0, 1)]:
        for paragraph in cell.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(12)

    # Data rows
    for i, (field, value) in enumerate(facts_data):
        table.cell(i + 1, 0).text = field
        table.cell(i + 1, 1).text = value
        for cell in [table.cell(i + 1, 0), table.cell(i + 1, 1)]:
            for paragraph in cell.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(11)

    add_footer(slide2)

    # Slide 3: Overview
    slide3 = prs.slides.add_slide(blank_layout)
    title_box3 = slide3.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.5))
    tf3 = title_box3.text_frame
    p = tf3.paragraphs[0]
    run = p.add_run()
    run.text = "Overview"
    run.font.size = Pt(24)
    run.font.bold = True

    overview_text = _truncate_at_sentence(sections.get("Overview", ""), 600)
    content_box = slide3.shapes.add_textbox(Inches(0.5), Inches(1.0), Inches(9), Inches(5.5))
    tf = content_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = overview_text
    run.font.size = Pt(12)
    add_footer(slide3)

    # Slide 4: Funding and Risks
    slide4 = prs.slides.add_slide(blank_layout)
    title_box4 = slide4.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.5))
    tf4 = title_box4.text_frame
    p = tf4.paragraphs[0]
    run = p.add_run()
    run.text = "Funding and risks"
    run.font.size = Pt(24)
    run.font.bold = True

    funding_text = _truncate_at_sentence(sections.get("Funding", ""), 400)
    risks_text = _truncate_at_sentence(sections.get("Risks", ""), 400)

    combined_text = f"Funding\n{funding_text}\n\nRisks\n{risks_text}"
    content_box4 = slide4.shapes.add_textbox(Inches(0.5), Inches(1.0), Inches(9), Inches(5.5))
    tf = content_box4.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = combined_text
    run.font.size = Pt(12)
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

    # Verify Derived sheet exists
    if "Derived" not in wb.sheetnames:
        mismatches.append("XLSX: Derived sheet missing")
    else:
        ws_derived = wb["Derived"]
        # Check formulas exist
        if ws_derived.cell(row=2, column=2).value is None:
            mismatches.append("XLSX Derived: Company Age formula missing")
        if ws_derived.cell(row=3, column=2).value is None:
            mismatches.append("XLSX Derived: Funding per Employee formula missing")

    wb.close()

    # Verify PPTX
    from pptx import Presentation as PPTXPresentation
    prs = PPTXPresentation(pptx_path)

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

    return mismatches