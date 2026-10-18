"""Library of Congress events — keyword-filtered for Theodore/Edith Roosevelt.

loc.gov's JSON API (`fo=json`) lists upcoming events in date order. Its keyword search
is unreliable for events, so every upcoming event is read and matched locally.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .. import config
from ..http import get_json
from ..model import Event, Venue, clean_text, guess_cost, relevance

SOURCE = {
    "id": "loc",
    "name": "Library of Congress",
    "short": "Library of Congress",
    "url": "https://www.loc.gov/events/?q=roosevelt",
    "type": "keyword",
    "region": "Washington, DC",
}
TZ = "America/New_York"


def fetch() -> list[Event]:
    # loc.gov pages are heavy (~50 KB per event), so look 8 months ahead rather than the full horizon
    limit = min(config.horizon(), date.today() + timedelta(days=240))
    url, page, rows = "https://www.loc.gov/events/", 1, []
    while page <= 40:
        d = get_json(url, params={"fo": "json", "c": 100, "sp": page, "at": "results"}, timeout=120, firecrawl=True)
        res = d.get("results") or []
        rows += res
        last = max((r.get("date") or "" for r in res), default="")
        if len(res) < 100 or last > limit.isoformat():
            break
        page += 1

    events, seen = [], set()
    for r in rows:
        it = r.get("item") or {}
        title = r.get("title") or ""
        desc = clean_text(it.get("article") or " ".join(r.get("description") or []))
        rel, terms = relevance(title, desc, it.get("tag_line") or "", " ".join(it.get("event_series") or []) if isinstance(it.get("event_series"), list) else "")
        if not rel or not it.get("event_start"):
            continue
        start = datetime.fromisoformat(it["event_start"])
        if start.date() > limit or (r.get("url"), start) in seen:
            continue
        seen.add((r.get("url"), start))
        end = datetime.fromisoformat(it["event_end"]) if it.get("event_end") else None
        v = it.get("venue") or {}
        addr = v.get("building_address") or {}
        coords = (v.get("building_coordinates") or "").split(",")
        online = it.get("online_only") in (True, "True") or it.get("venue_campus") == "online_only"
        stream = str(it.get("livestream")).lower() in ("yes", "true")
        attendance = "virtual" if online else ("hybrid" if stream else "in_person")
        cond = it.get("attendance_conditions") or ""
        cost, pmin, pmax, note = guess_cost(desc + " " + str(it.get("ticket_options") or ""))
        note = note or {"timed_entry_passes": "Timed-entry pass required", "ticket": "Ticket required",
                        "registration": "Registration required"}.get(cond)
        img = (r.get("image_url") or [None])[0]
        events.append(Event(
            source="loc", source_event_id=str(it.get("event_id") or r.get("id")), title=title.strip(),
            start=start, end=end, timezone=TZ, url=r.get("url"), description=desc,
            image=img.split("#")[0] if img else None, attendance=attendance,
            online_url=(it.get("livestream_urls") or [None])[0] if isinstance(it.get("livestream_urls"), list) else None,
            cost=cost, cost_note=note, price_min=pmin, price_max=pmax,
            registration_required=cond in ("ticket", "registration", "timed_entry_passes") or None,
            registration_url=it.get("ticket_link") or None,
            venue=Venue(name=" · ".join(x for x in (v.get("room"), v.get("building")) if x) or v.get("campus"),
                        address=addr.get("street_address"), city=addr.get("city"), region=addr.get("state"),
                        postal_code=addr.get("zipcode"),
                        lat=float(coords[0]) if len(coords) == 2 and coords[0] else None,
                        lon=float(coords[1]) if len(coords) == 2 and coords[1] else None),
            organizer=SOURCE["name"], kind="event", categories=it.get("categories") or [],
            audiences=[it.get("audience")] if it.get("audience") else [],
            status="cancelled" if it.get("event_status") == "cancelled" else "scheduled",
            relevance=rel, matched_terms=terms,
        ))
    return events
