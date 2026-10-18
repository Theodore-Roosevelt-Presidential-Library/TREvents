# TREvents

One calendar of Theodore Roosevelt events from every TR-related organization, rebuilt daily by GitHub Actions and published at **https://trevents.labs.trlibrary.com**.

Outputs:

| Output | URL |
|---|---|
| Upcoming events widget | `/widgets/upcoming.html` |
| Month calendar widget | `/widgets/month.html` |
| Week calendar widget | `/widgets/week.html` |
| Embed loader (auto-sizing iframe) | `/embed.js` |
| iCal — special events | `/calendar.ics` |
| iCal — everything incl. daily tours | `/calendar-all.ics` |
| iCal — online / free / per source | `/ics/virtual.ics`, `/ics/free.ics`, `/ics/{source}.ics` |
| JSON API | `/api/v1/events.json`, `upcoming.json`, `months/YYYY-MM.json`, `sources/{id}.json`, `sources.json`, `fields.json`, `review.json` |

## Sources

Roosevelt organizations are taken in full; general calendars are scanned for Theodore/Edith Roosevelt terms.

| id | Organization | How it's read | Scope |
|---|---|---|---|
| `trpl` | Theodore Roosevelt Presidential Library | sitemap → event pages (schema.org JSON-LD + "All Hours" table) | all |
| `nps` | NPS: Sagamore Hill, TR Birthplace, TR Inaugural Site, TR Island, TR National Park | NPS Data API (`NPS_API_KEY`) | all |
| `trsite` | TR Inaugural Site (Buffalo) | listing + event pages | all |
| `fosh` | Friends of Sagamore Hill | GoDaddy calendar data in the site bundle | all |
| `tra` | Theodore Roosevelt Association | ClubExpress list + event pages | all |
| `trc` | Theodore Roosevelt Center (DSU) | "Other Upcoming Events" text blocks (dates read from prose → review list) | all |
| `chautauqua` | Badlands Chautauqua (TR Medora Foundation) | medora.com/chautauqua/ headline dates → one multi-day event; picks up next year's dates when the page is refreshed | all |
| `joe` | The Teddy Roosevelt Show (Joe Wiegand) | tour schedule page; **private events skipped** | all public |
| `smithsonian` | Smithsonian | Trumba JSON feed behind si.edu/events | keyword |
| `loc` | Library of Congress | loc.gov JSON API (8 months ahead) | keyword |
| `nara` | National Archives | calendar RSS + upcoming list → event pages (cached) | keyword |
| `harvard` | Harvard Library | LibCal JSON | keyword |
| `whha` | White House Historical Association | upcoming list → event pages (cached) | keyword |
| `amnh` | American Museum of Natural History | calendar page via Firecrawl (`FIRECRAWL_API_KEY`; Cloudflare blocks direct reads) | keyword |

Keyword matching (`trevents/model.py → relevance`) treats terms like *Theodore Roosevelt, Edith Roosevelt, Sagamore Hill, Rough Riders, Bull Moose, Elkhorn Ranch, Roosevelt Island* as matches, plain *Roosevelt* as a "possible" match (sent to `/api/v1/review.json`), and drops anything that's about FDR or Eleanor Roosevelt.

## Every event carries

`id, series_id, source, source_name, source_event_id, also_listed, title, description, summary, url, image, start, end, all_day, timezone, attendance (in_person | virtual | hybrid | unknown), online_url, cost (free | paid | unknown), cost_note, price_min, price_max, registration_required, registration_url, venue {name, address, city, region, postal_code, country, lat, lon}, organizer, kind (event | tour | exhibition | program | closure), categories, audiences, recurring, status (scheduled | cancelled | postponed | sold_out), relevance (core | matched | possible), matched_terms, accessibility, region_label, first_seen, last_seen, extra`

Full definitions: `/api/v1/fields.json` (source: `trevents/fields.py`).

## Embedding

```html
<div data-trevents="upcoming" data-limit="5" data-source="trpl,nps"></div>
<script src="https://trevents.labs.trlibrary.com/embed.js" async></script>
```

`data-trevents` = `upcoming | month | week`. Optional: `data-source`, `data-attendance`, `data-cost`, `data-kind`, `data-q`, `data-limit`, `data-recurring` (`hide` = default, leaves out repeating tours and daily programs; `collapse` = one row per tour series; `show` = every tour time), `data-filters` (`1` shows the filter bar), `data-title` (`none` hides it), `data-theme` (`light | dark | auto`), `data-bg="transparent"`, `data-compact="1"`, `data-date` (`YYYY-MM-DD` start). The same keys work as URL parameters on the widget pages for a plain iframe. The home page has a snippet builder.

## Running it

```bash
pip install -r requirements.txt
python -m trevents.build               # every source
python -m trevents.build --only trpl,joe
```

GitHub Actions (`.github/workflows/update.yml`) runs daily at ~5:17 a.m. Central and on demand (Actions → Update events → Run workflow, optionally with a list of sources). It commits `docs/` and `data/`.

**Repo secrets:** `NPS_API_KEY` (free at https://www.nps.gov/subjects/developer/get-started.htm — without it the NPS source uses the rate-limited DEMO_KEY), `FIRECRAWL_API_KEY` (needed for AMNH; also used as a fallback if another site starts blocking the runner).

**Pages:** Settings → Pages → Deploy from branch `main`, folder `/docs`. Custom domain `trevents.labs.trlibrary.com` (`docs/CNAME`), with a DNS CNAME from `trevents.labs` to `theodore-roosevelt-presidential-library.github.io`.

**When a source fails** its last good data is kept for 7 days (`data/store/`), and `/api/v1/sources.json` shows the error. Detail pages for NARA and WHHA are cached in `data/cache/`.

## Hand corrections

- `config/overrides.yaml` — exclude events (by id, series, URL or title regex) or overwrite fields (e.g. force `attendance: hybrid`).
- `config/manual_events.yaml` — add events for organizations with no readable calendar.

## Adding a source

Add a module in `trevents/sources/` with a `SOURCE` dict and a `fetch()` that returns `Event` objects (`trevents/model.py`), then list it in `trevents/sources/__init__.py`. List order is the de-duplication priority when two organizations post the same event.
