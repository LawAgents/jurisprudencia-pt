import json
import unittest
from pathlib import Path

from helpers import TmpCase, REPO, VIEW, unid
import estatisticas
from common import LEGAL_NOTICE, NO_SUMMARY, TEXT_VERSION, format_frontmatter


class Stats(TmpCase):
    def put(self, tid, n, year, relator, desc, summary):
        did = f"{tid}-{n}-{year}-03-04"
        m = {"id": did, "title": "T", "tribunal": tid, "processo": str(n), "relator": relator, "data": f"{year}-03-04", "descritores": desc,
             "texto_integral": "S", "source": f"https://www.dgsi.pt/jstj.nsf/{VIEW}/{unid(n)}?OpenDocument", "retrieved": "2026-10-22",
             "text_version": TEXT_VERSION, "legal_notice": LEGAL_NOTICE}
        p = self.tmp / tid / str(year) / f"{did}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(format_frontmatter(m) + f"\n\n# T\n\n## Sumário\n\n{summary}\n", encoding="utf-8", newline="\n")

    def test_counts_and_files(self):
        self.put("stj", 1, 2020, "JUIZ A", ["Recurso", "Doação"], "I - x")
        self.put("stj", 2, 2021, "JUIZ A", ["Recurso"], NO_SUMMARY)
        self.put("trp", 3, 2021, "JUIZ B", [], NO_SUMMARY)
        (self.tmp / "excluded.json").write_text(json.dumps([{"tribunal": "stj", "unid": "x", "kept": False, "reason": "sem data"}]), encoding="utf-8")
        estatisticas.main(["--repo", str(self.tmp), "--config", str(REPO / "config"), "--name", "Teste", "--excluded", str(self.tmp / "excluded.json")])
        md = (self.tmp / "COBERTURA.md").read_text(encoding="utf-8")
        self.assertIn("Decisões: **3**", md)
        self.assertIn("Sem sumário publicado: 2 (66,7 %)", md)
        self.assertIn("| JUIZ A | 2 |", md)
        self.assertIn("| recurso | 2 |", md)
        self.assertIn("| 2020 | 1 |", md)
        self.assertIn("sem data", md)
        html = (self.tmp / "estatisticas.html").read_text(encoding="utf-8")
        self.assertIn("prefers-color-scheme:dark", html)
        self.assertNotIn("<script", html)


if __name__ == "__main__":
    unittest.main()
