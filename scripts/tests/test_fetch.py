import unittest

from helpers import FakeClock, FakeServer, TmpCase, tribunais, unid
import fetch
from common import read_gz
from dgsi_html import page_ok


class Fetch(TmpCase):
    def setUp(self):
        super().setUp()
        self.clock = FakeClock()
        self.server = FakeServer(self.clock, per_page=3)
        self.raw = fetch.Raw(self.tmp / "raw")
        self.logs = []

    def go(self, mode, only=None, limit=None, budget=None, ids=("stj", "jp"), client=None):
        self.client = client or self.server.client()
        return fetch.run_fetch(self.client, self.raw, tribunais(*ids), mode, only, limit, budget, workers=1,
                               now=self.clock, log=self.logs.append)

    def test_initial_lists_everything_and_caches_every_page_whole(self):
        self.server.add("jstj", 7)
        self.server.add("cajp", 4, start=100)
        self.assertEqual(self.go("initial"), 0)
        lst = self.raw.read_list("jstj")
        self.assertTrue(lst["complete"])
        self.assertEqual(len(lst["rows"]), 7)
        self.assertEqual(lst["expected"], 7)
        self.assertEqual(len(self.raw.read_list("cajp")["rows"]), 4)
        self.assertEqual(len(self.raw.pages("jstj")), 7)
        row = lst["rows"][unid(1)]
        self.assertEqual(row["processo"], "1/20.1T8LSB")
        self.assertEqual(row["data"], "2026-10-27")  # month/day/year converted
        body = read_gz(self.raw.page_path("jstj", unid(1)))
        self.assertIn(b"Texto integral inventado.", body)  # the whole page is kept, long text included
        # long texts only come with ExpandSection=1
        pages = [u for u in self.server.urls("OpenDocument")]
        self.assertEqual(len(pages), 11)
        self.assertTrue(all(u.endswith("?OpenDocument&ExpandSection=1") for u in pages))

    def test_second_run_makes_no_requests(self):
        self.server.add("jstj", 7)
        self.go("initial", ids=("stj",))
        n = len(self.server.requests)
        self.assertEqual(self.go("initial", ids=("stj",)), 0)
        self.assertEqual(len(self.server.requests), n)

    def test_resume_after_errors_skips_what_is_cached(self):
        self.server.add("jstj", 7)
        self.server.errors[unid(4)] = [500, 500, 500]
        self.assertEqual(self.go("initial", ids=("stj",)), 1)
        self.assertTrue(any("STOPPED" in m for m in self.logs))
        done = {p.name for p in self.raw.pages("jstj")}
        self.assertEqual(len(done), 3)  # decisions 1-3 were fetched before the failure
        self.server.requests.clear()
        self.assertEqual(self.go("initial", ids=("stj",)), 0)
        refetched = [u for u in self.server.urls("OpenDocument")]
        self.assertEqual(len(refetched), 4)
        self.assertFalse(any(unid(1) in u or unid(2) in u or unid(3) in u for u in refetched))
        self.assertEqual(len(self.raw.pages("jstj")), 7)

    def test_unfinished_list_continues_where_it_stopped(self):
        self.server.add("jstj", 9)
        self.go("initial", ids=("stj",), limit=2)  # stops listing early
        self.assertFalse(self.raw.read_list("jstj")["complete"])
        self.server.requests.clear()
        self.go("initial", ids=("stj",))
        self.assertTrue(self.raw.read_list("jstj")["complete"])
        self.assertEqual(len(self.raw.read_list("jstj")["rows"]), 9)
        self.assertFalse(any(u.endswith("OpenDatabase&Start=1") for u in self.server.urls("OpenDatabase")))  # did not start over

    def test_limit_is_split_between_databases_and_db_selects_one(self):
        self.server.add("jstj", 20)
        self.server.add("cajp", 20, start=100)
        self.go("initial", limit=6)
        self.assertEqual(len(self.raw.pages("jstj")), 3)
        self.assertEqual(len(self.raw.pages("cajp")), 3)
        self.server.requests.clear()
        self.go("initial", only="cajp", limit=2)
        self.assertEqual({u.split(".nsf")[0] for u in self.server.urls("dgsi")}, {"https://www.dgsi.pt/cajp"})

    def test_time_budget_returns_2_and_the_next_run_finishes(self):
        self.server.add("jstj", 30)
        rc = self.go("initial", ids=("stj",), budget=3)
        self.assertEqual(rc, 2)
        self.assertLess(len(self.raw.pages("jstj")), 30)
        self.assertEqual(self.go("initial", ids=("stj",)), 0)
        self.assertEqual(len(self.raw.pages("jstj")), 30)

    def test_error_page_with_status_200_counts_as_an_error(self):
        self.assertFalse(page_ok(b"<html><body>Error 500 Server Error</body></html>"))
        self.assertFalse(page_ok(b"<html><body><table><tr><td bgcolor='#71B2CF'>Processo:</td><td>1/20</td></tr></table>"))  # cut off
        self.server.add("jstj", 3)
        orig = self.server.transport
        self.server.transport = lambda url, h: (200, b"<html>Server Error</html>") if "OpenDocument&Expand" in url else orig(url, h)
        self.assertEqual(self.go("initial", ids=("stj",)), 1)
        self.assertEqual(len(self.raw.pages("jstj")), 0)

    def test_a_deleted_decision_is_noted_and_skipped(self):
        self.server.add("jstj", 4)
        self.server.errors[unid(2)] = [404]
        self.assertEqual(self.go("initial", ids=("stj",)), 0)
        self.assertEqual(len(self.raw.pages("jstj")), 3)
        self.assertIn(unid(2), (self.raw.root / "missing.txt").read_text())

    def test_progress_line_every_500_requests(self):
        self.server.per_page = 100
        self.server.add("jstj", 1100)
        self.go("initial", ids=("stj",))
        lines = [m for m in self.logs if "requests" in m and m.startswith("[")]
        self.assertTrue(any(" 500 requests" in m for m in lines) or any("5" in m for m in lines))
        counts = sorted({int(m.split("] ")[1].split(" ")[0]) for m in lines})
        self.assertTrue(all(c // 500 == i + 1 for i, c in enumerate(counts)), counts)  # one line per 500
        self.assertGreaterEqual(len(counts), 2)

    def test_slow_responses_during_a_fetch_are_logged_and_lower_the_rate(self):
        self.server.add("jstj", 6)
        self.server.delay[unid(2)] = 6.0
        c = self.server.client()
        msgs = []
        c._log = msgs.append
        self.go("initial", ids=("stj",), client=c)
        self.assertEqual(c.level, 1)
        self.assertTrue(any("dropped to 2 requests/s" in m for m in msgs))


class Weekly(TmpCase):
    def setUp(self):
        super().setUp()
        self.clock = FakeClock()
        self.server = FakeServer(self.clock, per_page=3)
        self.raw = fetch.Raw(self.tmp / "raw")

    def go(self, mode, ids=("stj",)):
        self.server.requests.clear()
        return fetch.run_fetch(self.server.client(), self.raw, tribunais(*ids), mode, None, None, None, workers=1, now=self.clock,
                               log=lambda m: None)

    def listing_starts(self, db="jstj"):
        return [int(u.rsplit("=", 1)[1]) for u in self.server.urls(f"/{db}.nsf?OpenDatabase")]

    def test_stops_at_the_first_listing_page_whose_decisions_are_all_cached(self):
        self.server.add("jstj", 6, start=10)  # 2 listing pages
        self.go("initial")
        new = [{"unid": unid(1), "processo": "1/26.1T8LSB", "relator": "X", "data": "10/21/2026", "descritores": ["A"]},
               {"unid": unid(2), "processo": "2/26.1T8LSB", "relator": "X", "data": "10/21/2026", "descritores": ["A"]}]
        self.server.dbs["jstj"] = new + self.server.dbs["jstj"]  # pages: [n1 n2 o1] [o2 o3 o4] [o5 o6]
        self.assertEqual(self.go("weekly"), 0)
        self.assertEqual(self.listing_starts(), [1, 4])  # page 1 has news, page 2 is all cached: stop, page 3 never asked
        fetched = self.server.urls("OpenDocument")
        self.assertEqual(len(fetched), 2)
        self.assertTrue(self.raw.has_page("jstj", unid(1)) and self.raw.has_page("jstj", unid(2)))
        rows = list(self.raw.read_list("jstj")["rows"])
        self.assertEqual(rows[:2], [unid(1), unid(2)])  # newest first
        self.assertEqual(len(rows), 8)

    def test_nothing_new_costs_one_listing_request(self):
        self.server.add("jstj", 6)
        self.go("initial")
        self.assertEqual(self.go("weekly"), 0)
        self.assertEqual(len(self.server.requests), 1)

    def test_news_on_several_pages_are_all_fetched(self):
        self.server.add("jstj", 3, start=100)
        self.go("initial")
        self.server.dbs["jstj"] = [{"unid": unid(k), "processo": f"{k}/26.1T8LSB", "relator": "X", "data": "10/21/2026", "descritores": []}
                                   for k in range(1, 8)] + self.server.dbs["jstj"]
        self.go("weekly")
        self.assertEqual(self.listing_starts(), [1, 4, 7, 10])  # pages 1-3 have news; page 4 (old ones) is all cached
        self.assertEqual(len(self.server.urls("OpenDocument")), 7)

    def test_list_ordered_by_something_else_than_date_is_read_to_the_end(self):
        self.server.add("cajp", 9)
        self.go("initial", ids=("jp",))
        self.server.dbs["cajp"].append({"unid": unid(77), "processo": "77/2026-JP", "relator": "X", "data": "10/21/2026", "descritores": []})
        self.go("weekly", ids=("jp",))
        self.assertEqual(self.listing_starts("cajp"), [1, 4, 7, 10])  # does not stop at the all-cached page 1
        self.assertTrue(self.raw.has_page("cajp", unid(77)))


if __name__ == "__main__":
    unittest.main()
