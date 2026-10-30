#!/usr/bin/env python3
"""Download the DGSI listings and decision pages into the raw cache (outside the repo).

  python scripts/fetch.py --mode initial|weekly --raw DIR [--config DIR] [--db NAME] [--limit N] [--workers 4]
                          [--budget-seconds N]

Raw cache layout (all gzip):
  lists/<db>.json.gz           one entry per decision: processo, relator, descritores, data, path (listing order)
  pages/<db>/<unid>.html.gz    the decision page as served for ?OpenDocument&ExpandSection=1 (whole page, long texts too)
  requests.log                 start time, status, seconds and rate level of every request (to measure the real rate)

initial: list every page of every database, then fetch every decision page that is not cached yet. Safe to stop and run
         again: finished lists and cached pages are skipped, an unfinished list continues where it stopped.
weekly:  per database, ask the listing pages from the first one (newest first) and fetch the decisions not cached yet;
         stop at the first listing page whose decisions are all cached. Databases whose list is not ordered by date
         ("completa" in config/tribunais.txt) are listed to the end.
--limit N: at most N decision pages in total, split evenly over the selected databases (for tests); lists stop early.

Exit codes: 0 done, 1 stopped by errors (3 in a row), 2 time budget reached (run again to resume).
"""
import argparse
import json
import math
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HOST, atomic_write, gz_bytes, load_tribunais, read_gz  # noqa: E402
from dgsi_client import Dgsi, FetchAborted  # noqa: E402
from dgsi_html import list_ok, page_ok, parse_list  # noqa: E402

PROGRESS_EVERY = 500
SAVE_EVERY_PAGES = 20
BATCH = 16


class Raw:
    """The raw cache directory."""

    def __init__(self, root):
        self.root = Path(root)

    def page_path(self, db, unid):
        return self.root / "pages" / db / f"{unid}.html.gz"

    def has_page(self, db, unid):
        return self.page_path(db, unid).exists()

    def write_page(self, db, unid, body):
        atomic_write(self.page_path(db, unid), gz_bytes(body), binary=True)

    def list_path(self, db):
        return self.root / "lists" / f"{db}.json.gz"

    def read_list(self, db):
        p = self.list_path(db)
        if not p.exists():
            return {"db": db, "complete": False, "next": None, "expected": None, "rows": {}}
        return json.loads(read_gz(p))

    def write_list(self, lst):
        atomic_write(self.list_path(lst["db"]), gz_bytes(json.dumps(lst, ensure_ascii=False).encode("utf-8")), binary=True)

    def note_missing(self, db, unid):
        with open(self.root / "missing.txt", "a", encoding="utf-8") as fh:
            fh.write(f"{db}/{unid}\n")

    def pages(self, db):
        d = self.root / "pages" / db
        return sorted(d.glob("*.html.gz")) if d.is_dir() else []


class Out:
    def __init__(self, client, log):
        self.client, self.log, self.t0, self._said = client, log, time.monotonic(), 0

    def progress(self, what):
        n = self.client.requests // PROGRESS_EVERY
        if n > self._said:
            self._said = n
            self.log(f"[{time.monotonic() - self.t0:7.0f}s] {self.client.requests} requests, {self.client.errors} errors, "
                     f"{1 / self.client.interval:g}/s: {what}")


def row_record(r):
    return {k: r[k] for k in ("path", "processo", "relator", "descritores", "data")}


def expected_count(client, db, first_path):
    """toplevelentries of the view (1 request), or None."""
    m = re.match(r"/[a-z0-9]+\.nsf/([0-9a-f]{32})/", first_path or "")
    if not m:
        return None
    body = client.get(f"{HOST}/{db}.nsf/{m.group(1)}?ReadViewEntries&Count=1&Start=1", check=lambda b: b"toplevelentries" in b)
    mm = re.search(rb'toplevelentries="(\d+)"', body or b"")
    return int(mm.group(1)) if mm else None


def fetch_pages(client, raw, db, rows, workers, out, deadline, now, max_pages=None):
    """Fetch the decision pages of `rows` ({unid: record}) that are not cached. Returns (fetched, stopped_by_budget)."""
    todo = [(u, r) for u, r in rows.items() if not raw.has_page(db, u)]
    if max_pages is not None:
        todo = todo[:max(0, max_pages)]

    def one(item):
        unid, rec = item
        body = client.get(f"{HOST}{rec['path']}?OpenDocument&ExpandSection=1", check=page_ok)
        if body is None:
            raw.note_missing(db, unid)
            return 0
        raw.write_page(db, unid, body)
        return 1

    done = 0
    ex = ThreadPoolExecutor(max_workers=workers) if workers > 1 else None
    try:
        for i in range(0, len(todo), BATCH):
            if deadline is not None and now() >= deadline:
                return done, True
            batch = todo[i:i + BATCH]
            done += sum(ex.map(one, batch) if ex else map(one, batch))
            out.progress(f"{db} pages {done}/{len(todo)}")
    finally:
        if ex:
            ex.shutdown(wait=True, cancel_futures=True)
    return done, False


def list_initial(client, raw, t, out, deadline, now, max_rows=None):
    """Complete (or continue) the list of one database. Returns True when stopped by the time budget."""
    lst = raw.read_list(t.db)
    if lst["complete"]:
        return False
    url = lst["next"] or f"/{t.db}.nsf?OpenDatabase&Start=1"
    pages = 0
    while True:
        if deadline is not None and now() >= deadline:
            raw.write_list(lst)
            return True
        body = client.get(HOST + url, check=list_ok)
        rows, nxt = parse_list(body or b"")
        new = [r for r in rows if r["unid"] not in lst["rows"]]
        for r in new:
            lst["rows"][r["unid"]] = row_record(r)
        if lst["expected"] is None and new:
            lst["expected"] = expected_count(client, t.db, new[0]["path"])
        pages += 1
        lst["next"] = nxt
        if not new or not nxt or nxt == url:
            lst["complete"], lst["next"] = True, None
            break
        url = nxt
        out.progress(f"{t.db} list {len(lst['rows'])}/{lst['expected']}")
        if max_rows is not None and len(lst["rows"]) >= max_rows:
            break
        if pages % SAVE_EVERY_PAGES == 0:
            raw.write_list(lst)
    raw.write_list(lst)
    return False


def weekly_db(client, raw, t, workers, out, deadline, now, max_pages=None):
    """Newest listing pages first; fetch what is not cached; stop at a page whose decisions are all cached.
    Returns True when stopped by the time budget."""
    lst = raw.read_list(t.db)
    url = f"/{t.db}.nsf?OpenDatabase&Start=1"
    seen, fetched = {url}, 0
    new_rows = {}
    stopped = False
    while True:
        if deadline is not None and now() >= deadline:
            stopped = True
            break
        body = client.get(HOST + url, check=list_ok)
        rows, nxt = parse_list(body or b"")
        page_rows = {r["unid"]: row_record(r) for r in rows}
        all_cached = all(raw.has_page(t.db, u) for u in page_rows)
        for u, rec in page_rows.items():
            if u not in lst["rows"]:
                new_rows[u] = rec
        left = None if max_pages is None else max_pages - fetched
        n, stopped = fetch_pages(client, raw, t.db, page_rows, workers, out, deadline, now, left)
        fetched += n
        if stopped or (max_pages is not None and fetched >= max_pages):
            break
        if not page_rows or not nxt or nxt in seen:
            break
        if all_cached and t.lista == "recentes":
            break
        seen.add(nxt)
        url = nxt
    if new_rows:  # newest first, as in the listing
        lst["rows"] = {**new_rows, **{u: r for u, r in lst["rows"].items() if u not in new_rows}}
    lst.setdefault("complete", False)
    raw.write_list(lst)
    return stopped


def run_fetch(client, raw, tribunais, mode, only=None, limit=None, budget_seconds=None, workers=4, now=time.monotonic,
              log=lambda m: print(m, file=sys.stderr, flush=True)):
    """Returns 0 done, 1 aborted by errors, 2 time budget reached."""
    chosen = [t for t in tribunais.values() if only in (None, t.id, t.db)]
    if not chosen:
        raise SystemExit(f"unknown database {only!r}")
    per_db = None if limit is None else math.ceil(limit / len(chosen))
    deadline = None if budget_seconds is None else now() + budget_seconds
    out = Out(client, log)
    try:
        if mode == "initial":
            for t in chosen:
                if list_initial(client, raw, t, out, deadline, now, per_db):
                    return 2
            for t in chosen:
                _, stopped = fetch_pages(client, raw, t.db, raw.read_list(t.db)["rows"], workers, out, deadline, now, per_db)
                if stopped:
                    return 2
        else:
            for t in chosen:
                if weekly_db(client, raw, t, workers, out, deadline, now, per_db):
                    return 2
    except FetchAborted as e:
        log(f"STOPPED: {e}. Cached files are kept; run the same command again to resume.")
        return 1
    return 0


def rate_summary(client):
    return (f"{client.requests} requests, {client.errors} errors, slowdowns {client.slowdowns or 'none'}, "
            f"max request starts in any 1 s window: {client.max_starts_in_window(1.0)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 epilog="Exit codes: 0 done, 1 stopped by errors, 2 time budget reached (resume later).")
    ap.add_argument("--mode", choices=["initial", "weekly"], required=True)
    ap.add_argument("--raw", required=True, help="raw cache directory (outside the repo)")
    ap.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "config"))
    ap.add_argument("--db", default=None, help="only this database (id from config/tribunais.txt or the DGSI name)")
    ap.add_argument("--limit", type=int, default=None, help="at most N decision pages in total (for tests)")
    ap.add_argument("--workers", type=int, default=4, help="downloads in flight; the start rate stays at most 4 per second")
    ap.add_argument("--budget-seconds", type=float, default=None)
    a = ap.parse_args(argv)
    raw = Raw(a.raw)
    raw.root.mkdir(parents=True, exist_ok=True)
    client = Dgsi(request_log=raw.root / "requests.log")
    rc = run_fetch(client, raw, load_tribunais(Path(a.config) / "tribunais.txt"), a.mode, a.db, a.limit, a.budget_seconds,
                   a.workers)
    print(rate_summary(client), file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
