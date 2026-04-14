"""Compute actionable short/long trade levels for the index dashboard.

Formula (per approved plan):
  short_trigger = max(5-day high, prior-day high + 0.25 * ATR(5))
  long_trigger  = min(5-day low,  prior-day low  - 0.25 * ATR(5))
  stop          = 0.5 * ATR beyond entry
  target_1R     = stop distance profit target (1R)
  target_2R     = 2 * stop distance profit target (2R)

All numbers rounded to the instrument's native tick so they're readable
and actually tradeable.
"""
from __future__ import annotations

from dataclasses import dataclass

from fetch_prices import PriceSnapshot
from utils import round_to_tick


@dataclass
class TradeLevels:
    symbol: str
    name: str
    premarket: float | None
    short_trigger: float | None
    short_stop: float | None
    short_target_1r: float | None
    short_target_2r: float | None
    long_trigger: float | None
    long_stop: float | None
    long_target_1r: float | None
    long_target_2r: float | None
    dist_to_short_pct: float | None
    dist_to_long_pct: float | None
    note: str = ""


def compute(snap: PriceSnapshot) -> TradeLevels:
    t = TradeLevels(
        symbol=snap.symbol, name=snap.name, premarket=snap.premarket,
        short_trigger=None, short_stop=None,
        short_target_1r=None, short_target_2r=None,
        long_trigger=None, long_stop=None,
        long_target_1r=None, long_target_2r=None,
        dist_to_short_pct=None, dist_to_long_pct=None,
    )
    if snap.error or snap.atr5 is None or snap.prior_high is None:
        t.note = f"levels unavailable: {snap.error or 'missing data'}"
        return t

    tick = snap.tick
    atr = snap.atr5
    buf = 0.25 * atr
    stop_dist = 0.5 * atr

    short = max(snap.five_day_high or 0, snap.prior_high + buf)
    long_ = min(snap.five_day_low or 1e12, snap.prior_low - buf)

    t.short_trigger = round_to_tick(short, tick)
    t.short_stop = round_to_tick(short + stop_dist, tick)
    t.short_target_1r = round_to_tick(short - stop_dist, tick)
    t.short_target_2r = round_to_tick(short - 2 * stop_dist, tick)

    t.long_trigger = round_to_tick(long_, tick)
    t.long_stop = round_to_tick(long_ - stop_dist, tick)
    t.long_target_1r = round_to_tick(long_ + stop_dist, tick)
    t.long_target_2r = round_to_tick(long_ + 2 * stop_dist, tick)

    if snap.premarket:
        t.dist_to_short_pct = (t.short_trigger - snap.premarket) / snap.premarket * 100
        t.dist_to_long_pct = (t.long_trigger - snap.premarket) / snap.premarket * 100

    return t


def compute_all(indices: list[PriceSnapshot]) -> list[TradeLevels]:
    return [compute(s) for s in indices]
