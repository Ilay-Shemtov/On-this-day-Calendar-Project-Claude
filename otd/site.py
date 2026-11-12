"""Writes the small website published next to the calendar: subscribe page, review report, days.json."""

from __future__ import annotations

import datetime as dt
import html
import json
from collections import Counter
from pathlib import Path

from .curate import Candidate, DayResult, year_label
from .ics import MONTHS

ICS_NAME = "on-this-day.ics"

STYLE = """
:root { --ink:#1d1b16; --muted:#6b6458; --paper:#fbf8f1; --card:#fff; --line:#e6dfd0; --accent:#8a3b12; --keep:#2f6b3a; --drop:#9b2c2c; }
* { box-sizing: border-box; }
body { margin:0; font:16px/1.55 Georgia, 'Iowan Old Style', serif; color:var(--ink); background:var(--paper); }
main { max-width: 860px; margin: 0 auto; padding: 48px 20px 80px; }
h1 { font-size: 2.1rem; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 1.15rem; margin: 36px 0 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--accent); font-family: system-ui, sans-serif; }
p.lede { color: var(--muted); margin: 0 0 28px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 20px 22px; margin: 14px 0; }
.buttons { display:flex; flex-wrap:wrap; gap:10px; margin: 12px 0 6px; }
a.btn, button.btn { font: 600 14px system-ui, sans-serif; padding: 10px 14px; border-radius: 8px; border: 1px solid var(--ink);
  background: var(--ink); color: #fff; text-decoration: none; cursor: pointer; }
a.btn.alt, button.btn.alt { background: transparent; color: var(--ink); }
code { font: 13px ui-monospace, Menlo, monospace; background:#f1ece1; padding: 2px 5px; border-radius: 4px; word-break: break-all; }
.small { font: 13px/1.5 system-ui, sans-serif; color: var(--muted); }
a { color: var(--accent); }
ul.items a, td a { color: inherit; text-decoration-color: #cbbfa6; text-underline-offset: 3px; }
ul.items a:hover, td a:hover { text-decoration-color: var(--accent); }
ul.items { list-style:none; padding:0; margin: 6px 0 14px; }
ul.items li { padding: 4px 0 4px 64px; text-indent: -64px; }
.yr { display:inline-block; width:60px; text-indent:0; font: 600 13px system-ui, sans-serif; color: var(--accent); }
table { width:100%; border-collapse: collapse; font: 14px/1.45 system-ui, sans-serif; background: var(--card); }
th, td { text-align:left; vertical-align: top; padding: 7px 8px; border-bottom: 1px solid var(--line); }
th { position: sticky; top: 0; background: #f4efe4; }
td.why { color: var(--muted); width: 30%; }
.pill { font: 600 11px system-ui, sans-serif; padding: 2px 7px; border-radius: 99px; color:#fff; white-space: nowrap; }
.pill.drop { background: var(--drop); } .pill.keep { background: var(--keep); }
input[type=search] { width:100%; padding:10px 12px; font: 15px system-ui, sans-serif; border:1px solid var(--line); border-radius:8px; margin: 8px 0 12px; }
.stats { display:flex; flex-wrap: wrap; gap: 8px; } .stats span { font: 13px system-ui, sans-serif; background:#fff; border:1px solid var(--line); border-radius: 99px; padding: 3px 10px; }
"""


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _day_label(key: str) -> str:
    return f"{MONTHS[int(key[:2]) - 1]} {int(key[3:])}"


def _item_json(c: Candidate) -> dict:
    return {"year": year_label(c.year), "text": c.text, "url": c.link}


def days_json(days: list[DayResult]) -> dict[str, str]:
    """One small JSON file per month (days/MM.json) for the landing page's 'today' preview."""
    months: dict[str, dict] = {}
    for d in days:
        months.setdefault(d.key[:2], {})[d.key] = {
            "headline": _item_json(d.headline) if d.headline else None,
            "events": [_item_json(c) for c in d.events],
            "births": [_item_json(c) for c in d.births],
            "deaths": [_item_json(c) for c in d.deaths],
        }
    return {f"days/{m}.json": json.dumps(v, ensure_ascii=False, separators=(",", ":")) for m, v in months.items()}


def index_html(cfg: dict) -> str:
    name = _esc(cfg["calendar"]["name"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name}</title><style>{STYLE}</style></head>
<body><main>
<h1>{name}</h1>
<p class="lede">{_esc(cfg["calendar"]["description"])} One all-day entry per date, repeating every year.</p>

<div class="card">
  <strong>Subscribe</strong>
  <div class="buttons">
    <a class="btn" id="google" href="#">Add to Google Calendar</a>
    <a class="btn alt" id="webcal" href="#">Apple Calendar / Outlook (webcal)</a>
    <button class="btn alt" id="copy" type="button">Copy feed URL</button>
  </div>
  <p class="small">Feed URL: <code id="url"></code><br>
  Google: if the button doesn't work, open Google Calendar on a computer → <em>Other calendars</em> → <em>+</em> →
  <em>From URL</em> and paste the feed URL. <strong>Google can take several hours (sometimes up to a day) to show
  a newly added calendar</strong>, and then refreshes it roughly once a day.<br>
  Outlook.com: <em>Add calendar</em> → <em>Subscribe from web</em> → paste the feed URL.<br>
  Troubleshooting: <a id="download" href="#" download>download the .ics</a> to import it once (shows
  immediately, but never updates) · <a id="validate" href="#">check the feed with an online validator</a></p>
</div>

<h2 id="today-title">Today</h2>
<div class="card" id="today"><p class="small">Loading…</p></div>

<p class="small">Want to check what the filter removed? See the <a href="report.html">review report</a>.
Text from Wikipedia's "On this day" pages, available under CC BY-SA 4.0.</p>
</main>
<script>
const feed = new URL("{ICS_NAME}", location.href);
const webcal = "webcal://" + feed.host + feed.pathname;
document.getElementById("url").textContent = feed.href;
document.getElementById("webcal").href = webcal;
document.getElementById("google").href = "https://www.google.com/calendar/render?cid=" + webcal;
document.getElementById("download").href = feed.href;
document.getElementById("validate").href = "https://icalendar.org/validator.html?url=" + encodeURIComponent(feed.href);
document.getElementById("copy").onclick = async (e) => {{
  try {{ await navigator.clipboard.writeText(feed.href); e.target.textContent = "Copied"; }}
  catch (_) {{ prompt("Copy the feed URL:", feed.href); }}
}};
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
const li = (i) => `<li><span class="yr">${{esc(i.year)}}</span> ${{i.url ? `<a href="${{esc(i.url)}}">${{esc(i.text)}}</a>` : esc(i.text)}}</li>`;
const now = new Date();
const mm = String(now.getMonth() + 1).padStart(2, "0");
const key = mm + "-" + String(now.getDate()).padStart(2, "0");
fetch(`days/${{mm}}.json`).then((r) => r.json()).then((days) => {{
  const d = days[key];
  document.getElementById("today-title").textContent = now.toLocaleDateString(undefined, {{ month: "long", day: "numeric" }});
  if (!d) {{ document.getElementById("today").innerHTML = "<p class='small'>No entry for today.</p>"; return; }}
  const block = (t, xs) => xs.length ? `<strong>${{t}}</strong><ul class="items">${{xs.map(li).join("")}}</ul>` : "";
  document.getElementById("today").innerHTML = block("Events", d.events) + block("Born", d.births) + block("Died", d.deaths);
}}).catch(() => {{ document.getElementById("today").innerHTML = "<p class='small'>Could not load today's entry.</p>"; }});
</script>
</body></html>
"""


def _row(day: str, c: Candidate, decision: str) -> str:
    cls = "keep" if decision == "kept" else "drop"
    text = _esc(c.text)
    if c.link:
        text = f'<a href="{_esc(c.link)}">{text}</a>'
    return (f"<tr><td>{_esc(_day_label(day))}</td><td>{_esc(c.section)}</td><td>{_esc(year_label(c.year))}</td>"
            f"<td>{text}</td><td class='why'><span class='pill {cls}'>{decision}</span> {_esc(c.why)}"
            f"{'' if 'fame' in c.why else f' · fame {c.fame}'}</td></tr>")


def _date_page(key: str) -> str:
    return f"https://en.wikipedia.org/wiki/{MONTHS[int(key[:2]) - 1]}_{int(key[3:])}"


def _counts_html(counts: dict[str, dict[str, int]], cfg: dict) -> str:
    if not counts:
        return ""
    def stat(kind: str) -> str:
        values = sorted((c[kind], k) for k, c in counts.items())
        lo, hi = values[0], values[-1]
        median = values[len(values) // 2][0]
        return (f"{kind}: median {median} per date (fewest {lo[0]} on {_esc(_day_label(lo[1]))}, "
                f"most {hi[0]} on {_esc(_day_label(hi[1]))})")
    cal = cfg["calendar"]
    rows = "".join(
        f"<tr><td>{_esc(_day_label(k))}</td><td>{c['events']}</td><td>{c['selected']}</td><td>{c['births']}</td>"
        f"<td>{c['deaths']}</td><td><a href='{_date_page(k)}'>Wikipedia article</a></td></tr>"
        for k, c in sorted(counts.items()))
    return f"""
<h2>Downloaded data</h2>
<p class="small">Everything listed under <em>Events</em>, <em>Births</em> and <em>Deaths</em> in each date's Wikipedia
article is downloaded (all sub-sections: pre-1600, 1601–1900, 1901–present), plus the 5 or so events Wikipedia's Main
Page picks for that date. The calendar then shows the top {cal["events_per_day"]} events, {cal["births_per_day"]} births
and {cal["deaths_per_day"]} deaths of each date (change this in <code>config.toml</code>).</p>
<p class="small">{stat("events")}<br>{stat("births")}<br>{stat("deaths")}</p>
<details><summary class="small">Counts for every date</summary>
<table><thead><tr><th>Date</th><th>Events</th><th>Main Page picks</th><th>Births</th><th>Deaths</th><th>Compare</th></tr></thead>
<tbody>{rows}</tbody></table></details>
"""


def report_html(days: list[DayResult], cfg: dict, generated: dt.datetime, notes: list[str],
                counts: dict[str, dict[str, int]] | None = None) -> str:
    removed = [(d.key, c) for d in days for c in d.removed]
    kept = [(d.key, c) for d in days for c in d.sensitive_kept]
    reasons = Counter(c.verdict.category if not c.override else "overrides.toml" for _, c in removed)
    stats = "".join(f"<span>{_esc(k)}: {v}</span>" for k, v in reasons.most_common())
    f = cfg["filter"]
    notes_html = "".join(f"<p class='small'>⚠ {_esc(n)}</p>" for n in notes)
    head = "<tr><th>Date</th><th>List</th><th>Year</th><th>Item</th><th>Decision</th></tr>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Filter review – {_esc(cfg["calendar"]["name"])}</title><style>{STYLE} main {{ max-width: 1100px; }}</style></head>
<body><main>
<h1>Filter review</h1>
<p class="lede">Built {generated:%Y-%m-%d %H:%M} UTC. Settings: war atrocities <b>{_esc(f["war_atrocities"])}</b>,
famous threshold <b>{f["famous_threshold"]}</b>, terrorism threshold <b>{f["terrorism_threshold"]}</b>.
"Fame" = number of Wikimedia sites with an article on the topic.</p>
{notes_html}
{_counts_html(counts or {}, cfg)}
<p class="small">Spot a mistake? Add the article title to <code>include_articles</code> or <code>exclude_articles</code> in
<code>overrides.toml</code> and push; the calendar rebuilds automatically.</p>
<input type="search" id="q" placeholder="Filter rows (e.g. a date, a word, a reason)">

<h2>Removed – would otherwise have appeared ({len(removed)})</h2>
<div class="stats">{stats}</div>
<table class="f"><thead>{head}</thead><tbody>
{"".join(_row(k, c, "removed") for k, c in removed)}
</tbody></table>

<h2>Kept although sensitive ({len(kept)})</h2>
<p class="small">Famous crimes, court cases, disasters, terrorism, war atrocities and political violence that passed the rules.</p>
<table class="f"><thead>{head}</thead><tbody>
{"".join(_row(k, c, "kept") for k, c in kept)}
</tbody></table>
</main>
<script>
document.getElementById("q").addEventListener("input", (e) => {{
  const q = e.target.value.toLowerCase();
  document.querySelectorAll("table.f tbody tr").forEach((tr) => {{
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none";
  }});
}});
</script>
</body></html>
"""


def write_site(out: Path, days: list[DayResult], ics_text: str, cfg: dict, generated: dt.datetime,
               notes: list[str], counts: dict[str, dict[str, int]] | None = None) -> dict[str, int]:
    files = {
        ICS_NAME: ics_text,
        "index.html": index_html(cfg),
        "report.html": report_html(days, cfg, generated, notes, counts),
        **days_json(days),
    }
    sizes = {}
    for name, content in files.items():
        data = content.encode("utf-8")
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(data)
        sizes[name] = len(data)
    return sizes
