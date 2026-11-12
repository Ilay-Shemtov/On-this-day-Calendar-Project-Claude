"""Command line:

  python -m otd all                 fetch what's missing, then build site/ (what GitHub Actions runs)
  python -m otd fetch               only download into cache/
  python -m otd build               only build site/ from cache/
  python -m otd check "some text"   show how the filter treats an event line (add --person for births/deaths)

Options: --days 07-20,10-03 (limit to some dates, for quick local tests), --refresh (re-download),
         --cache DIR, --out DIR, --root DIR (where config.toml lives)
"""

from __future__ import annotations

import argparse
import datetime as dt
import statistics
import sys
import time
from pathlib import Path

from . import fetch
from .config import load_config, load_overrides
from .curate import curate_day, qids_needed
from .ics import build_calendar
from .sensitive import classify, decide
from .site import ICS_NAME, write_site

MAX_MISSING_DAYS = 5
SIZE_WARNING = 900_000
THIN_DAY = 20  # date articles normally list 40-100+ events; fewer suggests a parsing problem upstream  # some calendar apps reject subscriptions around 1 MB


def _days(arg: str | None) -> list[tuple[int, int]]:
    if not arg:
        return fetch.all_days()
    out = []
    for part in arg.split(","):
        month, day = part.strip().split("-")
        dt.date(2000, int(month), int(day))  # validates
        out.append((int(month), int(day)))
    return out


def cmd_fetch(args, cfg) -> int:
    ua = fetch.user_agent(cfg["fetch"]["contact"])
    days = _days(args.days)
    deadline = time.monotonic() + args.max_minutes * 60 if args.max_minutes else None
    failed = fetch.fetch_feed(args.cache, ua, days, refresh=args.refresh, delay=cfg["fetch"]["delay_seconds"],
                              deadline=deadline)
    if len(failed) > MAX_MISSING_DAYS:
        print(f"ERROR: {len(failed)} days are still missing. Run again to continue where this run stopped "
              f"(already downloaded days are kept).")
        return 1
    qids: set[str] = set()
    for month, day in days:
        data = fetch.load_day(args.cache, fetch.day_key(month, day))
        if data:
            qids |= qids_needed(data)
    fetch.fetch_sitelinks(args.cache, ua, qids)
    if failed:
        print(f"Warning: missing days {', '.join(failed)} (re-run later to fill them in)")
    return 0


def cmd_build(args, cfg) -> int:
    root = Path(args.root)
    overrides = load_overrides(root)
    sitelinks = fetch.load_sitelinks(args.cache)
    notes = []
    if not sitelinks:
        notes.append("No Wikidata fame scores were available, so ranking used a weak fallback and every "
                     "'kept if famous' item was removed. Re-run the build to retry.")
        sitelinks_arg = None
    else:
        sitelinks_arg = sitelinks
    results, missing, counts = [], [], {}
    for month, day in _days(args.days):
        key = fetch.day_key(month, day)
        data = fetch.load_day(args.cache, key)
        if data is None:
            missing.append(key)
            continue
        counts[key] = {kind: len(data.get(kind, [])) for kind in fetch.KINDS}
        results.append(curate_day(key, data, sitelinks_arg, cfg, overrides))
    if not results:
        print("Nothing to build: the cache is empty. Run `python -m otd fetch` first.")
        return 1
    if missing:
        shown = ", ".join(missing[:10]) + (f" and {len(missing) - 10} more" if len(missing) > 10 else "")
        notes.append(f"{len(missing)} dates without data (left out of the calendar): {shown}")
    thin = [k for k, c in counts.items() if c["events"] < THIN_DAY]
    if thin:
        notes.append(f"Fewer than {THIN_DAY} events were downloaded for {', '.join(thin)}. Every date's Wikipedia "
                     "article normally lists far more; compare with Wikipedia (see 'Downloaded data' below).")
    generated = dt.datetime.now(dt.timezone.utc)
    ics_text = build_calendar(results, cfg, now=generated)
    sizes = write_site(Path(args.out), results, ics_text, cfg, generated, notes, counts)
    print("Downloaded per date (median): " + ", ".join(
        f"{statistics.median(c[k] for c in counts.values()):.0f} {k}" for k in ("events", "births", "deaths")))

    removed = sum(len(r.removed) for r in results)
    flagged = sum(len(r.sensitive_kept) for r in results)
    print(f"Built {len(results)} days -> {Path(args.out) / ICS_NAME} ({sizes[ICS_NAME] / 1024:.0f} KB)")
    print(f"Filter: removed {removed} items that would have been shown; kept {flagged} sensitive-but-allowed items "
          f"(see report.html)")
    for note in notes:
        print("Note:", note)
    if sizes[ICS_NAME] > SIZE_WARNING:
        print("Warning: the calendar is close to 1 MB; consider fewer items per day or links = \"none\".")
    if len(missing) > MAX_MISSING_DAYS and not args.days:
        print(f"ERROR: {len(missing)} dates have no data.")
        return 1
    return 0


def cmd_check(args, cfg) -> int:
    kind = "births" if args.person else "events"
    pages = [{"title": d.split("=", 1)[0], "desc": d.split("=", 1)[1] if "=" in d else ""} for d in args.page]
    v = classify(kind, args.text, pages)
    keep, why = decide(v, args.fame, cfg)
    print(f"{'KEEP' if keep else 'DROP'}  [{v.action}] {why}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m otd", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["all", "fetch", "build", "check"])
    parser.add_argument("text", nargs="?", help="for `check`: the event text")
    parser.add_argument("--days", help="comma-separated MM-DD dates (default: all 366)")
    parser.add_argument("--refresh", action="store_true", help="re-download days already in the cache")
    parser.add_argument("--max-minutes", type=float, default=None,
                        help="stop downloading after this many minutes (a later run continues)")
    parser.add_argument("--cache", type=Path, default=Path("cache"))
    parser.add_argument("--out", default="site")
    parser.add_argument("--root", default=".")
    parser.add_argument("--person", action="store_true", help="for `check`: treat text as a births/deaths line")
    parser.add_argument("--page", action="append", default=[], metavar="TITLE=DESCRIPTION",
                        help="for `check`: a linked article and its short description (repeatable)")
    parser.add_argument("--fame", type=int, default=0, help="for `check`: fame score to assume")
    args = parser.parse_args(argv)
    cfg = load_config(Path(args.root))

    if args.command == "check":
        if not args.text:
            parser.error("check needs the text to classify")
        return cmd_check(args, cfg)
    if args.command in ("fetch", "all"):
        code = cmd_fetch(args, cfg)
        if code and args.command == "fetch":
            return code
        if code:
            print("Building with the data that is available...")
            cmd_build(args, cfg)
            return code
    if args.command in ("build", "all"):
        return cmd_build(args, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
