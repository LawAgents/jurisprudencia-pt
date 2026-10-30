"""Generate COBERTURA.md and estatisticas.html from the front matter of the published decision files.

Usage: python -I scripts/estatisticas.py --repo DIR --name "Jurisprudência portuguesa (DGSI)" [--excluded excluded.json]

Only the head of each file is read, so the numbers are exactly what is published. estatisticas.html is one file: no
server, no external script, no external font, dark mode included.
"""
import argparse
import collections
import html
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NO_SUMMARY, iter_decision_files, load_tribunais, read_frontmatter  # noqa: E402


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "| " + " | ".join(["---"] + ["---:"] * (len(head) - 1)) + " |"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def fmt(n):
    return f"{n:,}".replace(",", ".")


def pct(a, b):
    return f"{100 * a / b:.1f}".replace(".", ",") + " %" if b else "0 %"


def bars(items):
    top = max((v for _, v in items), default=1) or 1
    return "\n".join(
        f'<div class="row"><span class="k">{html.escape(str(k))}</span><span class="bar"><i style="width:{100 * v / top:.1f}%"></i></span>'
        f'<span class="v">{fmt(v)}</span></div>' for k, v in items)


def scan(repo, tribunais):
    """Counters over the published files."""
    c = {k: collections.Counter() for k in ("tribunal", "year", "decade", "relator", "descritor", "nosum", "tribunal_nosum",
                                            "texto_integral")}
    files = size = 0
    for p in iter_decision_files(repo, tribunais):
        meta, head = read_frontmatter(p)
        files += 1
        size += p.stat().st_size
        t = meta["tribunal"]
        year = str(meta["data"])[:4]
        c["tribunal"][t] += 1
        c["year"][year] += 1
        c["decade"][year[:3] + "0"] += 1
        if meta.get("relator"):
            c["relator"][meta["relator"]] += 1
        for d in meta.get("descritores", []):
            c["descritor"][d.strip(" .;").lower()] += 1
        if NO_SUMMARY in head:
            c["nosum"]["total"] += 1
            c["tribunal_nosum"][t] += 1
        if meta.get("texto_integral"):
            c["texto_integral"][meta["texto_integral"]] += 1
    return c, files, size


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--excluded", help="excluded.json of the raw cache (decisions left out or with the sumário replaced, and why)")
    a = ap.parse_args(argv)
    repo = Path(a.repo)
    tribunais = load_tribunais((Path(a.config) if a.config else repo / "config") / "tribunais.txt")
    c, files, size = scan(repo, tribunais)
    today = date.today().isoformat()
    n = files
    by_t = [(tribunais[k].nome, v) for k, v in c["tribunal"].most_common()]
    nosum = c["nosum"]["total"]
    nosum_rows = [(tribunais[k].nome, fmt(v), fmt(c["tribunal"][k]), pct(v, c["tribunal"][k]))
                  for k, v in c["tribunal_nosum"].most_common()]

    md = [f"# Cobertura: {a.name}", "",
          f"Números medidos nos cabeçalhos dos ficheiros publicados em {today}. Gerado por `scripts/estatisticas.py`.", "",
          f"- Decisões: **{fmt(n)}**, em {fmt(files)} ficheiros ({size / 1e6:.0f} MB sem compressão).",
          f"- Sem sumário publicado: {fmt(nosum)} ({pct(nosum, n)}). Nesses ficheiros há só os metadados e a ligação à fonte.", "",
          "## Por tribunal", "", table([(k, fmt(v), pct(v, n)) for k, v in by_t], ["Tribunal", "Decisões", "Parte"]), "",
          "## Por década", "", table([(k, fmt(v)) for k, v in sorted(c["decade"].items())], ["Década", "Decisões"]), "",
          "## Por ano (os 15 anos com mais decisões)", "", table([(k, fmt(v)) for k, v in c["year"].most_common(15)], ["Ano", "Decisões"]), "",
          "## Relatores com mais decisões (os 20 primeiros)", "", table([(k, fmt(v)) for k, v in c["relator"].most_common(20)], ["Relator", "Decisões"]), "",
          "## Descritores mais usados (os 30 primeiros)", "", table([(k, fmt(v)) for k, v in c["descritor"].most_common(30)], ["Descritor", "Decisões"]), "",
          "## Sem sumário, por tribunal", "", table(nosum_rows, ["Tribunal", "Sem sumário", "Total", "Parte"]), ""]
    if c["texto_integral"]:
        md += ["## Campo «Texto Integral» tal como publicado", "", table([(k, fmt(v)) for k, v in c["texto_integral"].most_common()], ["Valor", "Decisões"]),
               "", "O campo só existe com S ou N em alguns tribunais; nos outros fica de fora do cabeçalho.", ""]
    if a.excluded and Path(a.excluded).exists():
        ex = json.loads(Path(a.excluded).read_text(encoding="utf-8"))
        why = collections.Counter((e.get("reason", "?"), "sim" if e.get("kept") else "não") for e in ex)
        md += ["## Páginas descarregadas que ficaram de fora ou foram alteradas", ""]
        if ex:
            md += [f"{fmt(len(ex))} páginas:", "",
                   table([(r, k, fmt(v)) for (r, k), v in why.most_common()], ["Motivo", "Decisão publicada", "Páginas"]), ""]
        else:
            md += ["Nenhuma página descarregada ficou de fora nem teve o sumário substituído.", ""]
    md += ["Para ver em gráficos, abre `estatisticas.html` no navegador.", ""]
    (repo / "COBERTURA.md").write_text("\n".join(md), encoding="utf-8", newline="\n")

    decs = sorted(c["decade"].items())
    biggest = max(c["decade"].values(), default=1)
    page = f"""<!doctype html>
<html lang="pt-PT"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Estatísticas: {html.escape(a.name)}</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--bar:#2a5db0;--trk:#e8ecf3}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14161a;--fg:#e8e8e8;--mut:#9aa0aa;--bar:#6b9be8;--trk:#252a33}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:880px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.6rem;margin:0 0 4px}}h2{{font-size:1.1rem;margin:32px 0 8px}}p{{color:var(--mut);margin:4px 0}}
.kpis{{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}}.kpi{{background:var(--trk);border-radius:8px;padding:10px 16px}}
.kpi b{{display:block;font-size:1.5rem}}
.row{{display:grid;grid-template-columns:minmax(120px,38%) 1fr 70px;gap:8px;align-items:center;margin:3px 0}}
.k{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.bar{{background:var(--trk);height:14px;border-radius:7px;overflow:hidden}}
.bar i{{display:block;height:100%;background:var(--bar)}}.v{{text-align:right;color:var(--mut);font-variant-numeric:tabular-nums}}
.cols{{display:flex;align-items:flex-end;gap:6px;height:180px;margin-top:8px}}.col{{flex:1;text-align:center;font-size:12px}}
.col i{{display:block;background:var(--bar);border-radius:4px 4px 0 0}}.col span{{display:block;color:var(--mut)}}
@media (max-width:520px){{.row{{grid-template-columns:1fr 1fr 60px}}}}
</style></head><body><main>
<h1>{html.escape(a.name)}</h1>
<p>Números medidos nos cabeçalhos dos ficheiros publicados em {today}. Sem valor legal: confirma sempre na fonte (DGSI).</p>
<div class="kpis"><div class="kpi"><b>{fmt(n)}</b>decisões</div><div class="kpi"><b>{size / 1e6:.0f} MB</b>de texto</div>
<div class="kpi"><b>{len(c["tribunal"])}</b>tribunais</div><div class="kpi"><b>{pct(nosum, n)}</b>sem sumário</div></div>
<h2>Por tribunal</h2>
{bars(by_t)}
<h2>Por década</h2>
<div class="cols">{''.join(f'<div class="col"><span>{fmt(v)}</span><i style="height:{150 * v / biggest:.0f}px"></i>{k}</div>' for k, v in decs)}</div>
<h2>Anos com mais decisões</h2>
{bars(c["year"].most_common(12))}
<h2>Relatores com mais decisões</h2>
{bars(c["relator"].most_common(20))}
<h2>Descritores mais usados</h2>
{bars(c["descritor"].most_common(30))}
<h2>Sem sumário, por tribunal</h2>
{bars([(tribunais[k].nome, v) for k, v in c["tribunal_nosum"].most_common()])}
</main></body></html>
"""
    (repo / "estatisticas.html").write_text(page, encoding="utf-8", newline="\n")
    print(f"{n} decisions, {files} files -> COBERTURA.md, estatisticas.html")


if __name__ == "__main__":
    main()
