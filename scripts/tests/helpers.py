"""Shared test helpers: fake DGSI pages (latin-1, like the real ones, with invented people), a fake clock and a fake server."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from common import load_tribunais  # noqa: E402
from dgsi_client import Dgsi  # noqa: E402

VIEW = "954f0ce6ad9dd8b980256b5f003fa814"


def tribunais(*ids):
    t = load_tribunais(REPO / "config" / "tribunais.txt")
    return {k: v for k, v in t.items() if not ids or k in ids}


def latin1(s):
    """Encode like the DGSI: latin-1, numeric entities for what latin-1 cannot hold."""
    return s.encode("latin-1", errors="xmlcharrefreplace")


def unid(n):
    return f"{n:032x}"


def label(name, bg="71B2CF", width="26%"):
    return (f'<tr valign="top"><td width="{width}" bgcolor="#{bg}"><b><font size="2" color="#FFFFFF">{name}:</font></b></td>')


def value(html, bg="E0F1FF"):
    return f'<td width="74%" bgcolor="#{bg}"><b><font size="2"> </font></b><b><font size="2" color="#000080">{html}</font></b></td></tr>\n'


def page_html(processo="1571/19.3T8OAZ-E.P1.S1", relator="MARIA INVENTADA SILVA", data="10/20/2026",
              descritores=("RECURSO DE REVISTA", "DOAÇÃO"), sumario=("I - A doação de imóveis exige escritura pública.",
                                                                     "II - A falta de forma torna o negócio nulo – art. 947.º."),
              texto_integral="S", full_text="Acordam em conferência. O autor Manuel Exemplo, residente na Rua Fictícia, pede a condenação.",
              extra_fields=(), label_bg="71B2CF", with_sumario=True):
    rows = [
        f'<tr valign="top"><td width="26%" bgcolor="#{label_bg}"><div align="center"><b><font size="4">Acórdão do Supremo Tribunal de Justiça</font></b></div></td></tr>',
        label("Processo", label_bg) + '<td width="74%" bgcolor="#E0F1FF"><table width="100%"><tr valign="top"><td width="50%"><b><font size="2" color="#000080">'
        + processo + '</font></b></td></tr></table></td></tr>\n',
        label("Relator", label_bg) + value(relator),
        label("Descritores", label_bg) + value("<br>\n".join(descritores)),
        label("Data do Acórdão", label_bg) + value(data),
        label("Votação", label_bg) + value("UNANIMIDADE"),
        label("Texto Integral", label_bg) + value(texto_integral),
        label("Privacidade", label_bg) + value("1"),
        label("Meio Processual", label_bg) + value("REVISTA"),
        label("Decisão", label_bg) + value("NEGADA A REVISTA"),
        '<tr valign="top"><td width="26%" bgcolor="#FFFFFF"><img width="1" height="1" src="/icons/ecblank.gif"></td>'
        '<td width="74%" bgcolor="#FFFFFF"><img width="1" height="1" src="/icons/ecblank.gif"></td></tr>',
    ]
    for name, text in extra_fields:
        rows.append(label(name, label_bg) + value(text))
    if with_sumario:
        body = "<br>\n".join(f'<font color="#000080">{p}</font>' for p in sumario)
        rows.append(label("Sumário", label_bg) + f'<td width="74%" bgcolor="#E0F1FF"><font size="2" color="#000080" face="Arial">{body}</font></td></tr>\n')
    rows.append(label("Reclamações", "6699CC") + '<td width="74%" bgcolor="#CCFFFF"><b><font size="2"> </font></b></td></tr>\n')
    rows.append(label("Decisão Texto Integral", label_bg) + f'<td width="74%" bgcolor="#FFFFFF"><font size="2">{full_text}</font></td></tr>\n')
    html = ('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">\n<html>\n<head>\n<title>Acórdão</title></head>\n<body>\n'
            '<table width="100%" border="0">\n' + "\n".join(rows) + "\n</table>\n</body>\n</html>\n")
    return latin1(html)


def list_html(db, rows, next_start=None, header=True):
    """rows: [(unid, processo, relator, descritores list, 'MM/DD/YYYY')]."""
    out = ['<html><head><title>Por Ano</title></head><body><table>']
    if header:
        out.append("<tr><th><font size=\"2\">SESSÃO</font></th><th><font size=\"2\">PROCESSO</font></th><th><font size=\"2\">RELATOR</font></th>"
                   "<th><font size=\"2\">DESCRITOR</font></th></tr>")
    for u, proc, rel, desc, d in rows:
        out.append(f'<tr valign="top"><td nowrap><img width="16" height="1" src="/icons/ecblank.gif"><font size="2">{d}</font></td>'
                   f'<td nowrap><font size="2"><a href="/{db}.nsf/{VIEW}/{u}?OpenDocument">{proc}</a></font></td>'
                   f'<td nowrap><font size="2">{rel}</font></td><td nowrap><font size="2">{"<br>".join(desc)}</font></td></tr>')
    out.append("</table>")
    if next_start:
        out.append(f'<div align="center"><a href="/{db}.nsf?OpenDatabase&amp;Start=1"><b><font size="2" color="#800080">Anterior</font></b></a>'
                   f'<a href="/{db}.nsf?OpenDatabase&amp;Start={next_start}"><b><font size="2" color="#800080">Seguinte</font></b></a></div>')
    out.append("</body></html>")
    return latin1("\n".join(out))


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.now += s


class FakeServer:
    """A tiny DGSI: databases with decisions listed newest first, `per_page` per listing page. Records every request."""

    def __init__(self, clock=None, per_page=3):
        self.clock, self.per_page = clock, per_page
        self.dbs = {}  # db -> [dict(unid, processo, relator, data, descritores, sumario...)]
        self.requests = []  # (url, headers)
        self.errors = {}  # url substring -> list of statuses to answer before behaving
        self.delay = {}  # url substring -> seconds the answer takes (advances the fake clock)

    def add(self, db, n, start=1, **kw):
        """n decisions with unids start..start+n-1, newest first."""
        lst = self.dbs.setdefault(db, [])
        for i in range(n):
            k = start + i
            lst.append({"unid": unid(k), "processo": f"{k}/20.1T8LSB", "relator": "JUIZ INVENTADO", "data": "10/%02d/2026" % (28 - (k % 27)),
                        "descritores": ["DESCRITOR A", f"DESCRITOR {k % 3}"], **kw})

    def transport(self, url, headers):
        self.requests.append((url, dict(headers)))
        for sub, secs in self.delay.items():
            if sub in url and self.clock:
                self.clock.sleep(secs)
        for sub, statuses in self.errors.items():
            if sub in url and statuses:
                return statuses.pop(0), b"error"
        m = re.match(r"https://www\.dgsi\.pt/([a-z0-9]+)\.nsf\?OpenDatabase&Start=(\d+)$", url)
        if m:
            db, start = m.group(1), int(m.group(2))
            docs = self.dbs.get(db, [])
            page = (start - 1) // self.per_page if start > 1 else 0
            chunk = docs[page * self.per_page:(page + 1) * self.per_page]
            nxt = (page + 1) * self.per_page + 1 if (page + 1) * self.per_page < len(docs) else None
            return 200, list_html(db, [(d["unid"], d["processo"], d["relator"], d["descritores"], d["data"]) for d in chunk], nxt)
        m = re.match(r"https://www\.dgsi\.pt/([a-z0-9]+)\.nsf/([0-9a-f]{32})\?ReadViewEntries", url)
        if m:
            return 200, f'<viewentries toplevelentries="{len(self.dbs.get(m.group(1), []))}"></viewentries>'.encode()
        m = re.match(r"https://www\.dgsi\.pt/([a-z0-9]+)\.nsf/[0-9a-f]{32}/([0-9a-f]{32})\?OpenDocument&ExpandSection=1$", url)
        if m:
            for d in self.dbs.get(m.group(1), []):
                if d["unid"] == m.group(2):
                    return 200, page_html(d["processo"], d["relator"], d["data"], d["descritores"],
                                          d.get("sumario", ("I - Sumário inventado.",)), full_text=d.get("full_text", "Texto integral inventado."))
        return 404, b"not found"

    def client(self, **kw):
        c = self.clock or FakeClock()
        self.clock = c
        return Dgsi(transport=self.transport, clock=c, sleep=c.sleep, log=lambda m: None, **kw)

    def urls(self, kind):
        return [u for u, _ in self.requests if kind in u]


class TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jur-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def config_dir(self, retirada=""):
        cfg = self.tmp / "config"
        cfg.mkdir(exist_ok=True)
        shutil.copy(REPO / "config" / "tribunais.txt", cfg / "tribunais.txt")
        (cfg / "retirada.txt").write_text(retirada, encoding="utf-8")
        return cfg


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))
