"""Shared helpers: HTTP with retry/cache, date/tz helpers, config loading."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytz
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
CACHE_DIR = ROOT / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

ET = pytz.timezone("America/New_York")
UTC = pytz.UTC

USER_AGENT = os.environ.get(
    "SMIT_USER_AGENT",
    "Smit_Trading/1.0 (+https://github.com/smitty234/smit_trading)",
)
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "Smit_Trading research contact@example.com",
)

log = logging.getLogger("smit")


def load_yaml(name: str) -> dict:
    with (CONFIG_DIR / name).open() as f:
        return yaml.safe_load(f)


def now_et() -> datetime:
    return datetime.now(ET)


def today_et() -> date:
    return now_et().date()


def is_market_holiday(d: date | None = None) -> bool:
    d = d or today_et()
    holidays = load_yaml("holidays.yml")["holidays"]
    return d.isoformat() in holidays


def is_weekend(d: date | None = None) -> bool:
    d = d or today_et()
    return d.weekday() >= 5


def should_skip_today() -> bool:
    return is_weekend() or is_market_holiday()


def _cache_path(url: str, params: dict | None = None) -> Path:
    key = url + "?" + json.dumps(params or {}, sort_keys=True)
    h = hashlib.sha1(key.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{h}.json"


def fetch(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    cache_ttl: int = 0,
    max_retries: int = 4,
    timeout: int = 20,
    sec: bool = False,
) -> str:
    """GET with exponential backoff and optional on-disk cache (TTL in seconds).

    Returns response body text. Raises on persistent failure.
    """
    hdrs = {"User-Agent": SEC_USER_AGENT if sec else USER_AGENT}
    if headers:
        hdrs.update(headers)

    cp = _cache_path(url, params)
    if cache_ttl and cp.exists():
        age = time.time() - cp.stat().st_mtime
        if age < cache_ttl:
            try:
                return json.loads(cp.read_text())["body"]
            except Exception:  # corrupt cache → refetch
                pass

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, headers=hdrs, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"{r.status_code}")
            r.raise_for_status()
            body = r.text
            if cache_ttl:
                cp.write_text(json.dumps({"body": body, "fetched": time.time()}))
            return body
        except Exception as e:  # pragma: no cover
            last_err = e
            wait = 2 ** attempt
            log.warning("fetch %s failed (%s), retrying in %ds", url, e, wait)
            time.sleep(wait)
    raise RuntimeError(f"fetch {url} failed after {max_retries} attempts: {last_err}")


def safe_call(fn, default: Any, label: str) -> Any:
    """Run fn(); on any exception log and return default. Keeps the build resilient."""
    try:
        return fn()
    except Exception as e:
        log.error("%s failed: %s", label, e)
        return default


def round_to_tick(value: float, tick: float) -> float:
    return round(round(value / tick) * tick, 2)


def fmt_money(v: float | None) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:.1f}k"
    return f"${v:,.2f}"


def fmt_num(v: float | None, decimals: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:,.{decimals}f}"


def time_until_us_open() -> timedelta:
    n = now_et()
    open_t = n.replace(hour=9, minute=30, second=0, microsecond=0)
    if n >= open_t:
        # already open or past — next session
        nd = n + timedelta(days=1)
        open_t = ET.localize(datetime(nd.year, nd.month, nd.day, 9, 30))
    return open_t - n
