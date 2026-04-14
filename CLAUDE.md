# Smit Trading — Project Guide (CLAUDE.md)

Pre-market trading newsletter for NQ / ES / GC and the Magnificent 7, auto-built daily at 09:00 ET and deployed to GitHub Pages.

---

## 1. What this repo does

Every weekday at 09:00 America/New_York (30 minutes before US cash open), a GitHub Action runs `scripts/build_newsletter.py`, which:

1. Pulls 5-day OHLC + pre-market quotes via **yfinance** for:
   - Indices/Futures: **NQ** (Nasdaq-100), **ES** (S&P 500), **GC** (Gold)
   - **MAG 7**: AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA
2. Computes **actionable short/long trade levels** per index (ATR-based).
3. Scrapes **Finviz** for news headlines + today's US economic calendar.
4. Scrapes **CapitolTrades** for recent trades from the tracked politicians.
5. Pulls **SEC EDGAR Form 4** filings (large recent insider transactions).
6. Derives **smart-money long/short candidates** (≥2 tracked politicians on the same ticker within 14 days).
7. Renders `docs/index.html` (+ `docs/archive/YYYY-MM-DD.html`).
8. Commits and pushes. **GitHub Pages** deploys from `main:/docs`.

Public URL: `https://smitty234.github.io/smit_trading/`

---

## 2. Repo layout

```
Smit_Trading/
├── CLAUDE.md                       ← you are here
├── README.md
├── requirements.txt
├── .github/workflows/daily-newsletter.yml
├── config/
│   ├── tickers.yml                 # instruments + tick sizes
│   ├── politicians.yml             # anchor + auto top-5
│   └── holidays.yml                # NYSE holidays to skip
├── scripts/
│   ├── build_newsletter.py         # orchestrator — entry point
│   ├── fetch_prices.py             # yfinance
│   ├── fetch_news.py               # Finviz news + calendar
│   ├── fetch_politicians.py        # CapitolTrades
│   ├── fetch_insiders.py           # SEC EDGAR
│   ├── levels.py                   # trade level math
│   ├── analyze.py                  # smart-money clustering
│   ├── render.py                   # Jinja2 → HTML
│   ├── utils.py                    # fetch/cache/time helpers
│   └── update_top_politicians.py   # weekly Sunday top-5 refresh
├── templates/newsletter.html.j2
├── static/style.css
├── docs/                           # GitHub Pages root
│   ├── index.html
│   ├── style.css                   # copied by render.py
│   └── archive/YYYY-MM-DD.html
└── data/cache/                     # ETag'd HTTP responses
```

---

## 3. How to run locally

```bash
cd Smit_Trading
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Full build:
python scripts/build_newsletter.py

# Build even on weekends/holidays:
python scripts/build_newsletter.py --force

# Dry run (ignores holiday gate):
python scripts/build_newsletter.py --dry-run

# Then open:
open docs/index.html
```

**SEC EDGAR requirement:** Set a real contact email via the env var `SEC_USER_AGENT`. In GitHub, add it as a repo secret (Settings → Secrets and variables → Actions → New secret → `SEC_USER_AGENT`, value like `Smit Trading you@example.com`).

---

## 4. Trade level math (scripts/levels.py)

For each index (NQ, ES, GC):

```
short_trigger = max(5-day high, prior high + 0.25 × ATR5)
long_trigger  = min(5-day low,  prior low  − 0.25 × ATR5)
stop          = 0.5 × ATR5 beyond entry
target_1R     = stop distance in profit
target_2R     = 2× stop distance in profit
```

All values rounded to the instrument's native tick:
- **NQ** → 25 points
- **ES** → 5 points
- **GC** → $5

Rationale: triggers sit just outside the prior range, so we only fire on confirmed breakouts/breakdowns, not noise. ATR(5) gives a recent-volatility-aware buffer; ticks keep the numbers round and actually usable when placing orders.

---

## 5. Politicians tracked

| Role | Name | Bioguide ID | Notes |
|---|---|---|---|
| **Anchor (fixed)** | Nancy Pelosi | P000197 | ~65% 2023 return per Unusual Whales "Pelosi Tracker"; heavy MAG 7 / large-cap tech options |
| Auto top-5 (weekly) | — | — | refreshed every Sunday by `update_top_politicians.py` from CapitolTrades 1-yr leaderboard |

**Smart-money rule**: a ticker becomes a long candidate when ≥2 of the 6 tracked politicians bought it in the last 14 days; short candidate on the sell side. Window and threshold are in `config/politicians.yml → signal`.

**Why this set**: Pelosi is the famous anchor for coverage + MAG 7 relevance. Auto-top-5 keeps the signal fresh — we don't hardcode winners, we let CapitolTrades' 1-year return leaderboard decide each week. The seed list (Ro Khanna, Josh Gottheimer, Dan Crenshaw, Michael McCaul, Tommy Tuberville) has been consistently in the upper ranks historically.

---

## 6. Data sources

| Source | Used for | Key required | Notes |
|---|---|---|---|
| yfinance | prices, pre-market | No | flaky pre-market field; fallback to 1-min prepost bars |
| CapitolTrades | politician trades | No | scraped HTML, 1 req/sec, 6h cache |
| SEC EDGAR (`efts.sec.gov`) | Form 4 insider filings | No (but User-Agent required) | `SEC_USER_AGENT` env var / secret |
| Finviz | news + econ calendar | No | scraped HTML, 15-min cache for news, 30-min for calendar |
| Quiver Quantitative | — | paid | not used in v1 (can add later) |
| Unusual Whales | — | paid | not used in v1 (can add later) |

All HTTP goes through `utils.fetch()` which handles retries (exponential backoff on 429/5xx), optional on-disk cache, and a custom User-Agent. Every section is wrapped in `safe_call()` so one source failing never breaks the whole build — the page renders with "source unavailable" in place of the missing section.

---

## 7. Scheduling

`.github/workflows/daily-newsletter.yml`:
- Two crons: `0 13 * * 1-5` (EDT) and `0 14 * * 1-5` (EST). Whichever isn't currently 09:00 ET no-ops via the "gate" step.
- Weekends skipped by `cron`. Holidays skipped by `utils.should_skip_today()` (reads `config/holidays.yml`).
- Manual trigger: Actions → Daily Newsletter → Run workflow. Tick "force" to ignore the gate.
- Weekly top-5 refresh runs only on Sunday via `update_top_politicians.py` before the build.

---

## 8. Troubleshooting

**Empty price table** → yfinance rate-limited. Re-run after a few minutes. Workflow will just re-publish the previous day if nothing fresh.

**No politician trades** → CapitolTrades layout changed. Update the CSS selectors in `scripts/fetch_politicians.py::_parse_trade_row`. They're isolated there.

**SEC EDGAR 403** → missing/invalid `SEC_USER_AGENT`. Must include contact email per SEC fair-access policy.

**GitHub Pages not updating** → check Settings → Pages → Source is `main`, folder `/docs`. Confirm `.nojekyll` is present (it's created automatically by `render.py`).

**Cron didn't fire** → GitHub Actions cron has ~5–20 min drift under load; the gate accepts hour == 9 ET so a late trigger still runs if it arrives in the 09:xx window. If consistently late, either widen the gate in the workflow or add an earlier cron.

---

## 9. Extending

- **Add a ticker** → edit `config/tickers.yml`. Pick a correct `tick` size. No code change needed.
- **Change signal threshold** → `config/politicians.yml → signal.min_politicians` and `window_days`.
- **Email/Slack delivery** → add a step to the workflow after "Build newsletter" that posts the HTML or a summary. `docs/index.html` is the canonical artifact.
- **Paid APIs (Quiver / Unusual Whales)** → create `scripts/fetch_quiver.py` mirroring `fetch_politicians.py`, store the key in repo secrets, fold the data into `analyze.smart_money_ideas()`.
- **Intraday refresh** → add more crons and gate on `now.minute`. Keep `concurrency.group` to avoid overlap.

## 10. Out of scope (deliberate, for v1)

- Email/SMS/Slack push delivery (pull model only)
- Options flow / dark pool (requires paid APIs)
- Portfolio P&L tracking
- Authentication on the Pages site
- Backtesting of the trade levels

## 11. Disclaimer

All trade ideas and levels are educational. Not financial advice. You are solely responsible for any trade you execute based on this content.
