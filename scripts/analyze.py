"""Derive smart-money long/short trade ideas from politician + insider data."""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from fetch_insiders import InsiderTrade
from fetch_politicians import PoliticianTrade
from utils import load_yaml

log = logging.getLogger("smit.analyze")


@dataclass
class SmartMoneyIdea:
    ticker: str
    direction: str           # "long" | "short"
    politicians: list[str] = field(default_factory=list)
    politician_trades: list[PoliticianTrade] = field(default_factory=list)
    insider_trades: list[InsiderTrade] = field(default_factory=list)
    rationale: str = ""
    score: int = 0


def _cluster(trades: list[PoliticianTrade], window_days: int):
    cutoff = (date.today() - timedelta(days=window_days)).isoformat()
    buys: dict[str, list[PoliticianTrade]] = defaultdict(list)
    sells: dict[str, list[PoliticianTrade]] = defaultdict(list)
    for t in trades:
        d = t.trade_date or t.published_date
        if not t.ticker or d < cutoff:
            continue
        (buys if t.side == "buy" else sells if t.side == "sell" else buys)[t.ticker].append(t)
    return buys, sells


def smart_money_ideas(
    politician_trades: list[PoliticianTrade],
    insiders: list[InsiderTrade],
) -> dict[str, list[SmartMoneyIdea]]:
    cfg = load_yaml("politicians.yml")["signal"]
    min_pols = cfg["min_politicians"]
    window = cfg["window_days"]
    buys, sells = _cluster(politician_trades, window)

    def make(tkr: str, direction: str, pts: list[PoliticianTrade]) -> SmartMoneyIdea:
        names = sorted({p.politician for p in pts})
        rationale = (
            f"{len(names)} tracked politicians {direction}-sided {tkr} in the last "
            f"{window} days: {', '.join(names)}."
        )
        return SmartMoneyIdea(
            ticker=tkr, direction=direction, politicians=names,
            politician_trades=pts, rationale=rationale, score=len(names),
        )

    longs = [make(t, "long", pts) for t, pts in buys.items()
             if len({p.politician for p in pts}) >= min_pols]
    shorts = [make(t, "short", pts) for t, pts in sells.items()
              if len({p.politician for p in pts}) >= min_pols]

    # Fold in insider clusters (≥3 insider filings for same ticker in window)
    ins_by_ticker: dict[str, list[InsiderTrade]] = defaultdict(list)
    for i in insiders:
        if i.ticker:
            ins_by_ticker[i.ticker.upper()].append(i)
    for tkr, entries in ins_by_ticker.items():
        if len(entries) < 3:
            continue
        found = next((l for l in longs if l.ticker.upper() == tkr), None)
        if found:
            found.insider_trades = entries
            found.score += 1
            found.rationale += f" Also {len(entries)} recent SEC Form 4 filings."
        else:
            longs.append(SmartMoneyIdea(
                ticker=tkr, direction="long", insider_trades=entries,
                rationale=f"{len(entries)} recent insider filings (SEC Form 4) in {window}d.",
                score=1,
            ))

    longs.sort(key=lambda i: i.score, reverse=True)
    shorts.sort(key=lambda i: i.score, reverse=True)
    return {"long": longs[:5], "short": shorts[:5]}
