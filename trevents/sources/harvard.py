"""Harvard Library events (LibCal) — keyword-filtered for Theodore/Edith Roosevelt.

LibCal's own `q=` search doesn't filter the JSON list, so every upcoming event is
pulled and matched locally (Harvard holds the Theodore Roosevelt Collection at Houghton).
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .. import config
from ..http import get_json
from ..model import Event, Venue, clean_text, guess_cost, relevance

SOURCE = {
    "id": "harvard",
    "name": "Harvard Library",
    "short": "Harvard Library",
    "url": "https://libcal.library.harvard.edu/calendar/main?t=d&q=roosevelt&cid=15049&cal=15049&inc=0",
    "type": "keyword",
    "region": "Cambridge, MA",
}
TZ = "America/New_York"
API = "https://libcal.library.harvard.edu/ajax/calendar/list"


def fetch() -> list[Event]:
    tz = ZoneInfo(TZ)
    rows, page = [], 1
    while page <= 20:
        d = get_json(API, params={"c": 15049, "date": "0000-00-00", "perpage": 48, "page": page, "inc": 0, "q": "roosevelt"},
                     headers={"X-Requested-With": "XMLHttpRequest"})
        res = d.get("results") or []
        rows += res
        if not res or len(rows) >= int(d.get("total_results") or 0):
            break
        page += 1

    events = []
    limit = config.horizon()
    for r in rows:
        desc = clean_text((r.get("description") or "") + " " + (r.get("more_info") or ""))
        cats = [c.get("name") for c in r.get("categories_arr") or [] if c.get("name")]
        rel, terms = relevance(r.get("title", ""), desc, " ".join(cats), r.get("presenter") or "")
        if not rel:
            continue
        start = datetime.strptime(r["startdt"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
        if start.date() > limit:
            continue
        end = datetime.strptime(r["enddt"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz) if r.get("enddt") else None
        online = bool(r.get("online_event"))
        loc = r.get("location") or ""
        locs = r.get("locations") or []
        if not loc and locs:
            loc = ", ".join(l.get("name", "") for l in locs if isinstance(l, dict))
        physical = bool(loc) or bool(r.get("in_person_registration"))
        attendance = "hybrid" if (online and physical) else "virtual" if online else "in_person" if physical else "unknown"
        cost_txt = r.get("registration_cost") or ""
        cost, pmin, pmax, note = guess_cost(cost_txt or desc)
        if not cost_txt and cost == "unknown":
            note = "No cost listed"
        events.append(Event(
            source="harvard", source_event_id=str(r["id"]), title=r.get("title", "").strip(),
            start=start, end=end, all_day=bool(r.get("all_day")), timezone=TZ, url=r.get("url"), description=desc,
            image=r.get("featured_image") or None, attendance=attendance, cost=cost, cost_note=note,
            price_min=pmin, price_max=pmax, registration_required=bool(r.get("registration_enabled")) or None,
            registration_url=r.get("url"),
            venue=Venue(name=loc or r.get("campus") or None, city="Cambridge" if physical else None,
                        region="MA" if physical else None, country="US" if physical else None),
            organizer=r.get("calendar") or SOURCE["name"], kind="event", categories=cats,
            audiences=[a.get("name") for a in r.get("audiences") or [] if a.get("name")],
            recurring=bool(r.get("recurring_event")), relevance=rel, matched_terms=terms,
            extra={"presenter": r.get("presenter") or None, "seats_left": r.get("seatsleft_text") or None},
        ))
    return events
