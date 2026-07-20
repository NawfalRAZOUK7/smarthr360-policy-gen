"""PDF document generation for policy-gen.

Turns the HR data the service already holds (employees, contracts, salaries)
into formal, downloadable documents:

* ``build_contract_pdf`` — an employment contract for one employee.
* ``build_policy_pdf``   — an internal HR policy document from a policy type.

Pure reportlab (no system libraries), returns raw PDF ``bytes`` so views can
stream them straight to the browser.
"""

from __future__ import annotations

import datetime as _dt
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

COMPANY_NAME = "SmartHR360"
_ACCENT = colors.HexColor("#6d5efc")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("DocTitle", parent=ss["Title"], fontSize=20, spaceAfter=4, textColor=_ACCENT))
    ss.add(ParagraphStyle("DocSub", parent=ss["Normal"], fontSize=10, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=14))
    ss.add(ParagraphStyle("H", parent=ss["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#1f2430")))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=10, leading=15))
    ss.add(ParagraphStyle("Small", parent=ss["Normal"], fontSize=8, textColor=colors.grey))
    return ss


def _fmt_date(d) -> str:
    if not d:
        return "—"
    if isinstance(d, (_dt.date, _dt.datetime)):
        return d.strftime("%d %B %Y")
    return str(d)


def _kv_table(rows, styles):
    """A two-column key/value table."""
    data = [[Paragraph(f"<b>{k}</b>", styles["Body"]), Paragraph(str(v), styles["Body"])] for k, v in rows]
    t = Table(data, colWidths=[55 * mm, 105 * mm])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e6e8ef")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def _header(story, title, subtitle, styles):
    story.append(Paragraph(COMPANY_NAME, styles["DocTitle"]))
    story.append(Paragraph(title, styles["H"]))
    story.append(Paragraph(subtitle, styles["DocSub"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=_ACCENT, spaceAfter=10))


def _render(story) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
        title="SmartHR360 document",
    )
    doc.build(story)
    return buf.getvalue()


def build_contract_pdf(employee, contract=None, salary=None, department=None, job_title=None) -> bytes:
    """Employment contract for ``employee``. Contract/salary are optional — when
    absent, reasonable defaults are used so a document is always produced."""
    styles = _styles()
    story = []

    name = f"{employee.first_name} {employee.last_name}".strip()
    today = _dt.date.today()
    _header(story, "Employment Contract", f"Issued {today.strftime('%d %B %Y')}", styles)

    story.append(Paragraph("Parties", styles["H"]))
    story.append(
        Paragraph(
            f"This employment contract is entered into between <b>{COMPANY_NAME}</b> "
            f'("the Employer") and <b>{name}</b> ("the Employee").',
            styles["Body"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("Employee details", styles["H"]))
    story.append(
        _kv_table(
            [
                ("Full name", name),
                ("Employee number", employee.employee_number or "—"),
                ("Email", employee.email or "—"),
                ("Department", getattr(department, "name", None) or "—"),
                ("Job title", getattr(job_title, "name", None) or "—"),
                ("Location", getattr(employee, "location", None) or "—"),
                ("Hire date", _fmt_date(getattr(employee, "hire_date", None))),
            ],
            styles,
        )
    )

    story.append(Paragraph("Contract terms", styles["H"]))
    ctype = (getattr(contract, "contract_type", None) or "Permanent (CDI)")
    hours = getattr(contract, "hours_per_week", None) or "35.00"
    start = _fmt_date(getattr(contract, "start_date", None) or getattr(employee, "hire_date", None) or today)
    end = _fmt_date(getattr(contract, "end_date", None)) if getattr(contract, "end_date", None) else "Open-ended"
    story.append(
        _kv_table(
            [
                ("Contract type", ctype),
                ("Start date", start),
                ("End date", end),
                ("Working hours", f"{hours} hours / week"),
            ],
            styles,
        )
    )

    story.append(Paragraph("Compensation", styles["H"]))
    if salary is not None:
        base = f"{salary.base_amount} {salary.currency}"
        freq = getattr(salary, "pay_frequency", None) or "monthly"
        comp_rows = [("Base salary", f"{base} ({freq})")]
        if getattr(salary, "employer_costs", None):
            comp_rows.append(("Employer cost", f"{salary.employer_costs} {salary.currency}"))
        comp_rows.append(("Effective from", _fmt_date(getattr(salary, "effective_from", None) or start)))
    else:
        comp_rows = [("Base salary", "As agreed in the offer letter"), ("Pay frequency", "Monthly")]
    story.append(_kv_table(comp_rows, styles))

    story.append(Spacer(1, 18))
    story.append(Paragraph("Signatures", styles["H"]))
    sign = Table(
        [
            [Paragraph("For the Employer", styles["Small"]), Paragraph("The Employee", styles["Small"])],
            [Spacer(1, 26), Spacer(1, 26)],
            [
                Paragraph(f"{COMPANY_NAME} — HR Department", styles["Body"]),
                Paragraph(name, styles["Body"]),
            ],
        ],
        colWidths=[80 * mm, 80 * mm],
    )
    sign.setStyle(TableStyle([("LINEABOVE", (0, 2), (-1, 2), 0.6, colors.grey), ("TOPPADDING", (0, 2), (-1, 2), 4)]))
    story.append(sign)

    story.append(Spacer(1, 16))
    story.append(
        Paragraph(
            f"Generated by {COMPANY_NAME} policy-gen · {today.isoformat()} · This is a system-generated draft "
            "for review and is not a substitute for legal advice.",
            styles["Small"],
        )
    )
    return _render(story)


POLICY_TEMPLATES = {
    "remote_work": (
        "Remote Work Policy",
        [
            ("Purpose", "This policy sets the framework under which employees may work remotely, "
                        "balancing flexibility with collaboration and data security."),
            ("Eligibility", "Employees whose role permits remote delivery, subject to manager approval."),
            ("Expectations", "Employees remain reachable during core hours, attend required on-site days, "
                             "and maintain a secure working environment."),
            ("Equipment & security", "Company devices and VPN must be used for all work involving personal data (GDPR)."),
        ],
    ),
    "flexible_hours": (
        "Flexible Working Hours Policy",
        [
            ("Purpose", "Allow employees to vary start/finish times around agreed core hours."),
            ("Core hours", "10:00–16:00, during which all employees are expected to be available."),
            ("Approval", "Flexible schedules are agreed with the line manager and reviewed periodically."),
        ],
    ),
    "training_budget": (
        "Training & Development Budget Policy",
        [
            ("Purpose", "Define how the annual training budget is allocated and claimed."),
            ("Entitlement", "Each employee has an annual development allowance for approved courses and certifications."),
            ("Approval & claims", "Training is approved by the manager and HR; receipts are submitted for reimbursement."),
        ],
    ),
    "wellness_program": (
        "Employee Wellness Programme",
        [
            ("Purpose", "Support the physical and mental wellbeing of employees."),
            ("Provision", "Access to wellbeing resources, periodic check-ins and support services."),
            ("Confidentiality", "Participation and any health information are treated as strictly confidential."),
        ],
    ),
}


def build_policy_pdf(policy_type: str, title: str | None = None, sections=None) -> bytes:
    """Internal HR policy document from a known template or custom sections."""
    styles = _styles()
    story = []
    today = _dt.date.today()

    default_title, default_sections = POLICY_TEMPLATES.get(
        policy_type, (policy_type.replace("_", " ").title() + " Policy", [])
    )
    doc_title = title or default_title
    body_sections = sections or default_sections or [
        ("Purpose", f"This document describes the {doc_title.lower()} for {COMPANY_NAME}."),
    ]

    _header(story, doc_title, f"Internal HR Policy · v1.0 · {today.strftime('%d %B %Y')}", styles)
    for heading, text in body_sections:
        story.append(Paragraph(heading, styles["H"]))
        story.append(Paragraph(text, styles["Body"]))
    story.append(Spacer(1, 18))
    story.append(
        Paragraph(
            f"Approved by {COMPANY_NAME} HR · Effective {today.isoformat()}. "
            "Complies with applicable local labour law and GDPR.",
            styles["Small"],
        )
    )
    return _render(story)
