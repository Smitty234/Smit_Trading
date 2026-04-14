"""Fetch 5-day OHLC and pre-market quote for every configured instrument."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import yfinance as yf

from utils import load_yaml, safe_call

log = logging.getLogger("smit.prices")


@dataclass
class PriceSnapshot:
    symbol: str
    name: str
    yf: str
    tick: float
    prior_close: float | None = None
    prior_high: float | None = None
    prior_low: float | None = None
    five_day_high: float | None = None
    five_day_low: float | None = None
    premarket: float | None = None
    atr5: float | None = None
    gap_pct: float | None = None
    sparkline: list[float] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def _atr(df: pd.DataFrame, n: int = 5) -> float | None:
    if len(df) < 2:
        return None
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return float(tr.tail(n).mean())


def _premarket(ticker: str) -> float | None:
    """Try multiple sources for a pre-market price."""
    t = yf.Ticker(ticker)
    info = safe_call(lambda: t.fast_info, {}, f"fast_info {ticker}")
    for key in ("pre_market_price", "preMarketPrice", "last_price"):
        v = info.get(key) if isinstance(info, dict) else getattr(info, key, None)
        if v:
            return float(v)
    # Last-resort: last 1-min bar with prepost
    hist = safe_call(
        lambda: t.history(period="1d", interval="1m", prepost=True),
        pd.DataFrame(),
        f"1m prepost {ticker}",
    )
    if not hist.empty:
        return float(hist["Close"].iloc[-1])
    return None


def snapshot_one(cfg: dict) -> PriceSnapshot:
    snap = PriceSnapshot(
        symbol=cfg["symbol"], name=cfg["name"], yf=cfg["yf"], tick=cfg["tick"]
    )
    df = safe_call(
        lambda: yf.download(
            cfg["yf"], period="10d", interval="1d",
            progress=False, auto_adjust=False, prepost=False,
        ),
        pd.DataFrame(),
        f"download {cfg['yf']}",
    )
    if df.empty:
        snap.error = "no daily bars"
        return snap
    # Handle yfinance's new multi-index columns when single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna().tail(7)
    if len(df) < 2:
        snap.error = "insufficient history"
        return snap

    # Prior day = last completed session
    prior = df.iloc[-1]
    snap.prior_close = float(prior["Close"])
    snap.prior_high = float(prior["High"])
    snap.prior_low = float(prior["Low"])

    last5 = df.tail(5)
    snap.five_day_high = float(last5["High"].max())
    snap.five_day_low = float(last5["Low"].min())
    snap.atr5 = _atr(df.tail(6), 5)
    snap.sparkline = [float(x) for x in last5["Close"].tolist()]
    snap.history = [
        {
            "date": idx.date().isoformat(),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
        }
        for idx, row in last5.iterrows()
    ]

    snap.premarket = _premarket(cfg["yf"])
    if snap.premarket and snap.prior_close:
        snap.gap_pct = (snap.premarket - snap.prior_close) / snap.prior_close * 100

    return snap


def fetch_all() -> dict[str, list[PriceSnapshot]]:
    cfg = load_yaml("tickers.yml")
    return {
        "indices": [snapshot_one(c) for c in cfg["indices"]],
        "mag7": [snapshot_one(c) for c in cfg["mag7"]],
    }


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    data = fetch_all()
    for group, snaps in data.items():
        print(f"== {group} ==")
        for s in snaps:
            print(s)
