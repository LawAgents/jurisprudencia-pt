#!/usr/bin/env python3
"""Repo size check (RULES.xml#rule.repo_size_limit): exit 1 when the git objects or the tracked working tree pass 1 GiB.

  python scripts/check_size.py --repo DIR [--tree DIR] [--limit-bytes N]

--tree measures that directory instead of the tracked files of the repo (used before publishing, on the staging tree
that is about to replace the repo files). Prints both numbers.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

LIMIT_BYTES = 1024 ** 3


def git_objects_bytes(repo):
    """Loose objects plus packs, from `git count-objects -v` (KiB). 0 when `repo` is not a git repository."""
    r = subprocess.run(["git", "-C", str(repo), "count-objects", "-v"], capture_output=True, text=True)
    if r.returncode != 0:
        return 0
    kib = {}
    for ln in r.stdout.splitlines():
        k, _, v = ln.partition(":")
        if v.strip().isdigit():
            kib[k.strip()] = int(v.strip())
    return (kib.get("size", 0) + kib.get("size-pack", 0)) * 1024


def tracked_bytes(repo):
    r = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True)
    if r.returncode != 0:
        return tree_bytes(repo)
    total = 0
    for rel in r.stdout.decode("utf-8", "replace").split("\0"):
        p = Path(repo) / rel
        if rel and p.is_file():
            total += p.stat().st_size
    return total


def tree_bytes(path):
    total = 0
    for dirpath, dirnames, files in os.walk(path):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        total += sum(os.path.getsize(os.path.join(dirpath, f)) for f in files)
    return total


def check(repo, tree=None, limit=LIMIT_BYTES):
    """Returns (ok, git_objects_bytes, working_tree_bytes)."""
    objs = git_objects_bytes(repo)
    work = tree_bytes(tree) if tree else tracked_bytes(repo)
    return objs <= limit and work <= limit, objs, work


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fail when the repo (git objects or tracked tree) exceeds 1 GiB.")
    ap.add_argument("--repo", required=True, help="the git repo")
    ap.add_argument("--tree", default=None, help="measure this directory instead of the repo's tracked files")
    ap.add_argument("--limit-bytes", type=int, default=LIMIT_BYTES)
    a = ap.parse_args(argv)
    ok, objs, work = check(a.repo, a.tree, a.limit_bytes)
    print(f"git objects: {objs} bytes ({objs / 1024 ** 2:.1f} MiB)")
    print(f"working tree: {work} bytes ({work / 1024 ** 2:.1f} MiB)")
    print(f"limit: {a.limit_bytes} bytes -> {'OK' if ok else 'TOO BIG'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
