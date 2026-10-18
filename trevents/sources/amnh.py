"""American Museum of Natural History — amnh.org/calendar, keyword-filtered.

AMNH sits behind a Cloudflare challenge, so this source needs FIRECRAWL_API_KEY.
Each calendar card links to /calendar/<slug> and carries category, title, blurb, date and time.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..http import get
from ..model import Event, Venue, at, guess_cost, parse_clock, relevance

SOURCE = {
    "id": "amnh",
    "name": "American Museum of Natural History",
    "short": "AMNH",
    "url": "https://www.amnh.org/calendar",
    "type": "keyword",
    "region": "New York, NY",
}
TZ = "America/New_York"
VENUE = Venue(name="American Museum of Natural History", address="200 Central Park West", city="New York", region="NY", postal_code="10024")
DATE_RX = re.compile(r"(?:\w+day, )?(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (\d{4})")


def _cards_from_markdown(md: str):
    for m in re.finditer(r"\[((?:[^\[\]]|\n)+?)\]\((https://www\.amnh\.org/calendar/[^)\s]+)\)", md):
        lines = [l.strip(" \\*") for l in re.split(r"\\+\n|\n", m.group(1)) if l.strip(" \\")]
        yield m.group(2), lines, m.group(1)


def _cards_from_html(html: str):
    soup = BeautifulSoup(html, "lxml")
    for a in soup.select('a[href*="/calendar/"]'):
        href = a["href"]
        if href.rstrip("/").endswith("/calendar"):
            continue
        if href.startswith("/"):
            href = "https://www.amnh.org" + href
        lines = [l.strip() for l in a.get_text("\n").split("\n") if l.strip()]
        bold = a.find(["strong", "b", "h3", "h4"])
        yield href, lines, f"**{bold.get_text(' ', strip=True)}**" if bold else ""


def fetch() -> list[Event]:
    resp = get(SOURCE["url"], firecrawl=True)
    md = getattr(resp, "markdown", "")
    cards = list(_cards_from_markdown(md)) if md else list(_cards_from_html(resp.text))
    events, today, seen = [], date.today(), set()
    for url, lines, raw in cards:
        bm = re.search(r"\*\*(.+?)\*\*", raw)
        title = bm.group(1).strip() if bm else (lines[1] if len(lines) > 1 else lines[0] if lines else "")
        dline = next((l for l in lines if DATE_RX.search(l)), None)
        if not title or not dline or url in seen:
            continue
        seen.add(url)
        dm = DATE_RX.search(dline)
        d0 = datetime.strptime(f"{dm.group(1)} {dm.group(2)} {dm.group(3)}", "%B %d %Y").date()
        if d0 < today:
            continue
        idx = lines.index(dline)
        tline = lines[idx + 1] if idx + 1 < len(lines) else ""
        tparts = re.split(r"\s*[–-]\s*", tline)
        t1 = parse_clock(tparts[1]) if len(tparts) > 1 else None
        t0txt = tparts[0]
        if t1 and not re.search(r"[ap]m", t0txt, re.I):  # "5–7:30 pm" -> both pm
            t0txt += " pm" if t1.hour >= 12 else " am"
        t0 = parse_clock(t0txt) if re.search(r"\d", t0txt) else None
        cat = lines[0] if lines and lines[0] != title else None
        blurb = " ".join(l for l in lines[1:idx] if l != title)
        rel, terms = relevance(title, blurb)
        if not rel:
            continue
        cost, pmin, pmax, note = guess_cost(blurb)
        events.append(Event(
            source="amnh", source_event_id=url.rsplit("/", 1)[-1], title=title, start=at(d0, t0, TZ),
            end=at(d0, t1, TZ) if t1 else None, all_day=t0 is None, timezone=TZ, url=url, description=blurb,
            attendance="in_person", cost=cost if cost != "unknown" else "paid", cost_note=note or "Ticketed event",
            price_min=pmin, price_max=pmax, venue=VENUE, organizer=SOURCE["name"], kind="event",
            categories=[cat] if cat else [], status="sold_out" if "sold out" in dline.lower() else "scheduled",
            relevance=rel, matched_terms=terms,
        ))
    return events
