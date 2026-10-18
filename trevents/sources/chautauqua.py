"""Badlands Chautauqua: A Gathering of Teddys — medora.com/chautauqua/ (Theodore Roosevelt Medora Foundation).

A single annual event page that gets refreshed each year. The headline date range
("July 17-19, 2026") becomes one multi-day event; the day-by-day program is kept in `extra`.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..http import get
from ..model import Event, Venue, at

SOURCE = {
    "id": "chautauqua",
    "name": "Badlands Chautauqua (Theodore Roosevelt Medora Foundation)",
    "short": "Badlands Chautauqua",
    "url": "https://medora.com/chautauqua/",
    "type": "core",
    "region": "Medora, ND",
}
TZ = "America/Denver"
M = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
RNG = re.compile(M + r"\s+(\d{1,2})\s*[-–]\s*(?:" + M + r"\s+)?(\d{1,2}),\s*(\d{4})")


def fetch() -> list[Event]:
    soup = BeautifulSoup(get(SOURCE["url"]).text, "lxml")
    for t in soup(["script", "style", "svg", "noscript", "nav", "footer", "header"]):
        t.decompose()
    main = soup.find("main") or soup.body
    lines = [l.strip() for l in main.get_text("\n").split("\n") if l.strip()]
    text = "\n".join(lines)
    m = RNG.search(text)
    if not m:
        return []
    y = int(m.group(5))
    d0 = datetime.strptime(f"{m.group(1)} {m.group(2)} {y}", "%B %d %Y").date()
    d1 = datetime.strptime(f"{m.group(3) or m.group(1)} {m.group(4)} {y}", "%B %d %Y").date()
    if d1 < date.today():
        return []  # last year's page; the new dates appear when the page is refreshed
    title_line = next((l for l in lines if "chautauqua" in l.lower()), "Badlands Chautauqua")
    sub = next((l for l in lines[:6] if "gathering" in l.lower()), "")
    title = "Badlands Chautauqua: A Gathering of Teddys" if "gathering of teddys" in (title_line + sub).lower() else title_line.rstrip(":")
    intro = " ".join(l for l in lines[1:8] if len(l) > 60)[:900]
    days = {}
    cur = None
    for l in lines:
        if l in ("FRIDAY", "SATURDAY", "SUNDAY", "THURSDAY", "MONDAY"):
            cur = l.title()
            days[cur] = []
        elif cur and re.match(r"\d{1,2}(:\d{2})?\s*(AM|PM)?\s*[–-]", l):
            days[cur].append(l)
        elif l.lower().startswith("special guests"):
            cur = None
    img = soup.find("meta", property="og:image")
    return [Event(
        source="chautauqua", source_event_id=f"chautauqua-{y}", title=title, start=at(d0, None, TZ), end=at(d1, None, TZ),
        all_day=True, timezone=TZ, url=SOURCE["url"], description=intro, image=img.get("content") if img else None,
        attendance="in_person", cost="unknown",
        cost_note="Some sessions require tickets" if "tickets required" in text.lower() else None,
        venue=Venue(name="Medora", city="Medora", region="ND", postal_code="58645"),
        organizer="Theodore Roosevelt Medora Foundation", kind="event", categories=["Festival", "Living history"],
        extra={"program": days},
    )]
