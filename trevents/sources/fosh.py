"""Friends of Sagamore Hill — friendsofsagamorehill.org/events (GoDaddy Website Builder).

The calendar widget's events are stored as `manualEvents` inside the site's published
script bundle (img1.wsimg.com/blobby/...), double-encoded as JSON. Descriptions are Draft.js blocks.
"""
from __future__ import annotations

import json
import re
from datetime import date

from ..http import get
from ..model import Event, Venue, at, guess_attendance, guess_cost, parse_clock

SOURCE = {
    "id": "fosh",
    "name": "Friends of Sagamore Hill",
    "short": "Friends of Sagamore Hill",
    "url": "https://friendsofsagamorehill.org/events",
    "type": "core",
    "region": "Oyster Bay, NY",
}
TZ = "America/New_York"


def _find_manual_events(js: str):
    for m in re.finditer(r'"((?:[^"\\]|\\.)*manualEvents(?:[^"\\]|\\.)*)"', js):
        try:
            inner = json.loads('"' + m.group(1) + '"')
        except json.JSONDecodeError:
            continue
        for start in [mm.start() for mm in re.finditer(r'"manualEvents"\s*:\s*\[', inner)]:
            i = inner.index("[", start)
            depth = 0
            for j in range(i, len(inner)):
                c = inner[j]
                if c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(inner[i : j + 1])
                        except json.JSONDecodeError:
                            break
    return None


def _draft_text(desc: str) -> str:
    try:
        d = json.loads(desc)
        return "\n\n".join(b.get("text", "").strip() for b in d.get("blocks", []) if b.get("text", "").strip())
    except (json.JSONDecodeError, TypeError, AttributeError):
        return desc or ""


def _dates(s: str) -> tuple[date, date] | None:
    """'8/15 2026' | '8/22-30 2026' | '12/30-1/2 2026'"""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})(?:\s*-\s*(?:(\d{1,2})/)?(\d{1,2}))?\s+(\d{4})", s or "")
    if not m:
        return None
    y = int(m.group(5))
    d0 = date(y, int(m.group(1)), int(m.group(2)))
    if m.group(4):
        em = int(m.group(3) or m.group(1))
        ey = y + 1 if em < d0.month else y
        d1 = date(ey, em, int(m.group(4)))
    else:
        d1 = d0
    return d0, d1


def fetch() -> list[Event]:
    page = get(SOURCE["url"]).text
    scripts = re.findall(r'src="(//img1\.wsimg\.com/blobby/go/[^"]+/script\.js)"', page)
    manual = None
    for src in scripts:
        manual = _find_manual_events(get("https:" + src).text)
        if manual:
            break
    if manual is None:
        raise RuntimeError("calendar data not found in site bundle")

    events, seen = [], set()
    today = date.today()
    for e in manual:
        key = (e.get("title"), e.get("date"))
        if key in seen:  # the bundle repeats each event for the desktop and mobile layouts
            continue
        seen.add(key)
        rng = _dates(e.get("date", ""))
        if not rng or rng[1] < today:
            continue
        d0, d1 = rng
        desc = _draft_text(e.get("desc", ""))
        st, en = (e.get("start") or "").strip(), (e.get("end") or "").strip()
        if "-" in st and not en:
            st, en = [x.strip() for x in st.split("-", 1)]
        t0, t1 = parse_clock(st) if re.search(r"\d", st) else None, parse_clock(en) if re.search(r"\d", en) else None
        loc = (e.get("location") or "").strip()
        parts = [p.strip() for p in loc.split(",")]
        venue = Venue(name=parts[0] if parts else None, address=", ".join(parts[1:]) or None,
                      city=parts[-2] if len(parts) >= 3 else None, region=parts[-1].split()[0] if len(parts) >= 3 else None)
        text = f"{e.get('title')} {desc} {loc}"
        cost, pmin, pmax, note = guess_cost(desc)
        multi = d1 > d0
        events.append(Event(
            source="fosh", source_event_id=e.get("id") or e.get("title"), title=e.get("title", "").strip(),
            start=at(d0, t0, TZ), end=at(d1 if multi else d0, t1, TZ) if (t1 or multi) else None,
            all_day=t0 is None, timezone=TZ, url=SOURCE["url"], description=desc,
            attendance=guess_attendance(text, bool(loc)), cost=cost, cost_note=note, price_min=pmin, price_max=pmax,
            venue=venue, organizer=SOURCE["name"], kind="event",
            categories=["Gable Lecture"] if "gable" in text.lower() else [],
            extra={"time_text": " – ".join(x for x in (e.get("start"), e.get("end")) if x)},
        ))
    return events
