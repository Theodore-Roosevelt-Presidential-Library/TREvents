"""The Teddy Roosevelt Show (Joe Wiegand) — teddyrooseveltshow.com/tour-schedule.html.

Static list of appearances. Rows marked private (title "Private event" or a
`.private-label`) are skipped. Show times like "5:00 PM & 7:30 PM" become separate
occurrences. The venue's state sets the time zone.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..http import get
from ..model import Event, Venue, at, guess_cost, parse_clock

SOURCE = {
    "id": "joe",
    "name": "The Teddy Roosevelt Show (Joe Wiegand)",
    "short": "Joe Wiegand",
    "url": "https://teddyrooseveltshow.com/tour-schedule.html",
    "type": "core",
    "region": "On tour",
}
STATE_TZ = {
    **{s: "America/New_York" for s in "CT DE DC FL GA IN KY ME MD MA MI NH NJ NY NC OH PA RI SC VT VA WV".split()},
    **{s: "America/Chicago" for s in "AL AR IL IA KS LA MN MS MO NE ND OK SD TN TX WI".split()},
    **{s: "America/Denver" for s in "CO ID MT NM UT WY".split()},
    "AZ": "America/Phoenix", **{s: "America/Los_Angeles" for s in "CA NV OR WA".split()},
    "AK": "America/Anchorage", "HI": "Pacific/Honolulu",
}


def fetch() -> list[Event]:
    soup = BeautifulSoup(get(SOURCE["url"]).text, "lxml")
    events, today = [], date.today()
    for row in soup.select("li.event-row"):
        h3 = row.find("h3")
        tm = row.select_one(".event-date time[datetime]")
        if not h3 or not tm:
            continue
        title = h3.get_text(" ", strip=True)
        if row.select_one(".private-label") or re.match(r"private\b", title, re.I):
            continue  # Joe's private bookings stay off the public calendar
        d0 = date.fromisoformat(tm["datetime"][:10])
        span = re.search(r"\d+\s*[–-]\s*(\d+)", tm.get_text(strip=True))
        d1 = d0
        if span:
            end_day = int(span.group(1))
            d1 = d0.replace(day=end_day) if end_day >= d0.day else (d0.replace(day=1) + timedelta(days=32)).replace(day=end_day)
        if d1 < today:
            continue
        loc = (row.select_one(".event-location") or BeautifulSoup("", "lxml")).get_text(" ", strip=True)
        venue_name, _, place = loc.partition(" · ")
        if not place:
            venue_name, place = "", loc
        city, _, st = place.rpartition(", ")
        st = st.strip()[:2].upper()
        tz = STATE_TZ.get(st, "America/Chicago")
        ttxt = (row.select_one(".event-time") or BeautifulSoup("", "lxml")).get_text(" ", strip=True)
        times_part, _, note = ttxt.partition(" · ")
        times = [parse_clock(t) for t in re.findall(r"\d{1,2}(?::\d{2})?\s*[AP]M", times_part, re.I)]
        link = row.select_one("a.event-link[href]")
        url = link["href"] if link else SOURCE["url"]
        slug = re.sub(r"\W+", "-", title.lower()).strip("-")
        base = dict(source="joe", title=title, timezone=tz, url=url,
                    description=" · ".join(x for x in ("Joe Wiegand as Theodore Roosevelt.", note if note and not re.match(r"(all day|[A-Z][a-z]+ \d)", note) else "") if x),
                    attendance="in_person", cost="unknown", cost_note="See event page",
                    venue=Venue(name=venue_name or None, city=city or None, region=st or None),
                    organizer="Joe Wiegand", kind="event", categories=["Performance"],
                    registration_url=link["href"] if link else None, extra={"time_text": ttxt})
        if times and d0 == d1:
            for i, t in enumerate(times):
                events.append(Event(source_event_id=f"{d0}-{slug}-{i}", start=at(d0, t, tz),
                                    all_day=False, recurring=False, **base))
        else:
            events.append(Event(source_event_id=f"{d0}-{slug}", start=at(d0, times[0] if times else None, tz),
                                end=at(d1, None, tz) if d1 > d0 else None, all_day=not times, **base))
    return events
