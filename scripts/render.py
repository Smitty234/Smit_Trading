"""Render Jinja2 template to docs/index.html and docs/archive/YYYY-MM-DD.html."""
from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from utils import ROOT, fmt_money, fmt_num, now_et

TPL_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUT_DIR = ROOT / "docs"
ARCHIVE_DIR = OUT_DIR / "archive"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TPL_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True, lstrip_blocks=True,
    )
    env.filters["money"] = fmt_money
    env.filters["num"] = fmt_num
    def signed(v, d=2):
        if v is None:
            return "—"
        return f"{'+' if v >= 0 else ''}{v:,.{d}f}"
    env.filters["signed"] = signed
    return env


def render(context: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / ".nojekyll").touch(exist_ok=True)

    css_src = STATIC_DIR / "style.css"
    if css_src.exists():
        shutil.copy2(css_src, OUT_DIR / "style.css")

    env = _env()
    tpl = env.get_template("newsletter.html.j2")
    html = tpl.render(**context)

    index = OUT_DIR / "index.html"
    index.write_text(html, encoding="utf-8")

    dated = ARCHIVE_DIR / f"{now_et().date().isoformat()}.html"
    dated.write_text(html, encoding="utf-8")
    return index
