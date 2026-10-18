"""Theodore Roosevelt Inaugural Site (Buffalo) — trsite.org/events (WordPress).

Listing cards give the event links; each event page has a heading like
"October 24, 9:00 am - November 1, 5:00 pm" and a "Cost:" line. Dates carry no year.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from ..http import get
from ..model import Event, Venue, at, clean_text, guess_attendance, guess_cost, nearest_year, parse_clock

SOURCE = {
    "id": "trsite",
    "name": "Theodore Roosevelt Inaugural Site",
    "short": "TR Inaugural Site",
    "url": "https://www.trsite.org/events/",
    "type": "core",
    "region": "Buffalo, NY",
}
TZ = "America/New_York"
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
VENUE = Venue(name="Theodore Roosevelt Inaugural Site", address="641 Delaware Ave", city="Buffalo", region="NY",
              postal_code="14202")


def _side(s: str, ref_month=None):
    """'October 24, 9:00 am' | 'November 1' | '5:00 pm' -> (month, day, time)"""
    s = s.strip().lower()
    m = re.match(r"(" + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(.*)", s)
    if m:
        return MONTHS.index(m.group(1)) + 1, int(m.group(2)), parse_clock(m.group(3)) if re.search(r"\d", m.group(3)) else None
    return ref_month, None, parse_clock(s) if re.search(r"\d", s) else None


def parse_when(s: str):
    parts = [p for p in re.split(r"\s+[-–]\s+", s.strip()) if p]
    if not parts:
        return None
    m0, d0, t0 = _side(parts[0])
    if not m0 or not d0:
        return None
    y0 = nearest_year(m0, d0)
    start = (date(y0, m0, d0), t0)
    end = None
    if len(parts) > 1:
        m1, d1, t1 = _side(parts[1], m0)
        if d1 is None:
            d1 = d0
        y1 = y0 + 1 if (m1 or m0) < m0 else y0
        end = (date(y1, m1 or m0, d1), t1)
    return start, end


def fetch() -> list[Event]:
    soup = BeautifulSoup(get(SOURCE["url"]).text, "lxml")
    events = []
    today = date.today()
    for card in soup.select("div.event-card"):
        a = card.select_one("a.event-anchor[href]")
        title_el = card.select_one(".post-preview-title")
        if not a or not title_el:
            continue
        url = a["href"]
        title = title_el.get_text(" ", strip=True)
        list_dates = (card.select_one(".event-dates") or {}).get_text(" ", strip=True) if card.select_one(".event-dates") else ""
        image = (card.select_one("img") or {}).get("src") if card.select_one("img") else None

        page = BeautifulSoup(get(url).text, "lxml")
        art = page.find("article") or page.find("main") or page.body
        when_el = None
        for h4 in art.find_all("h4"):
            if re.search(r"(" + "|".join(MONTHS) + r")\s+\d", h4.get_text(" ", strip=True), re.I):
                when_el = h4
                break
        when = when_el.get_text(" ", strip=True) if when_el else list_dates
        parsed = parse_when(when) or parse_when(list_dates)
        if not parsed:
            continue
        (d0, t0), end = parsed
        cost_line = ""
        for p in art.find_all("p"):
            if p.get_text(strip=True).lower().startswith("cost:"):
                cost_line = p.get_text(" ", strip=True)[5:].strip()
                break
        if when_el:
            when_el.parent.decompose()
        body = clean_text(str(art))
        if (end[0] if end else d0) < today:
            continue
        cost, pmin, pmax, note = guess_cost(cost_line or body)
        if cost_line and cost == "unknown":
            note = cost_line
        if re.search(r"\b(will be|is|are) closed\b", card.get_text(" ", strip=True) + " " + body[:400], re.I):
            kind = "closure"
        else:
            kind = "event"
        if t0 is not None and t0.hour == 0 and t0.minute == 0:
            t0 = None  # "12:00 am" means no time was set
        all_day = t0 is None
        e_end = None
        if end:
            e_end = at(end[0], end[1] or (None if all_day else t0), TZ) if (end[0] != d0 or end[1]) else None
        events.append(Event(
            source="trsite", source_event_id=url.rstrip("/").rsplit("/", 1)[-1], title=title,
            start=at(d0, t0, TZ), end=e_end, all_day=all_day, timezone=TZ, url=url, description=body, image=image,
            attendance=guess_attendance(f"{title} {body}", True), cost=cost, cost_note=note or (cost_line or None),
            price_min=pmin, price_max=pmax, venue=VENUE, organizer=SOURCE["name"], kind=kind,
            extra={"date_text": when},
        ))
    return events
