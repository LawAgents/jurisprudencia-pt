import threading
import unittest

from helpers import FakeClock  # noqa: F401  (also puts scripts/ on sys.path)
from dgsi_client import Dgsi, FetchAborted
from common import USER_AGENT


def make(statuses=None, delays=None):
    """A client on a fake clock whose transport answers from `statuses` (list, then 200) and takes `delays` seconds."""
    clock = FakeClock()
    seen, statuses, delays = [], list(statuses or []), dict(delays or {})
    msgs = []

    def transport(url, headers):
        seen.append((url, headers, clock()))
        if url in delays:
            clock.sleep(delays[url])
        return (statuses.pop(0) if statuses else 200), b"ok"

    return Dgsi(transport=transport, clock=clock, sleep=clock.sleep, log=msgs.append), seen, clock, msgs


class RateLimiter(unittest.TestCase):
    def test_starts_are_spaced_by_start_time_and_never_exceed_4_per_second(self):
        c, seen, clock, _ = make()
        for i in range(41):
            c.get(f"u{i}")
        starts = [t for _, _, t in seen]
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        self.assertGreaterEqual(min(gaps), 0.25 - 1e-9)
        self.assertLessEqual(c.max_starts_in_window(1.0), 4)
        self.assertAlmostEqual(starts[-1] - starts[0], 40 * 0.25, places=6)  # 4 per second, not slower

    def test_a_slow_response_does_not_cause_a_burst_afterwards(self):
        c, seen, clock, _ = make(delays={"slow": 0.9})  # below the 5 s limit: no slowdown, but 3 intervals pass
        c.get("a")
        c.get("slow")
        for i in range(8):
            c.get(f"b{i}")
        self.assertLessEqual(c.max_starts_in_window(1.0), 4)
        self.assertEqual(c.level, 0)

    def test_threads_share_one_schedule(self):
        # real clock on purpose: 4 threads, 12 requests, the 1-second windows of the real start times hold at most 4 starts
        c = Dgsi(transport=lambda url, h: (200, b"ok"), log=lambda m: None)
        ts = [threading.Thread(target=lambda k=k: [c.get(f"t{k}-{i}") for i in range(3)]) for k in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(c.requests, 12)
        self.assertLessEqual(c.max_starts_in_window(1.0), 4)

    def test_user_agent_is_exact(self):
        c, seen, _, _ = make()
        c.get("u")
        self.assertEqual(seen[0][1]["User-Agent"], "LawAgents-jurisprudencia (github.com/LawAgents)")
        self.assertEqual(USER_AGENT, "LawAgents-jurisprudencia (github.com/LawAgents)")


class SlowDown(unittest.TestCase):
    def test_6_second_response_drops_to_2_per_second_then_1_and_never_goes_back(self):
        c, seen, clock, msgs = make(delays={"slow1": 6.0, "slow2": 6.0})
        c.get("a")
        c.get("slow1")
        self.assertEqual(c.level, 1)
        for i in range(5):
            c.get(f"b{i}")
        starts = [t for u, _, t in seen if u.startswith("b")]
        self.assertGreaterEqual(min(b - a for a, b in zip(starts, starts[1:])), 0.5 - 1e-9)
        c.get("slow2")
        self.assertEqual(c.level, 2)
        for i in range(5):
            c.get(f"c{i}")
        starts = [t for u, _, t in seen if u.startswith("c")]
        self.assertGreaterEqual(min(b - a for a, b in zip(starts, starts[1:])), 1.0 - 1e-9)
        for i in range(30):
            c.get(f"d{i}")
        self.assertEqual(c.level, 2)  # never goes back up in the same run
        self.assertEqual(len(c.slowdowns), 2)
        self.assertTrue(any("dropped to 2 requests/s" in m for m in msgs))
        self.assertTrue(any("dropped to 1 requests/s" in m for m in msgs))

    def test_429_drops_the_rate_and_the_request_is_retried(self):
        c, seen, clock, msgs = make(statuses=[200, 429])
        c.get("a")
        body = c.get("b")
        self.assertEqual(body, b"ok")
        self.assertEqual(c.level, 1)
        self.assertEqual([u for u, _, _ in seen], ["a", "b", "b"])
        self.assertGreaterEqual(seen[2][2] - seen[1][2], 0.5 - 1e-9)

    def test_503_drops_the_rate(self):
        c, *_ = make(statuses=[503])
        c.get("a")
        self.assertEqual(c.level, 1)

    def test_exactly_5_seconds_is_not_slow(self):
        c, *_ = make(delays={"a": 5.0})
        c.get("a")
        self.assertEqual(c.level, 0)


class ErrorStop(unittest.TestCase):
    def test_three_consecutive_errors_abort(self):
        c, seen, _, _ = make(statuses=[500, 500, 500, 200])
        with self.assertRaises(FetchAborted):
            c.get("a")
        self.assertEqual(len(seen), 3)
        with self.assertRaises(FetchAborted):  # stays stopped
            c.get("b")
        self.assertEqual(len(seen), 3)

    def test_a_success_resets_the_count(self):
        c, seen, _, _ = make(statuses=[500, 500, 200, 500, 500, 200])
        c.get("a")
        c.get("b")
        self.assertEqual(len(seen), 6)
        self.assertFalse(c.aborted)

    def test_network_errors_count(self):
        clock = FakeClock()

        def boom(url, headers):
            raise OSError("reset")

        c = Dgsi(transport=boom, clock=clock, sleep=clock.sleep, log=lambda m: None)
        with self.assertRaises(FetchAborted):
            c.get("a")
        self.assertEqual(c.requests, 3)

    def test_404_returns_none_and_is_not_retried(self):
        c, seen, _, _ = make(statuses=[404])
        self.assertIsNone(c.get("gone"))
        self.assertEqual(len(seen), 1)
        self.assertEqual(c.get("next"), b"ok")

    def test_three_404_in_a_row_abort(self):
        c, *_ = make(statuses=[404, 404, 404])
        c.get("a")
        c.get("b")
        with self.assertRaises(FetchAborted):
            c.get("c")

    def test_a_broken_page_counts_as_an_error(self):
        c, seen, _, _ = make()
        with self.assertRaises(FetchAborted):
            c.get("a", check=lambda body: False)
        self.assertEqual(len(seen), 3)


if __name__ == "__main__":
    unittest.main()
