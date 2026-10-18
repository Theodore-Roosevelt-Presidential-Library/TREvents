"""National Archives (and the presidential libraries it runs) — keyword-filtered.

Candidates come from the calendar RSS feed (newest postings, with full descriptions)
and the "upcoming" list on archives.gov/calendar. Only events that mention Theodore or
Edith Roosevelt get their event page fetched; parsed pages are cached between runs.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .. import cache, config
from ..http import get
from ..model import Event, Venue, clean_text, guess_attendance, guess_cost, parse_clock, relevance

SOURCE = {
    "id": "nara",
    "name": "National Archives",
    "short": "National Archives",
    "url": "https://www.archives.gov/calendar/event",
    "type": "keyword",
    "region": "National",
}
BASE = "https://www.archives.gov"
TZABBR = {"EST": "America/New_York", "EDT": "America/New_York", "ET": "America/New_York",
          "CST": "America/Chicago", "CDT": "America/Chicago", "CT": "America/Chicago",
          "MST": "America/Denver", "MDT": "America/Denver", "MT": "America/Denver",
          "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles", "PT": "America/Los_Angeles"}


def _parse_when(s: str):
    s = re.sub(r"\s+", " ", s).strip()
    tzm = re.search(r"\b(E|C|M|P)(S|D)?T\b", s)
    tz = TZABBR.get(tzm.group(0), "America/New_York") if tzm else "America/New_York"
    dates = re.findall(r"(?:\w+day, )?(\w+ \d{1,2}, \d{4})", s)
    times = re.findall(r"(\d{1,2}(?::\d{2})? ?[ap]\.?m\.?|noon)", s, re.I)
    if not dates:
        return None
    d0 = datetime.strptime(dates[0], "%B %d, %Y").date()
    d1 = datetime.strptime(dates[-1], "%B %d, %Y").date()
    t0 = parse_clock(times[0]) if times else None
    t1 = parse_clock(times[1]) if len(times) > 1 else None
    return d0, d1, t0, t1, tz


def _detail(url: str) -> dict | None:
    soup = BeautifulSoup(get(url).text, "lxml")
    main = soup.select_one("#block-system-main") or soup.find("main") or soup.body
    h1 = main.find("h1")
    when_el = main.select_one(".date-display-single") or main.select_one(".date-display-range")
    if not h1 or not when_el:
        return None
    venue = main.find("h3")
    addr = main.select_one(".event_address")
    links = [(a.get_text(" ", strip=True), a["href"]) for a in main.find_all("a", href=True)]
    reg_links = [(t, h) for t, h in links if t.upper().startswith("REGISTER")]
    img = soup.find("meta", property="og:image")
    rec = {
        "title": h1.get_text(" ", strip=True), "when": when_el.get_text(" ", strip=True),
        "venue": venue.get_text(" ", strip=True) if venue else None,
        "address": addr.get_text(" ", strip=True) if addr else None,
        "register": reg_links, "image": img.get("content") if img else None,
    }
    for el in main.select(".event-social-media-buttons, h1, h3, .event_address, #find-event-btn"):
        el.decompose()
    when_el.decompose()
    for a in main.find_all("a", href=True):
        if a.get_text(" ", strip=True).upper().startswith("REGISTER"):
            a.decompose()
    rec["description"] = clean_text(str(main))[:6000]
    if rec["image"] and "naralogo" in rec["image"]:
        rec["image"] = None
    return rec


def fetch() -> list[Event]:
    store = cache.load("nara")
    candidates: dict[str, str] = {}
    try:
        root = ET.fromstring(get(f"{BASE}/calendar/feed").content)
        for item in root.iter("item"):
            link = (item.findtext("link") or "").strip()
            candidates[link] = (item.findtext("title") or "") + " " + clean_text(item.findtext("description") or "")
    except Exception:
        pass
    listing = get(f"{BASE}/calendar").text
    for path in set(re.findall(r'href="(/calendar/event/[a-z][a-z0-9-]{6,})"', listing)):
        candidates.setdefault(BASE + path, "")

    events = []
    today = date.today()
    for url, blurb in candidates.items():
        rec = store.get(url)
        if rec is None or cache.stale(rec):
            if blurb and not relevance(blurb)[0]:
                store[url] = cache.stamp({"irrelevant": True, "blurb": blurb[:300]})
                continue
            d = _detail(url)
            store[url] = cache.stamp(d or {"irrelevant": True})
            rec = store[url]
        if rec.get("irrelevant"):
            continue
        rel, terms = relevance(rec["title"], rec["description"], rec.get("venue") or "")
        if not rel:
            continue
        w = _parse_when(rec["when"])
        if not w:
            continue
        d0, d1, t0, t1, tz = w
        if d1 < today:
            continue
        z = ZoneInfo(tz)
        start = datetime.combine(d0, t0 or time(0), tzinfo=z)
        end = datetime.combine(d1, t1, tzinfo=z) if t1 else (datetime.combine(d1, time(0), tzinfo=z) if d1 > d0 else None)
        reg = [t.upper() for t, _ in rec.get("register", [])]
        in_p = any("IN-PERSON" in t or "IN PERSON" in t for t in reg)
        virt = any(k in t for t in reg for k in ("LIVESTREAM", "VIRTUAL", "ONLINE", "ZOOM", "WEBINAR"))
        online_venue = (rec.get("venue") or "").lower() in ("online", "virtual") or "online" in (rec.get("address") or "").lower()
        if in_p and virt:
            attendance = "hybrid"
        elif virt or online_venue:
            attendance = "virtual" if not in_p else "hybrid"
        else:
            attendance = guess_attendance(rec["description"], bool(rec.get("address")))
        cost, pmin, pmax, note = guess_cost(rec["description"])
        addr = rec.get("address") or ""
        parts = [p.strip() for p in addr.split(",")]
        events.append(Event(
            source="nara", source_event_id=url.rsplit("/", 1)[-1], title=rec["title"], start=start, end=end,
            all_day=t0 is None, timezone=tz, url=url, description=rec["description"], image=rec.get("image"),
            attendance=attendance, cost=cost, cost_note=note, price_min=pmin, price_max=pmax,
            registration_url=rec["register"][0][1] if rec.get("register") else None,
            registration_required=True if rec.get("register") else None,
            venue=Venue(name=rec.get("venue"), address=addr or None,
                        city=parts[-2] if len(parts) >= 3 else None, region=parts[-1][:2] if len(parts) >= 3 else None),
            organizer=SOURCE["name"], kind="event", relevance=rel, matched_terms=terms,
        ))
    cache.save("nara", store)
    return events
