#!/usr/bin/env python3
"""Validate the generated decision files.

  python scripts/validate.py --root DIR [--config DIR] [--expected N]

Checks per file: front matter with the required fields, id equal to the file name and unique, tribunal known, folder
<tribunal>/<year>, ISO dates, DGSI source link of the right database, ECLI consistent with config/tribunais.txt, body with
a sumário (or the fixed sentence 'Sem sumário publicado. Texto integral na fonte.'), no full text of any kind,
size under 60 KB, id not listed in config/retirada.txt. With --expected N also checks the number of files.
Exit code 0 when there are no errors, 1 otherwise.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (LEGAL_NOTICE, NO_SUMMARY, REQUIRED, SOURCE_RE, SUMMARY_HEADING, TEXT_VERSION, iter_decision_files,  # noqa: E402
                    load_retirada, load_tribunais, parse_frontmatter, valid_iso_date)

MAX_FILE_BYTES = 60 * 1024
IGNORED_DIRS = {".git", ".github", "config", "docs", "scripts", "__pycache__"}
FULL_TEXT = re.compile(r"Decis[ãa]o\s+Texto\s+Integral|^#{1,6}\s*Texto\s+Integral", re.I | re.M)
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def check_file(path, root, tribunais, retirada):
    """List of (code, message) problems of one decision file, plus its id (or None)."""
    errs = []
    raw = Path(path).read_bytes()
    if len(raw) >= MAX_FILE_BYTES:
        errs.append(("file_too_big", f"{len(raw)} bytes, limit {MAX_FILE_BYTES}"))
    try:
        text = raw.decode("utf-8")
        meta, body = parse_frontmatter(text)
    except (UnicodeDecodeError, ValueError) as e:
        return [("front_matter", str(e))], None
    for k in REQUIRED:
        if meta.get(k) in (None, "", []):
            errs.append(("missing_field", k))
    did = meta.get("id")
    rel = Path(path).relative_to(root).as_posix()
    tid = meta.get("tribunal")
    t = tribunais.get(tid)
    if did:
        if not ID_RE.match(str(did)):
            errs.append(("bad_id", f"id {did!r} has characters other than a-z, 0-9 and -"))
        if Path(path).stem != did:
            errs.append(("id_filename", f"id {did} but file {rel}"))
        if tid and not str(did).startswith(f"{tid}-"):
            errs.append(("id_tribunal", f"id {did} does not start with {tid}-"))
        if did in retirada:
            errs.append(("retired", f"{did} is listed in config/retirada.txt"))
    if tid and t is None:
        errs.append(("unknown_tribunal", f"{tid!r} is not in config/tribunais.txt"))
    for k in ("data", "retrieved"):
        if meta.get(k) not in (None, "") and not valid_iso_date(meta.get(k)):
            errs.append(("bad_date", f"{k}: {meta.get(k)!r}"))
    if valid_iso_date(meta.get("data")) and tid and rel != f"{tid}/{str(meta['data'])[:4]}/{did}.md":
        errs.append(("path", f"{rel} should be {tid}/{str(meta['data'])[:4]}/{did}.md"))
    src = meta.get("source")
    if src:
        m = SOURCE_RE.match(src)
        if not m:
            errs.append(("bad_source", f"{src!r} is not a DGSI decision link"))
        elif t and m.group(1) != t.db:
            errs.append(("bad_source", f"{src!r} is not a link of database {t.db}"))
    if meta.get("text_version") and meta["text_version"] != TEXT_VERSION:
        errs.append(("text_version", repr(meta["text_version"])))
    if meta.get("legal_notice") and meta["legal_notice"] != LEGAL_NOTICE:
        errs.append(("legal_notice", "differs from the fixed notice"))
    if "descritores" in meta and not (isinstance(meta["descritores"], list) and all(isinstance(x, str) for x in meta["descritores"])):
        errs.append(("descritores", "must be a list of strings"))
    if meta.get("texto_integral") not in (None, "S", "N"):
        errs.append(("texto_integral", repr(meta.get("texto_integral"))))
    if t:
        # a placeholder processo in the source ("???", "(…)") has no ECLI to build
        want = bool(t.sigla) and bool(re.search(r"[A-Za-z0-9]", str(meta.get("processo", ""))))
        conf = meta.get("ecli_confirmed")
        if conf is not want:
            errs.append(("ecli_confirmed", f"must be {want} for {tid}"))
        ecli, year = meta.get("ecli"), str(meta.get("data", ""))[:4]
        if want and not (ecli and ecli.startswith(f"ECLI:PT:{t.sigla}:{year}:")):
            errs.append(("ecli", f"{ecli!r} does not start with ECLI:PT:{t.sigla}:{year}:"))
        if not want and ecli:
            errs.append(("ecli", f"{tid} has no confirmed ECLI pattern, so the file must not carry one"))
    if FULL_TEXT.search(text):
        errs.append(("full_text", "the file contains a full-text section"))
    # Body: title, then the sumário (or the fixed sentence) and nothing else.
    title = meta.get("title", "")
    if not body.lstrip().startswith(f"# {title}\n"):
        errs.append(("body_title", "the body must start with '# <title>'"))
    head, sep, summary = body.partition(f"\n{SUMMARY_HEADING}\n")
    summary = summary.strip()
    if not sep:
        errs.append(("no_summary_section", f"missing '{SUMMARY_HEADING}'"))
    elif not summary:
        errs.append(("empty_summary", "empty sumário"))
    elif NO_SUMMARY in summary and summary != NO_SUMMARY:
        errs.append(("summary_mixed", "the fixed 'no sumário' sentence appears together with other text"))
    if re.search(r"^## ", summary, re.M):
        errs.append(("extra_section", "another '## ' section after the sumário"))
    return errs, did


def validate(root, tribunais, retirada=frozenset(), expected=None):
    """Returns (errors, warnings): lists of dicts with code, file and message."""
    root = Path(root)
    errors, warnings, seen, n = [], [], {}, 0
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        if d.is_dir() and d.name not in tribunais and d.name not in IGNORED_DIRS and any(d.rglob("*.md")):
            errors.append({"code": "unknown_folder", "file": d.name, "message": "folder with markdown files that is not a tribunal of config/tribunais.txt"})
    for p in iter_decision_files(root, tribunais):
        n += 1
        problems, did = check_file(p, root, tribunais, retirada)
        rel = p.relative_to(root).as_posix()
        for code, msg in problems:
            errors.append({"code": code, "file": rel, "message": msg})
        if did:
            if did in seen:
                errors.append({"code": "duplicate_id", "file": rel, "message": f"id {did} also in {seen[did]}"})
            seen[did] = rel
    if expected is not None and n != expected:
        errors.append({"code": "count", "file": "", "message": f"{n} decision files, expected {expected}"})
    return errors, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "config"))
    ap.add_argument("--expected", type=int, default=None)
    a = ap.parse_args(argv)
    cfg = Path(a.config)
    errors, _ = validate(a.root, load_tribunais(cfg / "tribunais.txt"), load_retirada(cfg / "retirada.txt"), a.expected)
    for e in errors[:50]:
        print(f"{e['code']}: {e['file']} {e['message']}", file=sys.stderr)
    if len(errors) > 50:
        print(f"... {len(errors) - 50} more", file=sys.stderr)
    print(f"{len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
