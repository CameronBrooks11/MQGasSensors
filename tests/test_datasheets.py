"""Tests for scripts/datasheets.py. No network: a local server plays the mirrors."""
import hashlib
import http.server
import io
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import datasheets  # noqa: E402

GOOD = b"%PDF-1.4\n" + b"the real datasheet " * 200
OTHER_EDITION = b"%PDF-1.4\n" + b"another edition!!! " * 200  # same length, other content
HTML = b"<html><body>Just a moment...</body></html>"


class Mirror(http.server.BaseHTTPRequestHandler):
    hits = {}
    flaky_failures = 2

    def log_message(self, *args):
        pass

    def do_GET(self):
        n = Mirror.hits[self.path] = Mirror.hits.get(self.path, 0) + 1
        body, status = {
            "/good": (GOOD, 200),
            "/good2": (GOOD, 200),
            "/other-edition": (OTHER_EDITION, 200),
            "/html": (HTML, 200),
            "/truncated": (GOOD[:-385], 200),
            "/missing": (b"not found", 404),
            "/down": (b"bad gateway", 502),
            "/flaky": (GOOD, 200) if n > Mirror.flaky_failures else (b"bad gateway", 502),
        }[self.path]
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class DatasheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Mirror)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Mirror.hits = {}
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "files"
        self.addCleanup(self.tmp.cleanup)

    def entry(self, *paths):
        return {
            "id": "mq-test", "sensor": "MQ-0", "maker": "Test", "edition": "test",
            "bytes": len(GOOD), "sha256": hashlib.sha256(GOOD).hexdigest(),
            "mirrors": [{"kind": "live", "url": self.base + p} for p in paths],
        }

    def run_fetch(self, *paths, retries=3):
        out = io.StringIO()
        code = datasheets.fetch([self.entry(*paths)], self.dest, retries, 0, 5, out=out)
        return code, out.getvalue()

    def assert_fetched(self):
        self.assertEqual((self.dest / "mq-test.pdf").read_bytes(), GOOD)

    def assert_nothing_left(self):
        self.assertEqual([p.name for p in self.dest.iterdir()], [])

    def test_first_mirror_serves_the_file(self):
        code, out = self.run_fetch("/good", "/good2")
        self.assertEqual(code, 0)
        self.assert_fetched()
        self.assertIn("mirror 1/2", out)
        self.assertNotIn("/good2", Mirror.hits)

    def test_dead_mirror_falls_through_to_the_next(self):
        code, out = self.run_fetch("/missing", "/good")
        self.assertEqual(code, 0)
        self.assert_fetched()
        self.assertIn("mirror 2/2", out)
        self.assertIn("HTTP 404", out)

    def test_client_error_is_not_retried(self):
        self.run_fetch("/missing", "/good")
        self.assertEqual(Mirror.hits["/missing"], 1)

    def test_html_page_answering_200_is_rejected(self):
        code, out = self.run_fetch("/html", "/good")
        self.assertEqual(code, 0)
        self.assert_fetched()
        self.assertIn("not a PDF", out)

    def test_truncated_copy_is_rejected(self):
        code, out = self.run_fetch("/truncated", "/good")
        self.assertEqual(code, 0)
        self.assert_fetched()
        self.assertIn(f"expected {len(GOOD)}", out)

    def test_another_edition_of_the_same_size_is_rejected(self):
        code, out = self.run_fetch("/other-edition", "/good")
        self.assertEqual(code, 0)
        self.assert_fetched()
        self.assertIn("different content", out)

    def test_server_error_is_retried_before_falling_through(self):
        code, out = self.run_fetch("/flaky", "/good", retries=3)
        self.assertEqual(code, 0)
        self.assert_fetched()
        self.assertEqual(Mirror.hits["/flaky"], 3)
        self.assertIn("mirror 1/2", out)
        self.assertNotIn("/good", Mirror.hits)

    def test_retries_are_bounded(self):
        code, _ = self.run_fetch("/down", retries=3)
        self.assertEqual(code, 1)
        self.assertEqual(Mirror.hits["/down"], 3)

    def test_no_good_mirror_fails_and_leaves_nothing_behind(self):
        code, out = self.run_fetch("/html", "/truncated", "/other-edition", "/missing")
        self.assertEqual(code, 1)
        self.assertIn("FAILED", out)
        self.assert_nothing_left()

    def test_verified_file_on_disk_is_not_downloaded_again(self):
        self.dest.mkdir()
        (self.dest / "mq-test.pdf").write_bytes(GOOD)
        code, out = self.run_fetch("/good")
        self.assertEqual(code, 0)
        self.assertIn("already present", out)
        self.assertEqual(Mirror.hits, {})

    def test_wrong_file_on_disk_is_replaced(self):
        self.dest.mkdir()
        (self.dest / "mq-test.pdf").write_bytes(OTHER_EDITION)
        code, _ = self.run_fetch("/good")
        self.assertEqual(code, 0)
        self.assert_fetched()

    def test_verify_checks_every_mirror(self):
        out = io.StringIO()
        code = datasheets.verify([self.entry("/good", "/html", "/good2")], 1, 0, 5, out=out)
        self.assertEqual(code, 0)
        self.assertEqual(set(Mirror.hits), {"/good", "/html", "/good2"})
        self.assertIn("1 with a failing mirror", out.getvalue())

    def test_verify_fails_when_no_mirror_works(self):
        out = io.StringIO()
        code = datasheets.verify([self.entry("/html", "/missing")], 1, 0, 5, out=out)
        self.assertEqual(code, 1)
        self.assertIn("DEAD", out.getvalue())


class ManifestTests(unittest.TestCase):
    def load(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(text)
        self.addCleanup(Path(f.name).unlink)
        return datasheets.load_manifest(f.name)

    def manifest(self, sha="a" * 64, mirrors='[{ kind = "wayback", url = "http://x/" }]', extra=""):
        one = (f'[[datasheet]]\nid = "a"\nsensor = "MQ-0"\nmaker = "T"\nedition = "t"\n'
               f'bytes = 10\nsha256 = "{sha}"\nmirrors = {mirrors}\n')
        return one + extra

    def test_valid_manifest_loads(self):
        self.assertEqual(len(self.load(self.manifest())), 1)

    def test_short_hash_is_refused(self):
        with self.assertRaises(datasheets.ManifestError):
            self.load(self.manifest(sha="abc123"))

    def test_duplicate_id_is_refused(self):
        with self.assertRaises(datasheets.ManifestError):
            self.load(self.manifest(extra=self.manifest()))

    def test_unknown_mirror_kind_is_refused(self):
        with self.assertRaises(datasheets.ManifestError):
            self.load(self.manifest(mirrors='[{ kind = "torrent", url = "http://x/" }]'))

    def test_github_mirror_must_be_last(self):
        with self.assertRaises(datasheets.ManifestError):
            self.load(self.manifest(mirrors='[{ kind = "github", url = "http://g/" }, { kind = "live", url = "http://x/" }]'))

    def test_repository_manifest_is_valid(self):
        entries = datasheets.load_manifest(ROOT / "datasheets" / "manifest.toml")
        self.assertEqual(len(entries), 18)
        for e in entries:
            self.assertEqual(e["mirrors"][0]["kind"], "wayback", e["id"])
            self.assertGreaterEqual(len(e["mirrors"]), 3, e["id"])
            for m in e["mirrors"]:
                if m["kind"] == "wayback":
                    self.assertIn("id_/", m["url"], e["id"])
                if m["kind"] == "swh":
                    self.assertIn(e["sha256"], m["url"], e["id"])


if __name__ == "__main__":
    unittest.main()
