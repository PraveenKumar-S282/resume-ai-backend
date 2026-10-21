"""Template definitions shared by the database seed, DOCX builder and PDF builder."""

TEMPLATE_DEFS = [
    {
        "key": "classic", "name": "Classic",
        "description": "Serif type, centred header. Traditional and easy to scan.",
        "config": {"docx_font": "Times New Roman", "pdf_font": "Times", "accent": "#111827", "align": "center", "body_pt": 10.5, "heading_pt": 11.5, "name_pt": 20, "space": 6},
    },
    {
        "key": "modern", "name": "Modern",
        "description": "Sans-serif with a coloured accent. Clean and current.",
        "config": {"docx_font": "Calibri", "pdf_font": "Helvetica", "accent": "#3730A3", "align": "left", "body_pt": 10, "heading_pt": 11.5, "name_pt": 22, "space": 6},
    },
    {
        "key": "compact", "name": "Compact",
        "description": "Tighter spacing for fitting more onto one page.",
        "config": {"docx_font": "Calibri", "pdf_font": "Helvetica", "accent": "#334155", "align": "left", "body_pt": 9, "heading_pt": 10, "name_pt": 17, "space": 3},
    },
]


def config_for(template_key: str, db_config: dict | None = None) -> dict:
    if db_config:
        return db_config
    for t in TEMPLATE_DEFS:
        if t["key"] == template_key:
            return t["config"]
    return TEMPLATE_DEFS[0]["config"]
