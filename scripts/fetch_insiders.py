"""Fetch large recent Form 4 (insider) transactions from SEC EDGAR.

Uses the free full-text search API. No key required, but a real
User-Agent including contact info is mandatory per SEC policy.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta

from utils import fetch, safe_call

log = logging.getLogger("smit.insiders")

EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"


@dataclass
class InsiderTrade:
    filer: str
    ticker: str
    company: str
    form: str
    date_filed: str
    link: str


def fetch_recent(days: int = 7, limit: int = 20) -> list[InsiderTrade]:
    since = (date.today() - timedelta(days=days)).isoformat()
    body = safe_call(
        lambda: fetch(
            EDGAR_SEARCH,
            params={
                "q": '"insider"',
                "dateRange": "custom",
                "startdt": since,
                "enddt": date.today().isoformat(),
                "forms": "4",
            },
            headers={"Accept": "application/json"},
            cache_ttl=3600,
            sec=True,
        ),
        "",
        "EDGAR search",
    )
    if not body:
        return []
    try:
        data = json.loads(body)
    except Exception:
        return []
    hits = (data.get("hits") or {}).get("hits") or []
    out: list[InsiderTrade] = []
    for h in hits[:limit]:
        src = h.get("_source") or {}
        out.append(InsiderTrade(
            filer=src.get("display_names", [""])[0] if src.get("display_names") else "",
            ticker=(src.get("tickers") or [""])[0],
            company=(src.get("display_names") or [""])[0],
            form=src.get("form", "4"),
            date_filed=src.get("file_date", ""),
            link=f"https://www.sec.gov/Archives/edgar/data/{src.get('ciks', [''])[0]}/"
                 f"{h.get('_id', '').replace(':', '/')}"
            if src.get("ciks") else "",
        ))
    return out
