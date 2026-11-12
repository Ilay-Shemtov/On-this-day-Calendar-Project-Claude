"""Scores, filters and picks the items shown for each day."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .config import norm_title
from .sensitive import Verdict, classify, clean_text, decide, is_generic, topic_prefix

# Wikipedia's Main Page "selected anniversaries" are picked for article quality and variety, not importance,
# so they get only a small edge (enough that their nicer wording wins when both lists have the same event).
SELECTED_BONUS = 1.2

# Titles of articles that are about one specific event.
EVENT_WORDS = re.compile(
    r"\b(?:Battle|Siege|Treaty|Accord|Agreement|Declaration|Conference|Summit|Massacre|Attacks?|Bombings?|Plot|"
    r"Crisis|Disaster|Earthquake|Cyclone|Hurricane|Election|Referendum|Landings?|Flight \d+|Expedition|Riots?|Coup|"
    r"Assassination|Incident|Affair|Trial|Raid|Invasion|Operation|Uprising|Rebellion|Revolution|Mutiny|Armistice)\b"
)
EVENTISH_TITLE = re.compile(
    r"\b(?:Battle|Siege|Treaty|Act|Accord|Agreement|Declaration|Conference|Summit|Revolution|Rebellion|Uprising|"
    r"War|Massacre|Attacks?|Bombings?|Plot|Crisis|Disaster|Fire|Earthquake|Election|Referendum|Landings?|Mission|"
    r"Flight|Expedition|Riots?|Coup|Assassination|Incident|Affair|Trial|Olympics|Games|Launch|Proclamation|Raid|"
    r"Invasion|Operation|Campaign|Movement|Strike|Boycott|March|Discovery|Founding|Independence)\b|\b\d{3,4}\b"
)
EVENTISH_DESC = re.compile(r"^\s*(?:c\.\s*)?\d{3,4}s?\b")


@dataclass
class Candidate:
    kind: str  # selected | events | births | deaths
    year: int | None
    text: str
    pages: list[dict]
    score: float = 0  # ranking: fame of the event's own article, or of its subject
    fame: int = 0  # filter: fame of the event's own article when there is one
    verdict: Verdict | None = None
    keep: bool = True
    why: str = ""
    override: str = ""
    topic: str | None = None
    link: str | None = None
    keys: frozenset = field(default_factory=frozenset)

    @property
    def section(self) -> str:
        return "events" if self.kind in ("selected", "events") else self.kind


def year_label(year: int | None) -> str:
    if year is None:
        return ""
    return f"{-year} BC" if year < 0 else str(year)


def _page_fame(page: dict, sitelinks: dict[str, int] | None) -> int:
    if sitelinks is None:  # Wikidata unavailable: weak fallback (articles with images tend to be bigger topics)
        return 3 if page.get("thumb") else 1
    return sitelinks.get(page.get("qid") or "", 0)


def _is_context_prefix(page: dict, year: int | None) -> bool:
    """'World War II: ...' on a 1941 event is context; '1973 Chilean coup d'état: ...' on a 1973 event is the event.

    A prefix article counts as the event itself when the event happens in its first year
    (its short description starts with that year, or its title contains it).
    """
    if year is None or year <= 0:
        return True
    desc = page.get("desc") or ""
    return not (re.match(rf"\s*(?:c\.\s*)?{year}\b", desc) or re.search(rf"\b{year}\b", page["title"]))


_STOP = {"the", "of", "and", "in", "on", "a", "an", "for", "to"}


def _words(s: str) -> set[str]:
    s = re.sub(r"\([^)]*\)", " ", s.casefold())
    return {w for w in re.findall(r"[\w']+", s) if w not in _STOP}


def _matches_prefix(title: str, prefix: str) -> bool:
    """'World War II' matches the label 'Second World War:'; 'Draft lottery (1969)' doesn't match 'Vietnam War:'."""
    if norm_title(title) == norm_title(prefix):
        return True
    t = _words(title)
    return bool(t) and len(t & _words(prefix)) * 2 >= len(t)


def _content_pages(text: str, pages: list[dict], year: int | None = None) -> list[dict]:
    """Pages that describe this specific item: not places/countries, not a 'World War II:'-style topic label."""
    pages = [p for p in pages if p.get("type") != "disambiguation"]
    prefix = topic_prefix(text)
    specific = [p for p in pages if not is_generic(p.get("desc") or "")]
    if prefix and len(specific) > 1:
        specific = [p for p in specific
                    if not (_matches_prefix(p["title"], prefix) and _is_context_prefix(p, year))] or specific
    return specific or pages


def _is_event_article(page: dict, year: int | None) -> bool:
    """An article about this very event: '1970 Bhola cyclone', 'Treaty of Rapallo (1920)', 'Operation Catechism'.

    Wikipedia's short descriptions of event articles usually start with the year ("1944 British air raid").
    Broad topics like 'Cold War' ("1947–1991 geopolitical rivalry") don't count unless the event is in their
    first year.
    """
    desc = page.get("desc") or ""
    if year is not None and year > 0:
        if re.match(rf"\s*(?:c\.\s*)?{year}\b", desc) or re.search(rf"\b{year}\b", page["title"]):
            return True
    return bool(EVENT_WORDS.search(page["title"])) and not re.match(r"\s*(?:c\.\s*)?\d{3,4}", desc)


def score_item(kind: str, text: str, pages: list[dict], sitelinks: dict[str, int] | None,
               year: int | None = None) -> int:
    """How important an item is: the fame of its own article, not of everything it mentions.

    Events: the article about the event itself if one is linked, otherwise the item's subject (the first
    specific link, e.g. "Leon Trotsky" in "Leon Trotsky is expelled from the Communist Party").
    A dredger launched "for the construction of the Panama Canal" is scored as the dredger, not the canal.
    """
    pages = [p for p in pages if p.get("type") != "disambiguation"]
    if not pages:
        return 0
    if kind in ("births", "deaths"):
        return _page_fame(pages[0], sitelinks)
    content = _content_pages(text, pages, year)
    events = [p for p in content if _is_event_article(p, year)]
    if events:
        return max(_page_fame(p, sitelinks) for p in events)
    return _page_fame(content[0], sitelinks)


def _event_pages(text: str, pages: list[dict], year: int | None) -> list[dict]:
    content = _content_pages(text, pages, year)
    return [p for p in content if EVENTISH_DESC.match(p.get("desc") or "") or EVENTISH_TITLE.search(p["title"])]


def gate_fame(kind: str, text: str, pages: list[dict], sitelinks: dict[str, int] | None, year: int | None) -> int:
    """Fame used for the 'kept if famous' rule: the event's own article when it has one.

    So O. J. Simpson's 1995 murder trial is judged by the trial article, and his much less known
    2008 robbery case by its own article, not by how famous O. J. Simpson himself is.
    """
    pages = [p for p in pages if p.get("type") != "disambiguation"]
    if kind not in ("births", "deaths"):
        events = _event_pages(text, pages, year)
        if events:
            return max(_page_fame(p, sitelinks) for p in events)
    return score_item(kind, text, pages, sitelinks, year)


def pick_link(kind: str, text: str, pages: list[dict], year: int | None = None) -> str | None:
    pages = [p for p in pages if p.get("type") != "disambiguation"]
    if not pages:
        return None
    if kind in ("births", "deaths"):
        return pages[0].get("url")
    content = _content_pages(text, pages, year)
    own = [p for p in content if _is_event_article(p, year)]
    return (own or _event_pages(text, pages, year) or content)[0].get("url")


def qids_needed(day: dict) -> set[str]:
    """Only the pages that are used for scoring need a Wikidata lookup."""
    out: set[str] = set()
    for kind in ("births", "deaths"):
        for item in day.get(kind, []):
            if item["pages"] and item["pages"][0].get("qid"):
                out.add(item["pages"][0]["qid"])
    for kind in ("selected", "events"):
        for item in day.get(kind, []):
            pages = [p for p in item["pages"] if p.get("type") != "disambiguation"]
            specific = [p for p in pages if not is_generic(p.get("desc") or "")] or pages
            out.update(p["qid"] for p in specific if p.get("qid"))
    return out


def _override(c: Candidate, overrides: dict) -> str:
    titles = {norm_title(p["title"]) for p in c.pages}
    if titles & overrides["exclude"] or any(ph in c.text.casefold() for ph in overrides["phrases"]):
        return "exclude"
    if titles & overrides["include"]:
        return "include"
    return ""


def build_candidates(day: dict, sitelinks: dict[str, int] | None, cfg: dict, overrides: dict) -> list[Candidate]:
    out = []
    for kind in ("selected", "events", "births", "deaths"):
        for item in day.get(kind, []):
            text = clean_text(item["text"])
            if not text:
                continue
            c = Candidate(kind, item.get("year"), text, item["pages"])
            c.score = score_item(kind, text, c.pages, sitelinks, c.year)
            c.fame = gate_fame(kind, text, c.pages, sitelinks, c.year)
            c.verdict = classify(kind, text, c.pages)
            c.keep, c.why = decide(c.verdict, c.fame, cfg)
            c.override = _override(c, overrides)
            if c.override:
                c.keep = c.override == "include"
                c.why = f"overrides.toml ({c.override})"
            prefix = topic_prefix(text)
            c.topic = norm_title(prefix) if prefix else None
            c.link = pick_link(kind, text, c.pages, c.year)
            c.keys = (frozenset(norm_title(p["title"]) for p in _content_pages(text, c.pages, c.year))
                      if c.section == "events" else frozenset())
            out.append(c)
    return out


def _rank(c: Candidate) -> float:
    return c.score * (SELECTED_BONUS if c.kind == "selected" else 1)


def select(cands: list[Candidate], section: str, n: int, max_per_topic: int, *, use_filter: bool = True) -> list[Candidate]:
    pool = sorted((c for c in cands if c.section == section), key=_rank, reverse=True)
    chosen: list[Candidate] = []
    topics: Counter = Counter()
    for c in pool:
        if len(chosen) >= n:
            break
        if use_filter and not c.keep:
            continue
        if section == "events":
            if any(c.year == o.year and (c.keys & o.keys or c.text == o.text) for o in chosen):
                continue  # same event listed in both "selected" and "events"
            if c.topic and topics[c.topic] >= max_per_topic:
                continue
            if c.topic:
                topics[c.topic] += 1
        elif any(c.text == o.text for o in chosen):
            continue
        chosen.append(c)
    return chosen


@dataclass
class DayResult:
    key: str  # MM-DD
    events: list[Candidate]
    births: list[Candidate]
    deaths: list[Candidate]
    headline: Candidate | None
    removed: list[Candidate]  # filtered out although they would have been picked
    sensitive_kept: list[Candidate]  # picked although flagged (famous, war atrocity, override...)


def curate_day(key: str, day: dict, sitelinks: dict[str, int] | None, cfg: dict, overrides: dict) -> DayResult:
    cal = cfg["calendar"]
    cands = build_candidates(day, sitelinks, cfg, overrides)
    counts = {"events": cal["events_per_day"], "births": cal["births_per_day"], "deaths": cal["deaths_per_day"]}
    picked, removed, flagged = {}, [], []
    for section, n in counts.items():
        chosen = select(cands, section, n, cal["max_per_topic"])
        unfiltered = select(cands, section, n, cal["max_per_topic"], use_filter=False)
        picked[section] = chosen
        removed += [c for c in unfiltered if not c.keep]
        flagged += [c for c in chosen if c.override == "include" or c.verdict.action in ("gate", "atrocity")
                    or c.verdict.category == "political violence"]
    events = picked["events"]
    headline = events[0] if events else (picked["births"][0] if picked["births"] else None)
    by_year = lambda c: (c.year if c.year is not None else 10**6)
    return DayResult(
        key=key,
        events=sorted(events, key=by_year),
        births=sorted(picked["births"], key=by_year),
        deaths=sorted(picked["deaths"], key=by_year),
        headline=headline,
        removed=removed,
        sensitive_kept=flagged,
    )
