"""Fetcher against a local fake of the Wikipedia feed and Wikidata Query Service (no internet needed).

The fake returns responses shaped like the real API (page summaries with titles.normalized,
wikibase_item, description, content_urls...), gzip-compressed, and starts with an HTTP 429
to exercise the retry logic.
"""

import gzip
import json
import re
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from otd import fetch


def summary(title, qid, desc):
    return {
        "type": "standard", "title": title.replace(" ", "_"), "displaytitle": title,
        "namespace": {"id": 0, "text": ""}, "wikibase_item": qid,
        "titles": {"canonical": title.replace(" ", "_"), "normalized": title, "display": title},
        "pageid": 1, "thumbnail": {"source": "https://upload.wikimedia.org/x.jpg", "width": 320, "height": 200},
        "lang": "en", "dir": "ltr", "revision": "1", "tid": "x", "timestamp": "2026-01-01T00:00:00Z",
        "description": desc, "description_source": "local",
        "content_urls": {"desktop": {"page": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"}},
        "extract": "…", "extract_html": "<p>…</p>", "normalizedtitle": title,
    }


FEED = {
    "selected": [{"text": "Apollo 11 astronauts Neil Armstrong and Buzz Aldrin become the first people to walk on the Moon.",
                  "year": 1969, "pages": [summary("Apollo 11", "Q43653", "First crewed Moon landing (1969)"),
                                          summary("Neil Armstrong", "Q1615", "American astronaut (1930–2012)")]}],
    "events": [{"text": "World War II: Claus von Stauffenberg fails to assassinate Adolf Hitler.", "year": 1944,
                "pages": [summary("World War II", "Q362", "1939–1945 global conflict"),
                          summary("20 July plot", "Q160088", "1944 attempt to assassinate Adolf Hitler")]}],
    "births": [{"text": "Gregor Mendel, Austrian-Czech scientist (d. 1884)", "year": 1822,
                "pages": [summary("Gregor Mendel", "Q5598", "Austrian-Czech scientist (1822–1884)")]}],
    "deaths": [{"text": "Bruce Lee, American-Hong Kong actor and martial artist (b. 1940)", "year": 1973,
                "pages": [summary("Bruce Lee", "Q16397", "Hong Kong-American actor (1940–1973)")]}],
    "holidays": [{"text": "Moon Day", "pages": []}],
}
SITELINKS = {"Q43653": 120, "Q1615": 110, "Q362": 280, "Q160088": 60, "Q5598": 105, "Q16397": 140}


class Fake(BaseHTTPRequestHandler):
    hits = {"feed": 0, "sparql": 0}
    user_agents = []

    def log_message(self, *args):
        pass

    def _send(self, code, body: bytes, headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Fake.user_agents.append(self.headers.get("User-Agent", ""))
        m = re.match(r"^/feed/onthisday/all/(\d\d)/(\d\d)$", self.path)
        if not m:
            return self._send(404, b"{}")
        Fake.hits["feed"] += 1
        if Fake.hits["feed"] == 1:
            return self._send(429, b"slow down", {"Retry-After": "1"})
        body = gzip.compress(json.dumps(FEED).encode())
        self._send(200, body, {"Content-Type": "application/json", "Content-Encoding": "gzip"})

    def do_POST(self):
        Fake.hits["sparql"] += 1
        Fake.user_agents.append(self.headers.get("User-Agent", ""))
        form = urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        qids = re.findall(r"wd:(Q\d+)", form["query"][0])
        rows = [{"item": {"value": f"http://www.wikidata.org/entity/{q}"}, "n": {"value": str(SITELINKS[q])}}
                for q in qids if q in SITELINKS]
        self._send(200, json.dumps({"results": {"bindings": rows}}).encode(),
                   {"Content-Type": "application/sparql-results+json"})


class TestFetch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_feed_and_sitelinks(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(fetch, "FEED_URLS", (self.base + "/feed/onthisday/all/{mm:02d}/{dd:02d}",)), \
                mock.patch.object(fetch, "WDQS_URL", self.base + "/sparql"), \
                mock.patch.object(fetch.time, "sleep", lambda s: None):
            cache = Path(tmp)
            ua = fetch.user_agent("test@example.com")
            failed = fetch.fetch_feed(cache, ua, [(7, 20), (2, 29)], delay=0)
            self.assertEqual(failed, [])
            day = fetch.load_day(cache, "07-20")
            self.assertEqual(set(day), {"selected", "events", "births", "deaths"})
            page = day["selected"][0]["pages"][0]
            self.assertEqual(page, {"title": "Apollo 11", "qid": "Q43653", "desc": "First crewed Moon landing (1969)",
                                    "type": "standard", "thumb": True, "url": "https://en.wikipedia.org/wiki/Apollo_11"})
            self.assertTrue((cache / "feed" / "02-29.json").exists())

            # second run: nothing re-downloaded
            before = Fake.hits["feed"]
            fetch.fetch_feed(cache, ua, [(7, 20), (2, 29)], delay=0)
            self.assertEqual(Fake.hits["feed"], before)

            from otd.curate import qids_needed
            ok = fetch.fetch_sitelinks(cache, ua, qids_needed(day), batch=2, delay=0)
            self.assertTrue(ok)
            links = fetch.load_sitelinks(cache)
            self.assertEqual(links["Q43653"], 120)
            self.assertEqual(links["Q5598"], 105)
            self.assertTrue(all("test@example.com" in ua for ua in Fake.user_agents))

    def test_time_budget_stops_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(fetch, "FEED_URLS", (self.base + "/feed/onthisday/all/{mm:02d}/{dd:02d}",)):
            before = Fake.hits["feed"]
            left = fetch.fetch_feed(Path(tmp), "ua (test@example.com)", [(1, 1), (1, 2)], delay=0,
                                    deadline=fetch.time.monotonic() - 1)
            self.assertEqual(left, ["01-01", "01-02"])
            self.assertEqual(Fake.hits["feed"], before)

    def test_user_agent_requires_contact(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit):
                fetch.user_agent("")
        with mock.patch.dict("os.environ", {"GITHUB_REPOSITORY": "someone/on-this-day"}, clear=True):
            self.assertIn("https://github.com/someone/on-this-day", fetch.user_agent(""))


if __name__ == "__main__":
    unittest.main()
