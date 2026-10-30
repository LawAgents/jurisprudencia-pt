#!/usr/bin/env python3
"""Run a whole update: fetch -> convert -> validate -> build_index -> check_size, then replace the repo files.

  python scripts/run_update.py --mode initial|weekly --raw DIR --repo DIR [--budget-seconds N] [--workers 4]

Everything is built in a staging directory (DIR/stage, outside the repo). The repo is only touched in the last step,
when every earlier step passed, so a failure leaves it exactly as it was.

Exit codes: 0 ready to commit (prints CHANGED=true|false, also appended to $GITHUB_OUTPUT when set),
            2 time budget reached while fetching (run again to resume; repo untouched),
            1 failure (repo untouched; error list in DIR/errors.json, summary on stderr).
"""
import argparse
import json
import os
import re
import shutil
import sys
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_index  # noqa: E402
import check_size  # noqa: E402
import convert  # noqa: E402
import fetch  # noqa: E402
import validate  # noqa: E402
from common import ROOT_INDEX, atomic_write, load_retirada, load_tribunais  # noqa: E402
from dgsi_client import Dgsi  # noqa: E402

MAX_EXCLUDED_RATIO = 0.005  # more pages than this left out by the converter means the site changed: fail
MIN_KEPT_RATIO = 0.98  # weekly: the new tree must keep at least this share of the files already in the repo


class Failure(Exception):
    def __init__(self, stage, errors, warnings=None):
        super().__init__(stage)
        self.stage, self.errors, self.warnings = stage, errors, warnings or []


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def tree_files(root, tribunais):
    """Pipeline-owned files of a tree: decision files (relative paths) and the index files at the root."""
    root = Path(root)
    out = {p.relative_to(root).as_posix() for t in tribunais if (root / t).is_dir() for p in (root / t).rglob("*.md")}
    if root.is_dir():
        out |= {p.name for p in root.iterdir() if p.is_file() and ROOT_INDEX.match(p.name)}
    return out


def is_pipeline_file(repo, rel):
    """Root index files and decision files (front matter with a tribunal). A hand-made README inside a tribunal folder is not ours."""
    if "/" not in rel:
        return True
    with open(Path(repo) / rel, "rb") as fh:
        return b"\ntribunal: " in fh.read(4096)


def same_ignoring_retrieved(a: bytes, b: bytes):
    if a == b:
        return True
    strip = lambda x: re.sub(rb"^retrieved: .*\n", b"", x, count=1, flags=re.M)  # noqa: E731
    return strip(a) == strip(b)


def apply_stage(stage, repo, tribunais):
    """Make the pipeline-owned files of `repo` equal to `stage`. Files whose only difference is the `retrieved` date are
    left alone. Returns (added, changed, removed); restores the repo if copying fails half way."""
    stage, repo = Path(stage), Path(repo)
    new = tree_files(stage, tribunais)
    old = {rel for rel in tree_files(repo, tribunais) if is_pipeline_file(repo, rel)}
    ops, added, changed = [], 0, 0
    for rel in sorted(new):
        src, dst = stage / rel, repo / rel
        if dst.exists():
            if same_ignoring_retrieved(src.read_bytes(), dst.read_bytes()):
                continue
            changed += 1
        else:
            added += 1
        ops.append(("put", rel))
    ops += [("del", rel) for rel in sorted(old - new)]
    undo = []
    try:
        for op, rel in ops:
            dst = repo / rel
            undo.append((rel, dst.read_bytes() if dst.exists() else None))
            if op == "put":
                atomic_write(dst, (stage / rel).read_bytes(), binary=True)
            else:
                dst.unlink()
    except Exception:
        for rel, data in reversed(undo):
            if data is None:
                (repo / rel).unlink(missing_ok=True)
            else:
                atomic_write(repo / rel, data, binary=True)
        raise
    for d in sorted({(repo / rel).parent for op, rel in ops if op == "del"}, key=lambda p: -len(p.parts)):
        while d != repo and d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    return added, changed, len(old - new)


def write_errors(raw, mode, stage, errors, warnings):
    atomic_write(Path(raw) / "errors.json", json.dumps(
        {"mode": mode, "stage": stage, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=1))
    by_code = Counter(e.get("code") or "error" for e in errors)
    _log(f"UPDATE FAILED at stage '{stage}': {len(errors)} errors" + (f" ({dict(by_code)})" if errors else ""))
    for e in errors[:25]:
        _log(f"  {e.get('code', 'error')}: {e.get('file') or ''} {e.get('message') or e.get('error') or ''}")
    if len(errors) > 25:
        _log(f"  ... {len(errors) - 25} more in {Path(raw) / 'errors.json'}")


def run(mode, raw_dir, repo, budget_seconds=None, config=None, client=None, workers=4, convert_workers=1,
        size_limit=check_size.LIMIT_BYTES, max_excluded_ratio=MAX_EXCLUDED_RATIO, clock=None):
    """Returns the exit code. `client`: injectable DGSI client for tests."""
    raw_dir, repo = Path(raw_dir), Path(repo)
    config = Path(config) if config else repo / "config"
    raw = fetch.Raw(raw_dir)
    stage = raw_dir / "stage"
    warnings = []
    try:
        tribunais = load_tribunais(config / "tribunais.txt")
        retirada = load_retirada(config / "retirada.txt")
        raw_dir.mkdir(parents=True, exist_ok=True)
        c = client or Dgsi(request_log=raw_dir / "requests.log")
        rc = fetch.run_fetch(c, raw, tribunais, mode, None, None, budget_seconds, workers, **({"now": clock} if clock else {}))
        _log(fetch.rate_summary(c))
        if rc == 2:
            return 2
        if rc != 0:
            raise Failure("fetch", [{"code": "fetch_aborted", "message": "the DGSI fetch stopped (see the log above)"}])

        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir(parents=True)
        written, excluded, retired = convert.convert_all(raw_dir, stage, config, convert_workers, None, retirada)
        atomic_write(raw_dir / "excluded.json", json.dumps(excluded, ensure_ascii=False, indent=1))
        pages = sum(len(raw.pages(t.db)) for t in tribunais.values())
        dropped = [e for e in excluded if not e["kept"]]
        if pages and len(dropped) / pages > max_excluded_ratio:
            raise Failure("convert", [{"code": "too_many_excluded", "message":
                                       f"{len(dropped)} of {pages} pages could not be converted (limit {max_excluded_ratio:.1%}); "
                                       f"see excluded.json"}] + [{"code": "excluded", "file": f"{e['tribunal']}/{e['unid']}",
                                                                  "message": e["reason"]} for e in dropped[:25]])
        errors, warnings = validate.validate(stage, tribunais, retirada, pages - len(dropped) - retired)
        if errors:
            raise Failure("validate", errors, warnings)

        old = {rel for rel in tree_files(repo, tribunais) if "/" in rel and is_pipeline_file(repo, rel)}
        new = {rel for rel in tree_files(stage, tribunais) if "/" in rel}
        if mode == "weekly" and old and len(new & old) + retired < MIN_KEPT_RATIO * len(old):
            raise Failure("shrink", [{"code": "raw_cache_incomplete", "message":
                                      f"the new tree has {len(new & old)} of the {len(old)} decisions already in the repo: the raw "
                                      f"cache looks incomplete. Restore it or run --mode initial before publishing."}], warnings)

        try:
            build_index.build_all(stage, config)
        except Exception as e:  # noqa: BLE001
            raise Failure("index", [{"code": "index_error", "message": str(e)}], warnings)

        ok, objs, work = check_size.check(repo, stage, size_limit)
        if not ok:
            raise Failure("size", [{"code": "repo_too_big", "message":
                                    f"git objects {objs} bytes, working tree {work} bytes, limit {size_limit}"}], warnings)

        added, changed, removed = apply_stage(stage, repo, tribunais)
        _log(f"repo updated: {added} added, {changed} changed, {removed} removed; {len(excluded)} pages excluded or with the sumário replaced")
        return _report_changed(bool(added or changed or removed))
    except Failure as f:
        write_errors(raw_dir, mode, f.stage, f.errors, f.warnings or warnings)
        return 1
    except Exception as e:  # noqa: BLE001  any surprise is a failed update, never a half-written repo
        write_errors(raw_dir, mode, "internal", [{"code": "internal_error", "message": "".join(
            traceback.format_exception_only(type(e), e)).strip(), "traceback": traceback.format_exc()}], warnings)
        return 1


def _report_changed(changed):
    line = f"CHANGED={'true' if changed else 'false'}"
    print(line)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fetch, convert, validate, index and check size; then update the repo files.",
                                 epilog="Exit codes: 0 ready to commit (CHANGED=true|false), 2 budget reached (resume "
                                        "later), 1 failure (see RAW/errors.json).")
    ap.add_argument("--mode", choices=["initial", "weekly"], required=True)
    ap.add_argument("--raw", required=True, help="raw cache and staging directory (outside the repo)")
    ap.add_argument("--repo", required=True, help="the repo working tree to update (a git checkout)")
    ap.add_argument("--budget-seconds", type=float, default=None, help="stop fetching after this long (exit code 2)")
    ap.add_argument("--config", default=None, help="config directory (default REPO/config)")
    ap.add_argument("--workers", type=int, default=4, help="downloads in flight; the start rate stays at most 4 per second")
    ap.add_argument("--convert-workers", type=int, default=1, help="processes for the conversion (use 4 or more for the full set)")
    a = ap.parse_args(argv)
    return run(a.mode, a.raw, a.repo, a.budget_seconds, a.config, workers=a.workers, convert_workers=a.convert_workers)


if __name__ == "__main__":
    sys.exit(main())
