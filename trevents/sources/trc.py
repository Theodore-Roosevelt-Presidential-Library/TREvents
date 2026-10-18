"""Theodore Roosevelt Center (Dickinson State University) — theodorerooseveltcenter.org/events.

There is no calendar feed: upcoming events are written as headed text blocks under
"Other Upcoming Events". Dates are read out of the prose, so these records are flagged
`date_from_text` for review.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from ..http import get
from ..model import Event, Venue, at, clean_text, guess_attendance, guess_cost, nearest_year, parse_clock

SOURCE = {
    "id": "trc",
    "name": "Theodore Roosevelt Center at Dickinson State University",
    "short": "TR Center",
    "url": "https://www.theodorerooseveltcenter.org/events/",
    "type": "core",
    "region": "Dickinson, ND",
}
TZ = "America/Denver"
M = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
DATE_RX = re.compile(M + r"\.?\s+(\d{1,2})(?:\s*[-–]\s*(?:" + M + r"\s+)?(\d{1,2}))?(?:,\s*(\d{4}))?", re.I)
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def fetch() -> list[Event]:
    soup = BeautifulSoup(get(SOURCE["url"]).text, "lxml")
    marker = None
    for h2 in soup.find_all("h2"):
        if "upcoming events" in h2.get_text(" ", strip=True).lower():
            marker = h2
            break
    if not marker:
        return []
    events = []
    today = date.today()
    for block in marker.find_all_next("div", class_="full-width-text"):
        h3s = block.find_all("h3")
        if not h3s:
            continue
        title = h3s[0].get_text(" ", strip=True)
        link = None
        for a in block.find_all("a", href=True):
            if "theodorerooseveltcenter.org" in a["href"] or a["href"].startswith("/"):
                link = a["href"]
                break
        img = block.find("img")
        text = clean_text(" ".join(str(p) for p in block.find_all("p")))
        m = DATE_RX.search(text)
        if not m:
            continue
        mon = MONTHS.index(m.group(1).lower()) + 1
        d0n = int(m.group(2))
        year = int(m.group(5)) if m.group(5) else nearest_year(mon, d0n)
        d0 = date(year, mon, d0n)
        d1 = d0
        if m.group(4):
            mon1 = MONTHS.index(m.group(3).lower()) + 1 if m.group(3) else mon
            d1 = date(year + (1 if mon1 < mon else 0), mon1, int(m.group(4)))
        if d1 < today:
            continue
        tm = re.search(r"\b(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)", text, re.I)
        t0 = parse_clock(tm.group(1)) if tm else None
        cost, pmin, pmax, note = guess_cost(text)
        events.append(Event(
            source="trc", source_event_id=re.sub(r"\W+", "-", title.lower()).strip("-"), title=title,
            start=at(d0, t0, TZ), end=at(d1, None, TZ) if d1 > d0 else None, all_day=t0 is None, timezone=TZ,
            url=link or SOURCE["url"], description=text, image=img.get("src") if img else None,
            attendance=guess_attendance(text, True), cost=cost, cost_note=note, price_min=pmin, price_max=pmax,
            venue=Venue(city="Dickinson", region="ND"),
            organizer=SOURCE["name"], kind="event", extra={"date_from_text": True},
        ))
    return events
