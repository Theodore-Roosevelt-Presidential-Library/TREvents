"""Theodore Roosevelt Association — theodoreroosevelt.org events calendar (ClubExpress).

The "Future" list view gives every upcoming event; each event page has the full
date/time range, location, category and fee text.
"""
from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..http import get
from ..model import Event, Venue, clean_text, guess_attendance, guess_cost

SOURCE = {
    "id": "tra",
    "name": "Theodore Roosevelt Association",
    "short": "TR Association",
    "url": "https://www.theodoreroosevelt.org/content.aspx?page_id=4001&club_id=991271",
    "type": "core",
    "region": "National",
}
TZ = "America/New_York"
BASE = "https://www.theodoreroosevelt.org"
LABELS = ["About this event", "Date and Time", "Location", "Event Contact(s)", "Category", "Registration Info",
          "Capacity", "Additional Info", "Registration", "Registration/Deposit", "Fees", "Event Fees"]


def _sections(lines: list[str]) -> dict:
    out, cur = {}, None
    for l in lines:
        if l in LABELS:
            cur = l
            out.setdefault(cur, [])
        elif cur:
            out[cur].append(l)
    return out


def _dt(s: str):
    s = re.sub(r"\s+", " ", s.strip())
    for fmt in ("%A, %B %d, %Y, %I:%M %p", "%A, %B %d, %Y", "%B %d, %Y, %I:%M %p"):
        try:
            return datetime.strptime(s, fmt), "%I" in fmt
        except ValueError:
            pass
    return None, False


def fetch() -> list[Event]:
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(TZ)
    soup = BeautifulSoup(get(SOURCE["url"]).text, "lxml")
    events, seen = [], set()
    for box in soup.select("div.list-event-container"):
        a = box.select_one(".event-list-title a[href*='item_id']")
        if not a:
            continue
        url = BASE + a["href"] if a["href"].startswith("/") else a["href"]
        item_id = re.search(r"item_id=(\d+)", url).group(1)
        if item_id in seen:
            continue
        seen.add(item_id)
        title = a.get_text(" ", strip=True)
        listing_desc = clean_text(str(box.select_one(".event-drop-details") or ""))

        dsoup = BeautifulSoup(get(url).text, "lxml")
        for t in dsoup(["script", "style", "svg", "noscript"]):
            t.decompose()
        lines = [l.strip() for l in dsoup.body.get_text("\n").split("\n") if l.strip()]
        sec = _sections(lines)
        when = " ".join(sec.get("Date and Time", [])[:1])
        parts = re.split(r"\s+until\s+", when)
        start, has_t0 = _dt(parts[0]) if parts and parts[0] else (None, False)
        if not start:
            m = re.search(r"\w{3}, (\w{3} \d{1,2}, \d{4})(?: at (\d{1,2}:\d{2} [AP]M))?", box.get_text(" ", strip=True))
            if not m:
                continue
            start = datetime.strptime(m.group(1) + (" " + m.group(2) if m.group(2) else ""), "%b %d, %Y" + (" %I:%M %p" if m.group(2) else ""))
            has_t0 = bool(m.group(2))
        end, _ = _dt(parts[1]) if len(parts) > 1 else (None, False)
        if end and end.date() != start.date() and not re.search(r"\d:\d\d", parts[1]):
            end = end.replace(hour=23, minute=59)

        about = "\n".join(sec.get("About this event", []))
        desc = clean_text(about) or listing_desc
        loc_lines = [l for l in sec.get("Location", []) if l.lower() not in ("map", "directions", "view map")][:4]
        category = " ".join(sec.get("Category", [])[:1])
        fee_text = " ".join(sec.get("Registration Info", []) + sec.get("Registration/Deposit", []) + sec.get("Fees", []) + sec.get("Event Fees", []))
        cost, pmin, pmax, note = guess_cost(fee_text + " " + desc)
        text = f"{title} {category} {desc} {' '.join(loc_lines)}"
        attendance = "virtual" if re.search(r"\bzoom\b", category + " " + title, re.I) else guess_attendance(text, bool(loc_lines))
        if attendance == "unknown" and re.search(r"trip|expedition|cruise|tour|gala|dinner|meeting|award", f"{title} {category}", re.I):
            attendance = "in_person"
        all_day = not has_t0
        events.append(Event(
            source="tra", source_event_id=item_id, title=title,
            start=start.replace(tzinfo=tz), end=end.replace(tzinfo=tz) if end else None, all_day=all_day, timezone=TZ,
            url=url, description=desc, attendance=attendance, cost=cost, cost_note=note, price_min=pmin, price_max=pmax,
            registration_required=True if re.search(r"registration is required", fee_text, re.I) else None,
            registration_url=url, venue=Venue(name=loc_lines[0] if loc_lines else None, address=", ".join(loc_lines[1:]) or None),
            organizer=SOURCE["name"], kind="event", categories=[category] if category else [],
            extra={"capacity": " ".join(sec.get("Capacity", [])[:1]) or None},
        ))
    return events
