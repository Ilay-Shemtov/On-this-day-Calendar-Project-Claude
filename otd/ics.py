"""Writes an RFC 5545 iCalendar file: one all-day, yearly-recurring event per date."""

from __future__ import annotations

import datetime as dt

from .curate import Candidate, DayResult, year_label

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def escape(value: str) -> str:
    return (value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\n").replace("\n", "\\n"))


def fold(line: str) -> str:
    """Fold to 75 octets per line without splitting UTF-8 characters (RFC 5545 section 3.1)."""
    if len(line.encode("utf-8")) <= 75:
        return line
    parts, current, size, limit = [], [], 0, 75
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > limit:
            parts.append("".join(current))
            current, size, limit = [], 0, 74  # continuation lines start with one space
        current.append(ch)
        size += n
    parts.append("".join(current))
    return "\r\n ".join(parts)


def shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:–- ")
    return cut + "…"


def first_sentences(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    head = text[:limit]
    end = max(head.rfind(". "), head.rfind("; "))
    return head[: end + 1] if end > 60 else shorten(text, limit)


def date_page_url(key: str) -> str:
    month, day = int(key[:2]), int(key[3:])
    return f"https://en.wikipedia.org/wiki/{MONTHS[month - 1]}_{day}"


def _line(c: Candidate, with_link: bool) -> list[str]:
    out = [f"• {year_label(c.year)} – {first_sentences(c.text)}"]
    if with_link and c.link:
        out.append(f"  {c.link}")
    return out


def description(day: DayResult, links: str) -> str:
    lines: list[str] = []
    sections = (("EVENTS", day.events, links in ("events", "all")),
                ("BORN", day.births, links == "all"),
                ("DIED", day.deaths, links == "all"))
    for title, items, with_link in sections:
        if items:
            if lines:
                lines.append("")
            lines.append(title)
            for c in items:
                lines += _line(c, with_link)
    lines += ["", f"More: {date_page_url(day.key)}", "Source: Wikipedia (CC BY-SA 4.0)"]
    return "\n".join(lines)


def summary(day: DayResult, prefix: str) -> str:
    h = day.headline
    if h is None:
        return f"{prefix}On this day"
    if h.section == "births":
        return shorten(f"{prefix}Born {year_label(h.year)}: {h.text}", 90)
    return shorten(f"{prefix}{year_label(h.year)} · {h.text}", 90)


def build_calendar(days: list[DayResult], cfg: dict, *, now: dt.datetime | None = None) -> str:
    cal = cfg["calendar"]
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    out = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//on-this-day-calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape(cal['name'])}",
        f"X-WR-CALDESC:{escape(cal['description'])}",
        "REFRESH-INTERVAL;VALUE=DURATION:P1W",
        "X-PUBLISHED-TTL:P1W",
    ]
    for day in days:
        month, dom = int(day.key[:2]), int(day.key[3:])
        start = dt.date(2000, month, dom)  # 2000 is a leap year, so Feb 29 exists (it then shows in leap years only)
        end = start + dt.timedelta(days=1)
        out += [
            "BEGIN:VEVENT",
            f"UID:otd-{day.key}@on-this-day-calendar",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
            f"DTEND;VALUE=DATE:{end:%Y%m%d}",
            "RRULE:FREQ=YEARLY",
            f"SUMMARY:{escape(summary(day, cal['title_prefix']))}",
            f"DESCRIPTION:{escape(description(day, cal['links']))}",
            f"URL:{date_page_url(day.key)}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    out.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in out) + "\r\n"
