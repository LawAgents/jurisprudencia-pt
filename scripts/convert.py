#!/usr/bin/env python3
"""Convert the raw DGSI pages into one markdown file per decision: metadata and sumário only, never the full text.

  python scripts/convert.py --raw DIR --out DIR [--config DIR] [--workers 1]

Output: <out>/<tribunal>/<year>/<id>.md, with front matter (see common.FIELDS) and the body
  # <tribunal>, processo <p>, <data>
  ## Sumário
  <sumário as published, reflowed only>      or      Sem sumário publicado. Texto integral na fonte.

Only fields the DGSI publishes are copied. Nothing is anonymised or de-anonymised, and the parties' names, the
'Decisão Texto Integral' text and every other text field are left out.
"""
import argparse
import json
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (LEGAL_NOTICE, MAX_SUMMARY_CHARS, NO_SUMMARY, SUMMARY_HEADING, TEXT_VERSION, HOST, atomic_write, format_frontmatter,  # noqa: E402
                    gz_mtime_date, load_retirada, load_tribunais, read_gz, slug)
from dgsi_html import one_line, parse_fields, text_lines, us_date  # noqa: E402

DATE_KEYS = ("data do acordao", "data da sentenca", "data da decisao", "data da decisao sumaria")
# Field that holds the section/chamber, per tribunal (when the DGSI publishes one).
SECAO_FIELD = {"sta": "tribunal", "conflitos": "tribunal", "tcas": "seccao", "trp": "indicacoes eventuais",
               "trg": "indicacoes eventuais"}
DOC_NUMBER_DATE = re.compile(r"^[A-Za-z]{2}\d?((?:19|20)\d{2})(\d{2})(\d{2})")


class Unusable(Exception):
    """The page cannot become a decision file; the message is the reason."""


def doc_number_date(s):
    m = DOC_NUMBER_DATE.match((s or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def parse_decision(raw, t):
    """Decision fields of one page: dict with processo, relator, data (ISO or None), votacao, meio_processual, decisao,
    descritores, texto_integral, privacidade, secao, sumario (list of paragraphs). Raises Unusable."""
    f = parse_fields(raw)
    line = lambda k: one_line(f.get(k, ""))  # noqa: E731
    processo = line("processo")
    if not processo:
        raise Unusable("sem processo")
    data = next((us_date(line(k)) for k in DATE_KEYS if us_date(line(k))), None) or doc_number_date(line("n do documento"))
    ti = line("texto integral").upper()
    secao = line(SECAO_FIELD[t.id]) if t.id in SECAO_FIELD else ""
    if t.id in ("trp", "trg") and not re.search(r"sec", secao, re.I):
        secao = ""
    sumario = text_lines(f.get("sumario", ""))
    too_long = sum(len(x) for x in sumario) > MAX_SUMMARY_CHARS
    return {
        "processo": processo, "relator": line("relator"), "data": data, "votacao": line("votacao"),
        "meio_processual": line("meio processual"), "decisao": line("decisao"),
        "descritores": list(dict.fromkeys(text_lines(f.get("descritores", "")))),
        "texto_integral": ti if ti in ("S", "N") else "", "privacidade": line("privacidade"), "secao": secao,
        "sumario": [] if too_long else sumario, "sumario_replaced": too_long,
    }


def ecli_for(t, processo, data):
    """ECLI as the CSM portal builds it (/ecli/ECLI:PT:<tribunal>:<year>:<processo with / and - turned into .>/), only
    for the tribunais whose pattern was confirmed (non-empty sigla in config/tribunais.txt)."""
    if not t.sigla or not slug(processo):
        return None
    number = re.sub(r"[/-]", ".", re.sub(r"\s+", "", processo))
    return f"ECLI:PT:{t.sigla}:{data[:4]}:{number}"


def render(t, d, decision_id, source, retrieved):
    """Markdown text of one decision file."""
    title = f"{t.nome}, processo {d['processo']}, {d['data']}"
    ecli = ecli_for(t, d["processo"], d["data"])
    meta = {
        "id": decision_id, "title": title, "tribunal": t.id, "secao": d["secao"], "processo": d["processo"],
        "relator": d["relator"], "data": d["data"], "votacao": d["votacao"], "meio_processual": d["meio_processual"],
        "decisao": d["decisao"], "descritores": d["descritores"], "texto_integral": d["texto_integral"],
        "privacidade": d["privacidade"], "source": source, "ecli": ecli, "ecli_confirmed": bool(ecli),
        "retrieved": retrieved, "text_version": TEXT_VERSION, "legal_notice": LEGAL_NOTICE,
    }
    body = "\n\n".join(d["sumario"]) if d["sumario"] else NO_SUMMARY
    return f"{format_frontmatter(meta)}\n\n# {title}\n\n{SUMMARY_HEADING}\n\n{body}\n"


def _work(args):
    """Process-pool worker: one cached page -> ('ok', unid, decision) or ('err', unid, reason)."""
    path, tid, config = args
    unid = Path(path).name.removesuffix(".html.gz")
    try:
        t = _TRIBUNAIS(config)[tid]
        d = parse_decision(read_gz(path), t)
        d["retrieved"] = gz_mtime_date(path)
        return "ok", unid, d
    except Unusable as e:
        return "err", unid, str(e)
    except Exception as e:  # noqa: BLE001  a weird page is excluded and reported, it never stops the others
        return "err", unid, f"erro ao ler a página: {type(e).__name__}: {e}"


_CACHE = {}


def _TRIBUNAIS(config):  # noqa: N802
    if config not in _CACHE:
        _CACHE[config] = load_tribunais(Path(config) / "tribunais.txt")
    return _CACHE[config]


def assign_ids(items):
    """items: [(unid, base_id)] -> {unid: final id}. The smallest unid of a group keeps the plain id; the others get the
    first 8 characters of their unid appended (only on collision)."""
    groups = {}
    for unid, base in items:
        groups.setdefault(base, []).append(unid)
    out = {}
    for base, unids in groups.items():
        for i, unid in enumerate(sorted(unids)):
            out[unid] = base if i == 0 else f"{base}-{unid[:8]}"
    return out


def convert_all(raw_dir, out_dir, config, workers=1, only=None, retirada=None):
    """Convert every cached page. Returns (written: {tribunal: n}, excluded: [{tribunal, unid, reason}], retired: n)."""
    raw_dir, out_dir, config = Path(raw_dir), Path(out_dir), Path(config)
    tribunais = load_tribunais(config / "tribunais.txt")
    retirada = load_retirada(config / "retirada.txt") if retirada is None else retirada
    written, excluded, retired = {}, [], 0
    for t in tribunais.values():
        if only not in (None, t.id, t.db):
            continue
        files = sorted((raw_dir / "pages" / t.db).glob("*.html.gz")) if (raw_dir / "pages" / t.db).is_dir() else []
        lst = json.loads(read_gz(raw_dir / "lists" / f"{t.db}.json.gz")) if (raw_dir / "lists" / f"{t.db}.json.gz").exists() else {"rows": {}}
        tasks = [(str(p), t.id, str(config)) for p in files]
        if workers > 1 and len(tasks) > 200:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                results = list(ex.map(_work, tasks, chunksize=200))
        else:
            results = [_work(x) for x in tasks]
        good = []
        for kind, unid, d in results:
            row = lst["rows"].get(unid)
            if kind == "err":
                excluded.append({"tribunal": t.id, "unid": unid, "kept": False, "reason": d})
                continue
            if not d["data"] and row and row.get("data"):
                d["data"] = row["data"]
            if not d["data"]:
                excluded.append({"tribunal": t.id, "unid": unid, "kept": False, "reason": "sem data"})
                continue
            if not row:
                excluded.append({"tribunal": t.id, "unid": unid, "kept": False, "reason": "página fora da lista (sem ligação à fonte)"})
                continue
            if d["sumario_replaced"]:
                excluded.append({"tribunal": t.id, "unid": unid, "kept": True,
                                 "reason": f"sumário com mais de {MAX_SUMMARY_CHARS} caracteres (provável texto integral): substituído pela frase fixa"})
            base = f"{t.id}-{slug(d['processo']) or 'sem-processo'}-{d['data']}"
            good.append((unid, base, d, row["path"]))
        ids = assign_ids([(u, b) for u, b, _, _ in good])
        n = 0
        for unid, base, d, path in good:
            did = ids[unid]
            if did in retirada or base in retirada:
                retired += 1
                continue
            source = f"{HOST}{path}?OpenDocument"
            atomic_write(out_dir / t.id / d["data"][:4] / f"{did}.md", render(t, d, did, source, d["retrieved"]))
            n += 1
        written[t.id] = n
    return written, excluded, retired


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "config"))
    ap.add_argument("--db", default=None)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args(argv)
    written, excluded, retired = convert_all(a.raw, a.out, a.config, a.workers, a.db)
    atomic_write(Path(a.raw) / "excluded.json", json.dumps(excluded, ensure_ascii=False, indent=1))
    dropped = [e for e in excluded if not e["kept"]]
    print(f"{sum(written.values())} decision files written, {len(dropped)} excluded, {len(excluded) - len(dropped)} sumários replaced "
          f"by the fixed sentence, {retired} left out by config/retirada.txt")
    for e in dropped[:20]:
        print(f"  excluded {e['tribunal']}/{e['unid']}: {e['reason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
