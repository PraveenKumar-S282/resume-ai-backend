from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.documents import ResumeContent

_FONTS = {
    "Times": ("Times-Roman", "Times-Bold", "Times-Italic"),
    "Helvetica": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique"),
}


def _t(s: str | None) -> str:
    """Escape for ReportLab markup and fold to characters the built-in fonts can draw."""
    return escape((s or "").encode("cp1252", "replace").decode("cp1252"))


def _styles(cfg: dict) -> dict[str, ParagraphStyle]:
    reg, bold, _ = _FONTS.get(cfg["pdf_font"], _FONTS["Helvetica"])
    body = cfg["body_pt"]
    accent = colors.HexColor(cfg["accent"])
    align = TA_CENTER if cfg["align"] == "center" else TA_LEFT
    return {
        "name": ParagraphStyle("name", fontName=bold, fontSize=cfg["name_pt"], leading=cfg["name_pt"] + 3, alignment=align, textColor=accent),
        "sub": ParagraphStyle("sub", fontName=reg, fontSize=body + 1, leading=body + 4, alignment=align),
        "contact": ParagraphStyle("contact", fontName=reg, fontSize=body, leading=body + 3, alignment=align, textColor=colors.HexColor("#475569")),
        "h": ParagraphStyle("h", fontName=bold, fontSize=cfg["heading_pt"], leading=cfg["heading_pt"] + 3, textColor=accent, spaceBefore=cfg["space"] + 4, spaceAfter=1),
        "body": ParagraphStyle("body", fontName=reg, fontSize=body, leading=body + 3.5),
        "bullet": ParagraphStyle("bullet", fontName=reg, fontSize=body, leading=body + 3.5),
        "letter": ParagraphStyle("letter", fontName=reg, fontSize=body + 1, leading=(body + 1) * 1.45, spaceAfter=10),
        "_bold": bold,
    }


def _heading(title: str, st, cfg):
    return [Paragraph(_t(title), st["h"]), HRFlowable(width="100%", thickness=0.8, color=colors.HexColor(cfg["accent"]), spaceAfter=3)]


def _bullets(items: list[str], st):
    if not items:
        return []
    return [ListFlowable(
        [ListItem(Paragraph(_t(b), st["bullet"]), leftIndent=12) for b in items],
        bulletType="bullet", start="•", leftIndent=12, bulletFontSize=7,
    )]


def _row(left_html: str, right: str | None, st, width):
    left = Paragraph(left_html, st["body"])
    r = Paragraph(_t(right), ParagraphStyle("r", parent=st["body"], alignment=2)) if right else Paragraph("", st["body"])
    t = Table([[left, r]], colWidths=[width * 0.76, width * 0.24])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _doc(buf, title):
    return SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm, title=title)


def build_resume_pdf(c: ResumeContent, cfg: dict) -> bytes:
    st = _styles(cfg)
    bold = st["_bold"]
    buf = BytesIO()
    doc = _doc(buf, c.header.name or "Resume")
    width = A4[0] - 4 * cm
    h = c.header

    flow = [Paragraph(_t(h.name or "Your name"), st["name"])]
    if h.headline:
        flow.append(Paragraph(_t(h.headline), st["sub"]))
    contact = [x for x in [h.email, h.phone, h.location, *[(l.label or l.url) for l in h.links]] if x]
    if contact:
        flow.append(Paragraph(_t("  |  ".join(contact)), st["contact"]))

    if c.summary:
        flow += _heading("Summary", st, cfg) + [Paragraph(_t(c.summary), st["body"])]
    if c.skills:
        flow += _heading("Skills", st, cfg)
        flow += [Paragraph(f"<font name='{bold}'>{_t(g.category)}:</font> {_t(', '.join(g.items))}", st["body"]) for g in c.skills]
    if c.experience:
        flow += _heading("Experience", st, cfg)
        for e in c.experience:
            title = f"<font name='{bold}'>{_t(e.role)}</font>" + (f", {_t(e.company)}" if e.company else "") + (f", {_t(e.location)}" if e.location else "")
            flow.append(KeepTogether([_row(title, " to ".join(x for x in (e.start, e.end) if x), st, width), *_bullets(e.bullets, st)]))
    if c.projects:
        flow += _heading("Projects", st, cfg)
        for p in c.projects:
            title = f"<font name='{bold}'>{_t(p.title)}</font>" + (f" ({_t(', '.join(p.tech))})" if p.tech else "")
            flow.append(KeepTogether([_row(title, None, st, width), *_bullets(p.bullets, st)]))
    if c.education:
        flow += _heading("Education", st, cfg)
        for ed in c.education:
            title = f"<font name='{bold}'>{_t(ed.institution)}</font>" + (f", {_t(ed.degree)}" if ed.degree else "") + (f" ({_t(ed.grade)})" if ed.grade else "")
            flow.append(_row(title, ed.dates, st, width))
    if c.certifications:
        flow += _heading("Certifications", st, cfg)
        for ct in c.certifications:
            flow.append(Paragraph(_t(ct.name + (f", {ct.issuer}" if ct.issuer else "") + (f" ({ct.date})" if ct.date else "")), st["body"]))

    doc.build(flow)
    return buf.getvalue()


def build_cover_letter_pdf(text: str, cfg: dict) -> bytes:
    st = _styles(cfg)
    buf = BytesIO()
    doc = _doc(buf, "Cover letter")
    flow = []
    for para in [p for p in text.split("\n\n") if p.strip()]:
        flow.append(Paragraph("<br/>".join(_t(line) for line in para.split("\n")), st["letter"]))
        flow.append(Spacer(1, 2))
    doc.build(flow)
    return buf.getvalue()
