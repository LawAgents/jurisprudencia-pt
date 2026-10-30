#!/usr/bin/env python3
"""Layered indices for the decision files (every index file is at most 40 KB).

  python scripts/build_index.py --root DIR [--config DIR]

Layer 1  indice.md                        one row per tribunal, with its overview file(s)
Layer 2  indice-<tribunal>.md             one row per year, and for years with several shards the date range of each shard
         (when this file passes 40 KB it is split into indice-<tribunal>-1.md, -2.md ...)
Layer 3  indice-<tribunal>-<ano>[-a].md   id | data | processo | relator | descritores (first 6) | path, by date
         (a year that does not fit in 40 KB is split into -a, -b, ... in date order)

descritores.md                            descritor (accents and case folded) | decisions | shards that contain it.
         Layers again: descritores.md -> descritores-d<level>-<n>.md (only when needed) -> descritores-<letter>-<n>.md.
"""
import argparse
import string
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import atomic_write, fold, iter_decision_files, load_tribunais, read_frontmatter  # noqa: E402

MAX_INDEX_BYTES = 40 * 1024  # the Read tool of the agents cuts files at about 25k tokens
SHARDS_PER_DESCRITOR = 5
SHARD_ROW_DESCRITORES = 6


def cell(s):
    return " ".join(str(s or "").split()).replace("|", "\\|")


def fmt(n):
    return f"{n:,}".replace(",", ".")


def suffix(i):
    """0 -> a, 25 -> z, 26 -> aa ..."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = string.ascii_lowercase[r] + s
    return s


def split_lines(lines, budget):
    """Group lines into chunks whose UTF-8 size (with newlines) stays within `budget` bytes."""
    chunks, cur, size = [], [], 0
    for ln in lines:
        b = len(ln.encode("utf-8")) + 1
        if cur and size + b > budget:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(ln)
        size += b
    if cur:
        chunks.append(cur)
    return chunks


def collect(root, tribunais):
    """Rows of every decision file: {tribunal: {year: [row]}} (front matter only)."""
    out = defaultdict(lambda: defaultdict(list))
    for p in iter_decision_files(root, tribunais):
        meta, _ = read_frontmatter(p)
        rel = p.relative_to(root).as_posix()
        out[meta["tribunal"]][str(meta["data"])[:4]].append({
            "id": meta["id"], "data": str(meta["data"]), "processo": meta.get("processo", ""),
            "relator": meta.get("relator", ""), "descritores": meta.get("descritores", []), "path": rel})
    return out


def shard_file(root, name, header_lines, rows):
    body = "\n".join(header_lines + rows) + "\n"
    atomic_write(Path(root) / name, body)
    return len(body.encode("utf-8"))


def build_all(root, config=None):
    """Write the index files into `root`. Returns {'files': n, 'rows': n}."""
    root = Path(root)
    config = Path(config) if config else Path(__file__).resolve().parent.parent / "config"
    tribunais = load_tribunais(config / "tribunais.txt")
    data = collect(root, tribunais)
    desc = defaultdict(lambda: [0, defaultdict(int)])  # folded descritor -> [decisions, {shard file: decisions}]
    summary, files, rows_total = [], 0, 0

    for tid, t in tribunais.items():
        years = data.get(tid)
        if not years:
            continue
        year_lines, total = [], 0
        for year in sorted(years):
            rows = sorted(years[year], key=lambda r: (r["data"], r["id"]))
            total += len(rows)
            head_note = f"# Índice: {t.nome}, {year}"
            cols = ["", "| id | data | processo | relator | descritores | caminho |", "| --- | --- | --- | --- | --- | --- |"]
            lines = [f"| {cell(r['id'])} | {r['data']} | {cell(r['processo'])} | {cell(r['relator'])} | "
                     f"{cell('; '.join(r['descritores'][:SHARD_ROW_DESCRITORES]))} | {r['path']} |" for r in rows]
            budget = MAX_INDEX_BYTES - len(("\n".join([head_note] + cols)).encode("utf-8")) - 400
            chunks = split_lines(lines, budget)
            names = []
            for i, chunk in enumerate(chunks):
                name = f"indice-{tid}-{year}" + (f"-{suffix(i)}" if len(chunks) > 1 else "") + ".md"
                start = sum(len(c) for c in chunks[:i])
                part = rows[start:start + len(chunk)]
                note = [head_note + (f" (parte {suffix(i)})" if len(chunks) > 1 else ""), "",
                        f"{len(chunk)} decisões, de {part[0]['data']} a {part[-1]['data']}, por data. "
                        f"Cada linha: id, data, processo, relator, descritores (até {SHARD_ROW_DESCRITORES}) e o ficheiro da decisão.", ""] + cols[1:]
                shard_file(root, name, note, chunk)
                names.append((name, part))
                files += 1
                for r in part:
                    for d in {fold(x).strip(" .;") for x in r["descritores"] if fold(x).strip(" .;")}:
                        e = desc[d]
                        e[0] += 1
                        e[1][name] += 1
            rows_total += len(rows)
            if len(names) == 1:
                year_lines.append(f"| {year} | {fmt(len(rows))} | [{names[0][0]}]({names[0][0]}) |")
            else:
                year_lines.append(f"| {year} | {fmt(len(rows))} | {len(names)} ficheiros, por data: "
                                  f"[{names[0][0]}]({names[0][0]}) … [{names[-1][0]}]({names[-1][0]}) |")
                for name, part in names:
                    year_lines.append(f"| ↳ {name[:-3].rsplit('-', 1)[1]} | {fmt(len(part))} | [{name}]({name}), "
                                      f"{part[0]['data']} a {part[-1]['data']} |")
        head = [f"# Índice: {t.nome}", "", f"{fmt(total)} decisões. Um ficheiro por ano (ou vários, por data, quando o ano é grande).",
                "", "| ano | decisões | ficheiro |", "| --- | ---: | --- |"]
        budget = MAX_INDEX_BYTES - len("\n".join(head).encode("utf-8")) - 400
        pieces = split_lines(year_lines, budget)
        pnames = []
        for i, piece in enumerate(pieces):
            name = f"indice-{tid}.md" if len(pieces) == 1 else f"indice-{tid}-{i + 1}.md"
            shard_file(root, name, head, piece)
            pnames.append(name)
            files += 1
        links = ", ".join(f"[{n}]({n})" for n in pnames)
        summary.append(f"| {t.nome} | {tid} | {fmt(total)} | {min(years) if min(years) == max(years) else min(years) + "-" + max(years)} | {links} |")

    atomic_write(root / "indice.md", "\n".join([
        "# Índice de jurisprudência", "",
        "Sumários e metadados das decisões publicadas no DGSI. Abre o ficheiro do tribunal, depois o do ano, e só então a decisão.",
        "Para procurar por tema, usa [descritores.md](descritores.md).", "",
        "| tribunal | id | decisões | anos | ficheiros |", "| --- | --- | ---: | --- | --- |", *summary]) + "\n")
    files += 1
    files += write_descritores(root, desc)
    return {"files": files, "rows": rows_total}


def write_descritores(root, desc):
    """descritores.md and the files below it. Returns the number of files written."""
    keys = sorted(desc)
    lines = []
    for k in keys:
        n, shards = desc[k]
        top = sorted(shards, key=lambda s: (-shards[s], s))
        shown = ", ".join(f"[{s[7:-3]}]({s})" for s in top[:SHARDS_PER_DESCRITOR])
        more = f" +{len(top) - SHARDS_PER_DESCRITOR}" if len(top) > SHARDS_PER_DESCRITOR else ""
        lines.append(f"| {cell(k)} | {fmt(n)} | {shown}{more} |")
    head = ["# Descritores", "", "Descritor (sem acentos nem maiúsculas) | decisões | ficheiros de índice que o contêm (os com mais decisões primeiro).",
            "", "| descritor | decisões | índice |", "| --- | ---: | --- |"]
    budget = MAX_INDEX_BYTES - len("\n".join(head).encode("utf-8")) - 400
    written, counters = 0, defaultdict(int)
    level = []  # (file name, first key, last key, rows)
    for chunk, start in zip(split_lines(lines, budget), _starts(split_lines(lines, budget))):
        first, last = keys[start], keys[start + len(chunk) - 1]
        c = first[:1] if first[:1].isalpha() else "0"
        counters[c] += 1
        name = f"descritores-{c}-{counters[c]}.md"
        shard_file(root, name, head, chunk)
        written += 1
        level.append((name, first, last, len(chunk)))
    depth = 0
    while True:
        dhead = ["# Descritores", "", "| de | a | descritores | ficheiro |", "| --- | --- | ---: | --- |"]
        dlines = [f"| {cell(a)} | {cell(b)} | {fmt(n)} | [{name}]({name}) |" for name, a, b, n in level]
        budget = MAX_INDEX_BYTES - len("\n".join(dhead).encode("utf-8")) - 400
        chunks = split_lines(dlines, budget)
        if len(chunks) == 1:
            shard_file(root, "descritores.md", dhead, chunks[0])
            return written + 1
        depth += 1
        nxt = []
        for i, (chunk, start) in enumerate(zip(chunks, _starts(chunks))):
            name = f"descritores-d{depth}-{i + 1}.md"
            shard_file(root, name, dhead, chunk)
            written += 1
            nxt.append((name, level[start][1], level[start + len(chunk) - 1][2], sum(x[3] for x in level[start:start + len(chunk)])))
        level = nxt


def _starts(chunks):
    out, n = [], 0
    for c in chunks:
        out.append(n)
        n += len(c)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--config", default=None)
    a = ap.parse_args(argv)
    r = build_all(a.root, a.config)
    print(f"{r['files']} index files for {r['rows']} decisions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
