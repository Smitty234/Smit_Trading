"""Scrape recent trades for tracked politicians from CapitolTrades.

Public site, no API key. We throttle to 1 req/sec and cache for 6 hours
so we're a good citizen. Each trade is normalised into a PoliticianTrade.
"""
from __future__ import annotations

import logging
import re
import time as time_mod
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from utils import fetch, load_yaml, safe_call

log = logging.getLogger("smit.pols")

CT_BASE = "https://www.capitoltrades.com"


@dataclass
class PoliticianTrade:
    politician: str
    party: str
    chamber: str
    ticker: str
    company: str
    trade_date: str          # YYYY-MM-DD
    published_date: str
    side: str                # "buy" | "sell"
    size: str                # reported size bucket, e.g. "$1K–$15K"
    url: str


_SIZE_RE = re.compile(r"\$[\d,]+[KMB]?")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _parse_trade_row(tr, pol_name: str, party: str, chamber: str) -> PoliticianTrade | None:
    cells = tr.find_all("td")
    if len(cells) < 5:
        return None
    text = tr.get_text(" ", strip=True)

    # Ticker + company
    tkr_el = tr.select_one("span.q-field.issuer-ticker, h3.q-field.issuer-name a")
    ticker = tkr_el.get_text(strip=True) if tkr_el else ""
    company_el = tr.select_one("h3.q-field.issuer-name")
    company = company_el.get_text(" ", strip=True) if company_el else ""

    # Dates
    dates = _DATE_RE.findall(text)
    trade_date = dates[0] if dates else ""
    pub_date = dates[1] if len(dates) > 1 else trade_date

    # Side
    side_el = tr.select_one("span.q-field.tx-type")
    side_txt = (side_el.get_text(strip=True) if side_el else "").lower()
    if "buy" in side_txt or "purchase" in side_txt:
        side = "buy"
    elif "sell" in side_txt or "sale" in side_txt:
        side = "sell"
    else:
        side = side_txt or "unknown"

    # Size
    size_match = _SIZE_RE.findall(text)
    size = size_match[-1] if size_match else ""

    link = tr.select_one("a[href*='/trades/']")
    url = CT_BASE + link["href"] if link and link.get("href", "").startswith("/") else ""

    return PoliticianTrade(
        politician=pol_name, party=party, chamber=chamber,
        ticker=ticker, company=company,
        trade_date=trade_date, published_date=pub_date,
        side=side, size=size, url=url,
    )


def _fetch_politician_trades(pol_id: str, pol_name: str, party: str, chamber: str,
                             pages: int = 1) -> list[PoliticianTrade]:
    trades: list[PoliticianTrade] = []
    for page in range(1, pages + 1):
        url = f"{CT_BASE}/trades"
        html = safe_call(
            lambda: fetch(
                url,
                params={"politician": pol_id, "page": page, "pageSize": "50"},
                cache_ttl=6 * 3600,
            ),
            "",
            f"CT trades {pol_name} p{page}",
        )
        if not html:
            break
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("tbody tr")
        for tr in rows:
            t = _parse_trade_row(tr, pol_name, party, chamber)
            if t and t.ticker:
                trades.append(t)
        time_mod.sleep(1.0)  # be polite
    return trades


def fetch_all() -> list[PoliticianTrade]:
    cfg = load_yaml("politicians.yml")
    tracked = [cfg["anchor"]] + cfg.get("top5_auto", [])
    out: list[PoliticianTrade] = []
    for p in tracked:
        out.extend(_fetch_politician_trades(
            p["capitoltrades_id"], p["name"],
            p.get("party", ""), p.get("chamber", ""),
        ))
    return out


def recent(trades: list[PoliticianTrade], days: int = 30) -> list[PoliticianTrade]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    keep = []
    for t in trades:
        d = t.trade_date or t.published_date
        if d >= cutoff:
            keep.append(t)
    keep.sort(key=lambda x: x.trade_date or x.published_date, reverse=True)
    return keep
