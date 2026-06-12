"""
routers/reports.py
All report/export logic extracted from main.py.

Endpoints:
  GET /generate-report          – PDF download (original URL kept for compatibility)
  GET /api/documents/pdf        – PDF alias
  GET /api/documents/excel      – XLSX download
  GET /api/documents/word       – DOCX download
"""

import io
import zipfile
from html import escape

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import graph_engine
import models
from database import get_db

router = APIRouter(tags=["Reporting"])


# ── Internal helpers ───────────────────────────────────────────────────────────

def _resource_rows(db: Session) -> list[list[str]]:
    rows = [["Resource ID", "Name", "Type", "Provider", "Region", "Sensitivity", "Public", "Cost", "Risk Score", "Status"]]
    for resource in db.query(models.CloudResource).order_by(models.CloudResource.resource_uid).all():
        rows.append([
            resource.resource_uid,
            resource.name,
            resource.resource_type,
            resource.provider or "",
            resource.region or "",
            resource.sensitivity or "",
            "Yes" if resource.public_access else "No",
            f"{resource.cost or 0:.2f}",
            f"{resource.risk_score or 0:.1f}",
            resource.status or "",
        ])
    return rows


def _connection_rows(db: Session) -> list[list[str]]:
    rows = [["From", "To", "Type", "Risk Weight", "Created"]]
    for connection in db.query(models.ResourceConnection).all():
        rows.append([
            connection.from_node,
            connection.to_node,
            connection.connection_type or "",
            str(connection.risk_weight or 0),
            connection.created_at.isoformat() if connection.created_at else "",
        ])
    return rows


def _xlsx_col(col_index: int) -> str:
    """Convert 1-based column index to Excel column letter(s) — supports > 26 columns."""
    result = ""
    while col_index > 0:
        col_index, remainder = divmod(col_index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _xlsx_sheet(rows: list[list[str]], sheet_id: int) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            col = _xlsx_col(col_index)   # Fixed: was chr(64 + col_index), broke at col 27
            cells.append(
                f'<c r="{col}{row_index}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
            )
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        '</worksheet>'
    )


def _build_xlsx(db: Session) -> io.BytesIO:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        ))
        archive.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        ))
        archive.writestr("xl/workbook.xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets>'
            '<sheet name="Resources" sheetId="1" r:id="rId1"/>'
            '<sheet name="Connections" sheetId="2" r:id="rId2"/>'
            '</sheets></workbook>'
        ))
        archive.writestr("xl/_rels/workbook.xml.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            '</Relationships>'
        ))
        archive.writestr("xl/worksheets/sheet1.xml", _xlsx_sheet(_resource_rows(db), 1))
        archive.writestr("xl/worksheets/sheet2.xml", _xlsx_sheet(_connection_rows(db), 2))
    output.seek(0)
    return output


def _build_docx(db: Session) -> io.BytesIO:
    resources = db.query(models.CloudResource).order_by(models.CloudResource.resource_uid).all()
    connections = db.query(models.ResourceConnection).all()
    total_cost = sum(resource.cost or 0 for resource in resources)
    high_risk = sum(1 for resource in resources if (resource.risk_score or 0) >= 70)

    paragraphs = [
        "Cloud Risk Intelligence Report",
        f"Resources: {len(resources)}",
        f"Connections: {len(connections)}",
        f"High-risk resources: {high_risk}",
        f"Total monthly cost: ${total_cost:,.2f}",
        "Top resources:",
    ]
    paragraphs.extend(
        f"{resource.resource_uid} - {resource.name} - {resource.resource_type} - risk {resource.risk_score or 0:.1f}"
        for resource in sorted(resources, key=lambda item: item.risk_score or 0, reverse=True)[:20]
    )
    body = "".join(f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>" for text in paragraphs)

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        ))
        archive.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>'
        ))
        archive.writestr("word/document.xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body}</w:body></w:document>"
        ))
    output.seek(0)
    return output


def _build_pdf(db: Session) -> io.BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    resources = db.query(models.CloudResource).order_by(models.CloudResource.resource_uid).all()
    total_cost = sum(resource.cost or 0 for resource in resources)
    high_risk = sum(1 for resource in resources if graph_engine._risk_level(resource.risk_score or 0) == "High")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Cloud Risk Intelligence Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph("Executive Summary", styles["Heading2"]),
        Paragraph(f"Total Nodes: {len(resources)}", styles["Normal"]),
        Paragraph(f"Total Cloud Cost: ${total_cost:,.2f} / month", styles["Normal"]),
        Paragraph(f"High Risk Nodes: {high_risk}", styles["Normal"]),
        Spacer(1, 12),
    ]

    table_data = [["Resource ID", "Name", "Type", "Risk Score", "Level", "Cost"]]
    all_resources = sorted(resources, key=lambda item: item.risk_score or 0, reverse=True)
    shown = all_resources[:50]
    for resource in shown:
        table_data.append([
            resource.resource_uid,
            resource.name[:20],
            resource.resource_type,
            f"{resource.risk_score or 0:.1f}",
            graph_engine._risk_level(resource.risk_score or 0),
            f"${resource.cost or 0:.2f}",
        ])

    if len(table_data) > 1:
        if len(all_resources) > 50:
            table_data.append([f"... and {len(all_resources) - 50} more resources", "", "", "", "", ""])
        table = Table(table_data, colWidths=[90, 120, 80, 80, 70, 80])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#d1d5db")),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No cloud resources found in inventory.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ── Route handlers ─────────────────────────────────────────────────────────────

@router.get("/generate-report")
@router.get("/api/documents/pdf")
def generate_report(db: Session = Depends(get_db)):
    """Generate and download a PDF risk report."""
    buffer = _build_pdf(db)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=cloud_risk_report.pdf"},
    )


@router.get("/api/documents/excel")
def document_excel(db: Session = Depends(get_db)):
    """Download XLSX export of resources and connections."""
    return StreamingResponse(
        _build_xlsx(db),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=cloud_risk_inventory.xlsx"},
    )


@router.get("/api/documents/word")
def document_word(db: Session = Depends(get_db)):
    """Download DOCX report."""
    return StreamingResponse(
        _build_docx(db),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=cloud_risk_report.docx"},
    )
