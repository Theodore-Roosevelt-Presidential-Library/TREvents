"""White House Historical Association — whitehousehistory.org/events, keyword-filtered.

The upcoming-events listing gives links; each event page has Date / Time / Days / Location
fields. Pages are cached, and only Roosevelt-related events are kept.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from .. import cache
from ..http import get
from ..model import Event, Venue, at, clean_text, guess_attendance, guess_cost, parse_clock, relevance

SOURCE = {
    "id": "whha",
    "name": "White House Historical Association",
    "short": "White House Historical Assn.",
    "url": "https://www.whitehousehistory.org/events?topic=All&type=upcoming&orderBy=date+ASC",
    "type": "keyword",
    "region": "Washington, DC",
}
TZ = "America/New_York"
LABELS = ("Date", "Time", "Days", "Location", "Cost", "Price", "Tickets")


def _detail(url: str) -> dict:
    soup = BeautifulSoup(get(url).text, "lxml")
    main = soup.find("main") or soup.body
    for t in main(["script", "style", "svg", "noscript", "nav", "form"]):
        t.decompose()
    lines = [l.strip() for l in main.get_text("\n").split("\n") if l.strip()]
    fields, i = {}, 0
    while i < len(lines):
        if lines[i] in LABELS and i + 1 < len(lines):
            vals, j = [], i + 1
            while j < len(lines) and lines[j] not in LABELS and len(vals) < 4 and lines[j] not in ("Directions", "Show Me More"):
                vals.append(lines[j])
                j += 1
            fields[lines[i]] = vals
            i = j
        else:
            i += 1
    body_start = max((lines.index(l) for l in ("Directions",) if l in lines), default=0)
    body = " ".join(lines[body_start + 1 :])
    body = re.split(r"Subscribe to our newsletter", body)[0]
    img = soup.find("meta", property="og:image")
    h1 = soup.find("h1")
    return {"title": h1.get_text(" ", strip=True) if h1 else None, "fields": fields, "description": body[:6000],
            "image": img.get("content") if img else None}


def fetch() -> list[Event]:
    store = cache.load("whha")
    soup = BeautifulSoup(get(SOURCE["url"]).text, "lxml")
    events = []
    today = date.today()
    for card in soup.select("article.result-card--events"):
        a = card.select_one("a.result-card__link[href]")
        tm = card.select_one("time[datetime]")
        if not a or not tm:
            continue
        url = a["href"]
        title = a.get_text(" ", strip=True)
        rec = store.get(url)
        if rec is None or cache.stale(rec):
            rec = store[url] = cache.stamp(_detail(url))
        rel, terms = relevance(title, rec["description"], " ".join(rec["fields"].get("Location", [])))
        if not rel:
            continue
        f = rec["fields"]
        try:
            d0 = datetime.strptime(f["Date"][0], "%m/%d/%Y").date() if f.get("Date") else date.fromisoformat(tm["datetime"])
        except ValueError:
            d0 = date.fromisoformat(tm["datetime"][:10])
        if d0 < today:
            continue
        ttxt = " ".join(f.get("Time", []))
        tparts = re.split(r"\s*[-–]\s*", ttxt)
        t0 = parse_clock(tparts[0]) if ttxt else None
        t1 = parse_clock(tparts[1]) if len(tparts) > 1 else None
        loc = f.get("Location", [])
        loc_txt = " ".join(loc)
        virtual_venue = bool(re.search(r"facebook|youtube|zoom|online|virtual|livestream", loc_txt, re.I))
        attendance = guess_attendance(f"{title} {rec['description']} {loc_txt}", bool(loc) and not virtual_venue)
        if virtual_venue and attendance == "in_person":
            attendance = "virtual"
        cost, pmin, pmax, note = guess_cost(" ".join(f.get("Cost", []) + f.get("Price", []) + f.get("Tickets", [])) + " " + rec["description"])
        events.append(Event(
            source="whha", source_event_id=url.rstrip("/").rsplit("/", 1)[-1], title=rec.get("title") or title,
            start=at(d0, t0, TZ), end=at(d0, t1, TZ) if t1 else None, all_day=t0 is None, timezone=TZ, url=url,
            description=rec["description"], image=rec.get("image"), attendance=attendance,
            cost=cost, cost_note=note, price_min=pmin, price_max=pmax,
            venue=Venue(name=None if virtual_venue else (loc[0] if loc else None), address=", ".join(loc[1:]) or None),
            online_url=None, organizer=SOURCE["name"], kind="event", relevance=rel, matched_terms=terms,
        ))
    cache.save("whha", store)
    return events
