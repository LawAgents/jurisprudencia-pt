"""Throttled HTTP client for dgsi.pt (Lotus Domino, no API, no robots.txt).

Rules (owner decision):
- up to 4 request STARTS per second, scheduled by start time under one lock with a monotonic clock. The next start is
  computed from the ACTUAL start time of the previous one, so any 1-second window holds at most 4 starts even when
  the clock or the scheduler is late; never a window count, never a burst after a pause;
- the project User-Agent on every request;
- stop after 3 consecutive errors;
- a response slower than 5 s, or an HTTP 429/503, drops the rate to 2/s and then to 1/s (logged); it never goes back
  up during the same run.
"""
import sys
import threading
import time
import urllib.error
import urllib.request

from common import USER_AGENT

LEVEL_INTERVALS = (0.25, 0.5, 1.0)  # seconds between two request starts: 4/s, 2/s, 1/s
SLOW_SECONDS = 5.0
SLOW_STATUS = (429, 503)
MAX_CONSECUTIVE_ERRORS = 3
GONE = (404, 410)
TIMEOUT = 60


class FetchAborted(Exception):
    """Too many consecutive errors: stop everything, keep what is cached, resume later."""


def urllib_transport(url, headers, timeout=TIMEOUT):
    """Default transport: returns (status, body). Network failures raise OSError."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b""
    except urllib.error.URLError as e:
        raise OSError(str(e.reason)) from e
    except Exception as e:  # http.client errors, ssl errors, timeouts
        raise OSError(f"{type(e).__name__}: {e}") from e


class Dgsi:
    def __init__(self, transport=urllib_transport, clock=time.monotonic, sleep=time.sleep, user_agent=USER_AGENT,
                 log=None, request_log=None, level=0):
        self._transport, self._clock, self._sleep = transport, clock, sleep
        self.user_agent = user_agent
        self._log = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
        self._request_log = request_log  # optional path: one line per request (start time, status, seconds, level)
        self.level = level
        self._lock = threading.Lock()
        self._next_start = clock()
        self._last_start = None
        self.aborted = False
        self.errors_in_row = 0
        self.requests = 0
        self.errors = 0
        self.starts = []  # actual start times (monotonic seconds), for measuring the real rate
        self.slowdowns = []  # (request number, reason) of every drop in rate
        if request_log:
            with open(request_log, "a", encoding="utf-8") as fh:
                fh.write(f"# run mono_origin={clock():.6f}\n")

    @property
    def interval(self):
        return LEVEL_INTERVALS[self.level]

    def _slow_down(self, reason):
        """Called under the lock. Only ever goes down in rate."""
        if self.level >= len(LEVEL_INTERVALS) - 1:
            return
        self.level += 1
        if self._last_start is not None:
            self._next_start = max(self._next_start, self._last_start + self.interval)
        msg = f"rate dropped to {1 / self.interval:g} requests/s after request {self.requests}: {reason}"
        self.slowdowns.append((self.requests, reason))
        self._log(msg)

    def _wait_until(self, start):
        while True:
            now = self._clock()
            if now >= start:
                return
            self._sleep(start - now)

    def get(self, url, check=None):
        """Body bytes of `url`, or None when the server says 404/410. `check(body)` must be true for the answer to
        count as good (a 200 with a broken page counts as an error). Raises FetchAborted after 3 consecutive errors."""
        headers = {"User-Agent": self.user_agent}
        while True:
            with self._lock:
                if self.aborted:
                    raise FetchAborted("aborted by an earlier request")
                self._wait_until(max(self._clock(), self._next_start))
                start = self._clock()
                self._last_start = start
                self._next_start = start + self.interval
                self.requests += 1
                number, level = self.requests, self.level
                self.starts.append(start)
            try:
                status, body = self._transport(url, headers)
                err = None
            except OSError as e:
                status, body, err = None, b"", f"network error: {e}"
            seconds = self._clock() - start
            if err is None and status != 200:
                err = f"HTTP {status}"
            elif err is None and check is not None and not check(body):
                err = "unexpected content"
            with self._lock:
                if self._request_log:
                    with open(self._request_log, "a", encoding="utf-8") as fh:
                        fh.write(f"{start:.6f}\t{status}\t{seconds:.3f}\t{level}\t{url}\n")
                if status in SLOW_STATUS or seconds > SLOW_SECONDS:
                    self._slow_down(f"HTTP {status}" if status in SLOW_STATUS else f"response took {seconds:.1f} s")
                if err is None:
                    self.errors_in_row = 0
                    return body
                self.errors += 1
                self.errors_in_row += 1
                rows = self.errors_in_row
                if rows >= MAX_CONSECUTIVE_ERRORS:
                    self.aborted = True
            self._log(f"request failed ({err}) for {url}")
            if rows >= MAX_CONSECUTIVE_ERRORS:
                raise FetchAborted(f"{rows} consecutive errors, last: {err} for {url}")
            if status in GONE:
                return None

    def max_starts_in_window(self, window=1.0):
        """Largest number of request starts inside any half-open window [t, t + window) of the recorded starts."""
        s = sorted(self.starts)
        best, j = 0, 0
        for i in range(len(s)):
            while s[i] - s[j] >= window:
                j += 1
            best = max(best, i - j + 1)
        return best
