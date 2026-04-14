"""Fetch Finviz news and economic calendar, with keyword sentiment tally."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from utils import fetch, safe_call

log = logging.getLogger("smit.news")

FINVIZ_NEWS = "https://finviz.com/news.ashx"
FINVIZ_CAL = "https://finviz.com/calendar.ashx"

POSITIVE = re.compile(
    r"\b(beat|beats|surge|jump|rally|soar|upgrade|record|strong|growth|gains?|bullish)\b",
    re.I,
)
NEGATIVE = re.compile(
    r"\b(miss|fall|drop|plunge|slump|downgrade|weak|layoffs?|probe|fraud|bearish|lawsuit|warn)\b",
    re.I,
)
RELEVANT = re.compile(
    r"\b(fed|cpi|ppi|jobs|payroll|futures|nasdaq|s&p|gold|nvidia|apple|msft|meta|tesla|amazon|google|mag\s?7)\b",
    re.I,
)


@dataclass
class Headline:
    time: str
    title: str
    url: str
    source: str
    sentiment: int  # +1, 0, -1


def _score(title: str) -> int:
    p = bool(POSITIVE.search(title))
    n = bool(NEGATIVE.search(title))
    if p and not n:
        return 1
    if n and not p:
        return -1
    return 0


def fetch_headlines(limit: int = 25) -> list[Headline]:
    html = safe_call(
        lambda: fetch(FINVIZ_NEWS, cache_ttl=900),
        "",
        "finviz news",
    )
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: list[Headline] = []
    for row in soup.select("tr.nn"):
        tds = row.find_all("td")
        if len(tds) < 2:
            continue
        time_cell = tds[0].get_text(strip=True)
        a = tds[1].find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        if not RELEVANT.search(title):
            continue
        url = a.get("href", "")
        src_span = tds[1].find("span")
        source = src_span.get_text(strip=True).strip("()") if src_span else ""
        out.append(Headline(time_cell, title, url, source, _score(title)))
        if len(out) >= limit:
            break
    return out


def fetch_calendar() -> list[dict]:
    """High-impact US econ events for today."""
    html = safe_call(
        lambda: fetch(FINVIZ_CAL, cache_ttl=1800),
        "",
        "finviz calendar",
    )
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for row in soup.select("tr.calendar-impact-3, tr.calendar-impact-2"):
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cells) >= 3:
            out.append({
                "time": cells[0] if cells else "",
                "release": cells[2] if len(cells) > 2 else cells[-1],
                "impact": "high" if "impact-3" in (row.get("class") or []) else "medium",
            })
    return out[:15]


def sentiment_summary(headlines: list[Headline]) -> dict:
    pos = sum(1 for h in headlines if h.sentiment > 0)
    neg = sum(1 for h in headlines if h.sentiment < 0)
    neutral = len(headlines) - pos - neg
    tone = "neutral"
    if pos > neg * 1.5:
        tone = "bullish"
    elif neg > pos * 1.5:
        tone = "bearish"
    return {"positive": pos, "negative": neg, "neutral": neutral, "tone": tone}
