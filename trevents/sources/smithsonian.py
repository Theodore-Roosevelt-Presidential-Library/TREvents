"""Smithsonian Institution events — keyword-filtered for Theodore/Edith Roosevelt.

si.edu/events is a Trumba embed; the same calendar is published as JSON at
trumba.com/calendars/smithsonian-events.json (si.edu itself sits behind a bot wall).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .. import config
from ..http import get_json
from ..model import Event, Venue, clean_text, guess_attendance, guess_cost, relevance

SOURCE = {
    "id": "smithsonian",
    "name": "Smithsonian Institution",
    "short": "Smithsonian",
    "url": "https://www.si.edu/events",
    "type": "keyword",
    "region": "Washington, DC",
}
TZ = "America/New_York"
FEED = "https://www.trumba.com/calendars/smithsonian-events.json"
ATT = {"In-Person": "in_person", "Online": "virtual", "Hybrid": "hybrid"}


def _dt(s: str, off: str) -> datetime:
    sign = -1 if off.startswith("-") else 1
    tz = timezone(sign * timedelta(hours=int(off[1:3]), minutes=int(off[3:5])))
    return datetime.fromisoformat(s).replace(tzinfo=tz)


def fetch() -> list[Event]:
    rows = get_json(FEED, timeout=120)
    events = []
    limit = config.horizon()
    for r in rows:
        cf = {f.get("label"): f.get("value") for f in r.get("customFields") or []}
        desc = clean_text(r.get("description"))
        rel, terms = relevance(r.get("title", ""), desc, clean_text(cf.get("Related Exhibition")), clean_text(cf.get("Event Location")))
        if not rel:
            continue
        start = _dt(r["startDateTime"], r.get("startTimeZoneOffset") or "-0500")
        if start.date() > limit:
            continue
        end = _dt(r["endDateTime"], r.get("endTimeZoneOffset") or "-0500") if r.get("endDateTime") else None
        all_day = bool(r.get("allDay"))
        if all_day and end:
            end = end - timedelta(days=1)  # Trumba all-day ends are exclusive
        cost_text = clean_text(cf.get("Cost"))
        cost, pmin, pmax, note = guess_cost(cost_text)
        if cost == "unknown" and (r.get("requiresPayment") or re.search(r"registration price|ticket price|buy tickets|purchase|\bfee\b", cost_text, re.I)):
            cost = "paid"
        if cost == "unknown" and cost_text:
            note = cost_text[:200]
        img = (r.get("eventImage") or {}).get("url")
        ol = re.search(r'href="([^"]+)"', cf.get("Online Link") or "")
        online_link = ol.group(1) if ol else (clean_text(cf.get("Online Link")) or None)
        tickets = cf.get("Get Tickets/Register") or ""
        m = re.search(r'href="([^"]+)"', tickets) or re.search(r'href="([^"]+)"', cf.get("Cost") or "")
        venue_name = clean_text(cf.get("Venue")) or clean_text(cf.get("Building")) or None
        events.append(Event(
            source="smithsonian", source_event_id=str(r["eventID"]), title=clean_text(r.get("title")),
            start=start, end=end, all_day=all_day, timezone=TZ, url=r.get("permaLinkUrl") or r.get("webLink"),
            description=desc, image=img, attendance=ATT.get(r.get("locationType")) or guess_attendance(f"{r.get('title')} {desc}", bool(venue_name or cf.get("Event Location"))), online_url=online_link,
            cost=cost, cost_note=note, price_min=pmin, price_max=pmax,
            registration_url=m.group(1) if m else None, registration_required=True if m else None,
            venue=Venue(name=venue_name, address=clean_text(cf.get("Event Location")) or None, city=None, region=None, country=None),
            organizer=clean_text(cf.get("Sponsor")) or SOURCE["name"], kind="event",
            categories=[c.strip() for c in clean_text(cf.get("Categories")).split(",") if c.strip()],
            status="cancelled" if r.get("canceled") else ("sold_out" if r.get("reservationFull") else "scheduled"),
            relevance=rel, matched_terms=terms, accessibility=clean_text(cf.get("Accessibility")) or None,
            extra={"related_exhibition": clean_text(cf.get("Related Exhibition")) or None},
        ))
    return events
