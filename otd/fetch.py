"""Downloads Wikipedia's "On this day" feed for all 366 dates and Wikidata fame scores.

Everything is cached under cache/ so re-runs only fetch what is missing:
  cache/feed/MM-DD.json   slimmed feed for one date
  cache/sitelinks.json    {"Q123": 57, ...}  number of Wikimedia sites with an article on the topic
"""

from __future__ import annotations

import datetime as dt
import email.utils
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

FEED_URLS = (
    "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{mm:02d}/{dd:02d}",
    # Older gateway; being phased out by Wikimedia, kept only as a fallback.
    "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/{mm:02d}/{dd:02d}",
)
WDQS_URL = "https://query.wikidata.org/sparql"
KINDS = ("selected", "events", "births", "deaths")
QID_RE = re.compile(r"^Q\d+$")


def all_days() -> list[tuple[int, int]]:
    """Every month/day pair of a leap year, so February 29 is included."""
    start = dt.date(2000, 1, 1)
    return [((start + dt.timedelta(d)).month, (start + dt.timedelta(d)).day) for d in range(366)]


def day_key(month: int, day: int) -> str:
    return f"{month:02d}-{day:02d}"


def user_agent(contact: str) -> str:
    """Wikimedia's User-Agent policy requires a way to contact the operator."""
    if not contact and os.environ.get("GITHUB_REPOSITORY"):
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        contact = f"{server}/{os.environ['GITHUB_REPOSITORY']}"
    if not contact:
        raise SystemExit(
            "Wikimedia requires contact details in the User-Agent.\n"
            'Set [fetch] contact = "you@example.com" (or a URL) in config.toml for local runs.'
        )
    return f"OnThisDayCalendar/1.0 ({contact}) python-urllib/{sys.version_info.major}.{sys.version_info.minor}"


class NotFound(Exception):
    pass


def _retry_after(headers) -> float | None:
    value = headers.get("Retry-After") if headers else None
    if not value:
        return None
    if value.strip().isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
        return max(0.0, (when - dt.datetime.now(dt.timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


def http_json(url: str, ua: str, *, data: bytes | None = None, accept: str = "application/json",
              timeout: float = 90, retries: int = 6) -> dict:
    headers = {"User-Agent": ua, "Accept": accept, "Accept-Encoding": "gzip"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    last_error: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return json.loads(body)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise NotFound(url) from err
            if err.code not in (429, 500, 502, 503, 504):
                raise
            last_error = err
            wait = _retry_after(err.headers) or min(300.0, 5.0 * 2 ** attempt)
            print(f"  HTTP {err.code} for {url} - waiting {wait:.0f}s", flush=True)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as err:
            last_error = err
            wait = min(300.0, 5.0 * 2 ** attempt)
            print(f"  {type(err).__name__} for {url} - retrying in {wait:.0f}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"giving up on {url}: {last_error}")


# ---------------------------------------------------------------------------- feed

def _slim_page(page: dict) -> dict | None:
    if not isinstance(page, dict):
        return None
    titles = page.get("titles") or {}
    title = (titles.get("normalized") or page.get("normalizedtitle") or page.get("title") or "").replace("_", " ")
    if not title:
        return None
    url = ((page.get("content_urls") or {}).get("desktop") or {}).get("page")
    if not url:
        url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
    return {
        "title": title,
        "qid": page.get("wikibase_item") or "",
        "desc": page.get("description") or "",
        "type": page.get("type") or "standard",
        "thumb": bool(page.get("thumbnail")),
        "url": url,
    }


def slim_feed(raw: dict) -> dict:
    out: dict = {}
    for kind in KINDS:
        items = []
        for item in raw.get(kind) or []:
            if not isinstance(item, dict) or not item.get("text"):
                continue
            pages = [p for p in (_slim_page(p) for p in item.get("pages") or []) if p]
            items.append({"year": item.get("year"), "text": " ".join(str(item["text"]).split()), "pages": pages})
        out[kind] = items
    return out


def fetch_feed(cache: Path, ua: str, days: list[tuple[int, int]], *, refresh: bool = False,
               delay: float = 0.5, deadline: float | None = None) -> list[str]:
    """Fetch missing days into cache/feed. Returns the keys of days that could not be fetched.

    `deadline` (a time.monotonic() value) stops fetching early; the cache keeps what was fetched.
    """
    feed_dir = cache / "feed"
    feed_dir.mkdir(parents=True, exist_ok=True)
    todo = [(m, d) for m, d in days if refresh or not (feed_dir / f"{day_key(m, d)}.json").exists()]
    print(f"Wikipedia feed: {len(days) - len(todo)} of {len(days)} days cached, fetching {len(todo)}", flush=True)
    failed = []
    for i, (month, day) in enumerate(todo, 1):
        if deadline is not None and time.monotonic() > deadline:
            rest = [day_key(m, d) for m, d in todo[i - 1:]]
            print(f"  time budget used up; {len(rest)} days left for the next run", flush=True)
            return failed + rest
        raw = None
        for template in FEED_URLS:
            url = template.format(mm=month, dd=day)
            try:
                raw = http_json(url, ua)
                break
            except (NotFound, RuntimeError, urllib.error.HTTPError) as err:
                print(f"  {day_key(month, day)}: {url} failed ({err})", flush=True)
        if raw is None:
            failed.append(day_key(month, day))
            continue
        slim = slim_feed(raw)
        tmp = feed_dir / f"{day_key(month, day)}.json.tmp"
        tmp.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
        tmp.replace(feed_dir / f"{day_key(month, day)}.json")
        if i % 25 == 0 or i == len(todo):
            print(f"  fetched {i}/{len(todo)} (last: {day_key(month, day)})", flush=True)
        time.sleep(delay)
    return failed


def load_day(cache: Path, key: str) -> dict | None:
    path = cache / "feed" / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------- fame

def load_sitelinks(cache: Path) -> dict[str, int]:
    path = cache / "sitelinks.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save_sitelinks(cache: Path, data: dict[str, int]) -> None:
    path = cache / "sitelinks.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def fetch_sitelinks(cache: Path, ua: str, qids: set[str], *, batch: int = 2500, delay: float = 1.0) -> bool:
    """Look up sitelink counts (how many Wikipedias etc. cover a topic) via the Wikidata Query Service.

    Returns False if the service could not be reached; the build then falls back to a weaker ranking.
    """
    known = load_sitelinks(cache)
    todo = sorted((q for q in qids if QID_RE.match(q) and q not in known), key=lambda q: int(q[1:]))
    print(f"Wikidata fame scores: {len(qids) - len(todo)} cached, looking up {len(todo)}", flush=True)
    ok = True
    for start in range(0, len(todo), batch):
        chunk = todo[start:start + batch]
        query = ("SELECT ?item ?n WHERE { VALUES ?item { " + " ".join(f"wd:{q}" for q in chunk)
                 + " } ?item wikibase:sitelinks ?n . }")
        try:
            res = http_json(WDQS_URL, ua, data=urllib.parse.urlencode({"query": query}).encode(),
                            accept="application/sparql-results+json", timeout=120)
        except (RuntimeError, NotFound, urllib.error.HTTPError) as err:
            print(f"  Wikidata lookup failed ({err}); continuing with partial scores", flush=True)
            ok = False
            break
        for row in res.get("results", {}).get("bindings", []):
            qid = row["item"]["value"].rsplit("/", 1)[-1]
            known[qid] = int(row["n"]["value"])
        for qid in chunk:
            known.setdefault(qid, 0)  # deleted or redirected items
        _save_sitelinks(cache, known)
        print(f"  scored {min(start + batch, len(todo))}/{len(todo)}", flush=True)
        time.sleep(delay)
    return ok
