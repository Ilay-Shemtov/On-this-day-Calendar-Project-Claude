"""End-to-end: build the site from tests/fixtures/cache and check the calendar file.

The fixture cache holds the real December 1 page plus hand-made days; fame numbers are estimates.
"""

import datetime as dt
import json
import re
import tempfile
import unittest
from pathlib import Path

from otd.__main__ import main

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "cache"
DAYS = "01-24,02-29,04-20,09-11,10-03,12-01"


def unfold(ics: str) -> str:
    return ics.replace("\r\n ", "")


class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / "site"
        code = main(["build", "--cache", str(FIXTURES), "--out", str(out), "--days", DAYS, "--root", str(ROOT)])
        assert code == 0
        cls.out = out
        cls.raw = (out / "on-this-day.ics").read_bytes()
        cls.text = unfold(cls.raw.decode("utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_files(self):
        for name in ("on-this-day.ics", "index.html", "report.html", "days/12.json", "days/02.json"):
            self.assertTrue((self.out / name).exists(), name)

    def test_rfc5545_basics(self):
        lines = self.raw.split(b"\r\n")
        self.assertLessEqual(max(len(line) for line in lines), 75, "lines must be folded at 75 octets")
        self.assertNotIn(b"\n", self.raw.replace(b"\r\n", b""), "only CRLF line endings")
        self.assertTrue(self.text.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0"))
        self.assertEqual(self.text.count("BEGIN:VEVENT"), 6)
        self.assertEqual(self.text.count("RRULE:FREQ=YEARLY"), 6)
        self.assertIn("DTSTART;VALUE=DATE:20000229", self.text)
        uids = re.findall(r"^UID:(.+)$", self.text, re.M)
        self.assertEqual(len(uids), len(set(uids)))

    def test_filter_outcomes(self):
        text = self.text.replace("\\,", ",").replace("\\;", ";")
        self.assertNotIn("Columbine", text)
        self.assertNotIn("Ted Bundy", text)
        self.assertNotIn("Eric Harris", text)
        self.assertNotIn("armed robbery", text)  # O. J. Simpson's lesser-known 2008 case
        self.assertIn("acquitted of the murders", text)  # ...but the famous 1995 verdict stays
        self.assertIn("September 11 attacks", text)
        self.assertIn("Adolf Hitler", text)  # births of historical figures are history

    def test_days_json(self):
        days = {}
        for path in (self.out / "days").glob("*.json"):
            days.update(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(set(days), set(DAYS.split(",")))
        self.assertTrue(days["12-01"]["headline"]["text"])

    def test_with_icalendar_if_installed(self):
        try:
            import icalendar
            import recurring_ical_events
        except ImportError:
            self.skipTest("pip install icalendar recurring-ical-events for this check")
        cal = icalendar.Calendar.from_ical(self.raw)
        counts = {}
        for year in (2026, 2027, 2028):
            occ = recurring_ical_events.of(cal).between(dt.date(year, 1, 1), dt.date(year + 1, 1, 1))
            counts[year] = len(occ)
        self.assertEqual(counts, {2026: 5, 2027: 5, 2028: 6})  # Feb 29 only in leap years


if __name__ == "__main__":
    unittest.main()
