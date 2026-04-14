"""Orchestrator: build the daily pre-market newsletter.

Usage:
  python scripts/build_newsletter.py          # full run
  python scripts/build_newsletter.py --dry-run  # skip holiday gate
  python scripts/build_newsletter.py --force    # ignore weekend/holiday skip
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow `python scripts/build_newsletter.py` to import siblings.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze
import fetch_insiders
import fetch_news
import fetch_politicians
import fetch_prices
import levels
import render
from utils import now_et, safe_call, should_skip_today, time_until_us_open


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="render even if empty")
    ap.add_argument("--force", action="store_true", help="ignore holiday skip")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("smit.build")

    if should_skip_today() and not args.force and not args.dry_run:
        log.info("Market closed today (weekend/holiday) — skipping build.")
        return 0

    log.info("Fetching prices…")
    prices = safe_call(fetch_prices.fetch_all, {"indices": [], "mag7": []}, "fetch_prices")

    log.info("Computing trade levels…")
    trade_levels = levels.compute_all(prices["indices"])

    log.info("Fetching news…")
    headlines = safe_call(fetch_news.fetch_headlines, [], "fetch_news")
    sentiment = fetch_news.sentiment_summary(headlines)
    calendar = safe_call(fetch_news.fetch_calendar, [], "fetch_calendar")

    log.info("Fetching politician trades…")
    pol_trades_all = safe_call(fetch_politicians.fetch_all, [], "fetch_politicians")
    pol_recent = fetch_politicians.recent(pol_trades_all, days=30)

    log.info("Fetching insider filings…")
    insider_trades = safe_call(fetch_insiders.fetch_recent, [], "fetch_insiders")

    log.info("Deriving smart-money ideas…")
    ideas = analyze.smart_money_ideas(pol_trades_all, insider_trades)

    context = {
        "generated_at_et": now_et().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "generated_date": now_et().date().isoformat(),
        "minutes_to_open": max(0, int(time_until_us_open().total_seconds() // 60)),
        "prices": prices,
        "levels": trade_levels,
        "headlines": headlines,
        "sentiment": sentiment,
        "calendar": calendar,
        "politician_trades": pol_recent[:25],
        "insider_trades": insider_trades[:15],
        "ideas": ideas,
    }

    out = render.render(context)
    log.info("Rendered %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
