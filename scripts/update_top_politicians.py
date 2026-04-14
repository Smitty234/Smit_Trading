"""Weekly refresh of the top-5 politicians list from CapitolTrades.

Scrapes the leaderboard sorted by 1-year performance, keeps the top 5
(excluding the anchor Pelosi), and rewrites config/politicians.yml.

Intended to run on a weekly cron (Sunday); invoked separately from the
daily build so it doesn't slow the pre-market critical path.
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import CONFIG_DIR, fetch  # noqa: E402

log = logging.getLogger("smit.top")

LEADERBOARD = "https://www.capitoltrades.com/politicians"
ID_RE = re.compile(r"/politicians/([A-Z]\d{6})")


def fetch_top5() -> list[dict]:
    html = fetch(LEADERBOARD, params={"sortBy": "performance_1y_desc"}, cache_ttl=0)
    soup = BeautifulSoup(html, "lxml")
    top: list[dict] = []
    for row in soup.select("tbody tr"):
        link = row.select_one("a[href^='/politicians/']")
        if not link:
            continue
        m = ID_RE.search(link.get("href", ""))
        if not m:
            continue
        pol_id = m.group(1)
        if pol_id == "P000197":  # anchor (Pelosi)
            continue
        name = link.get_text(strip=True)
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        party = "D" if "Democrat" in " ".join(cells) else (
            "R" if "Republican" in " ".join(cells) else ""
        )
        chamber = "Senate" if "Senate" in " ".join(cells) else "House"
        top.append({
            "name": name,
            "capitoltrades_id": pol_id,
            "chamber": chamber,
            "party": party,
            "state": "",
        })
        if len(top) >= 5:
            break
    return top


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    cfg_path = CONFIG_DIR / "politicians.yml"
    cfg = yaml.safe_load(cfg_path.read_text())
    new_top = fetch_top5()
    if not new_top:
        log.warning("No top-5 parsed; leaving existing list untouched.")
        return 1
    cfg["top5_auto"] = new_top
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    log.info("Updated top 5: %s", [p["name"] for p in new_top])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
