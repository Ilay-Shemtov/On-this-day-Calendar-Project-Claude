"""Loads config.toml and overrides.toml (both optional) on top of built-in defaults."""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path

DEFAULTS: dict = {
    "calendar": {
        "name": "On This Day",
        "description": "Historical events, births and deaths from Wikipedia, every day.",
        "title_prefix": "\U0001F4DC ",  # scroll emoji + space
        "events_per_day": 5,
        "births_per_day": 3,
        "deaths_per_day": 3,
        "links": "events",  # "none" | "events" | "all"
        "max_per_topic": 2,
    },
    "filter": {
        "war_atrocities": "keep",  # "keep" | "drop"
        "famous_threshold": 20,
        "terrorism_threshold": 80,
    },
    "fetch": {
        "contact": "",
        "delay_seconds": 0.5,
    },
}

OVERRIDE_DEFAULTS: dict = {
    "include_articles": [],
    "exclude_articles": [],
    "exclude_phrases": [],
}


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(root: Path) -> dict:
    path = root / "config.toml"
    user = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    cfg = _merge(DEFAULTS, user)
    links = cfg["calendar"]["links"]
    if links not in ("none", "events", "all"):
        raise SystemExit(f'config.toml: calendar.links must be "none", "events" or "all" (got {links!r})')
    if cfg["filter"]["war_atrocities"] not in ("keep", "drop"):
        raise SystemExit('config.toml: filter.war_atrocities must be "keep" or "drop"')
    return cfg


def norm_title(title: str) -> str:
    return " ".join(title.replace("_", " ").split()).casefold()


def load_overrides(root: Path) -> dict:
    path = root / "overrides.toml"
    user = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    ov = _merge(OVERRIDE_DEFAULTS, user)
    return {
        "include": {norm_title(t) for t in ov["include_articles"]},
        "exclude": {norm_title(t) for t in ov["exclude_articles"]},
        "phrases": [p.casefold() for p in ov["exclude_phrases"] if p.strip()],
    }
