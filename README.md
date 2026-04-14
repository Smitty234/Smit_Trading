# Smit Trading

Daily pre-market trading brief for USA Tech 100 (NQ), S&P 500 (ES), Gold (GC), and the Magnificent 7.

Auto-generated 30 minutes before US cash open (09:00 America/New_York), deployed to GitHub Pages.

**Live page:** https://smitty234.github.io/smit_trading/

## What's on the page

- 5-day highs & lows, prior close, pre-market quote, gap %, ATR(5) for every tracked instrument
- **Actionable trade levels** for NQ / ES / GC (short above X, long below Y, with stops + targets)
- Market sentiment from Finviz headlines
- Today's US economic calendar
- Tracked politician trades (Nancy Pelosi + auto-refreshed top 5 from CapitolTrades)
- Large SEC Form 4 insider filings (last 7 days)
- Smart-money long/short candidates (cluster detection)

## Quick start (local)

```bash
pip install -r requirements.txt
python scripts/build_newsletter.py --force   # --force ignores weekend/holiday gate
open docs/index.html
```

Set `SEC_USER_AGENT="Your Name you@example.com"` for SEC EDGAR fair-access compliance.

## Project guide

See [`CLAUDE.md`](CLAUDE.md) for architecture, extending, and troubleshooting.

## Disclaimer

Educational content only. Not financial advice.
