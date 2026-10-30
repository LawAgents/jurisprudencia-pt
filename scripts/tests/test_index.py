import re
import unittest
from pathlib import Path

from helpers import TmpCase, VIEW, unid
import build_index
from common import LEGAL_NOTICE, NO_SUMMARY, TEXT_VERSION, format_frontmatter, slug


class Index(TmpCase):
    def decision(self, tid, n, year, desc, processo=None):
        proc = processo or f"{n}/{year % 100}.1T8LSB"
        did = f"{tid}-{slug(proc)}-{year}-03-04"
        m = {"id": did, "title": f"T, processo {proc}, {year}-03-04", "tribunal": tid, "processo": proc, "relator": "JUIZ INVENTADO",
             "data": f"{year}-03-04", "descritores": desc, "source": f"https://www.dgsi.pt/jstj.nsf/{VIEW}/{unid(n)}?OpenDocument",
             "retrieved": "2026-10-22", "text_version": TEXT_VERSION, "legal_notice": LEGAL_NOTICE}
        p = self.tmp / "root" / tid / str(year) / f"{did}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(format_frontmatter(m) + f"\n\n# {m['title']}\n\n## Sumário\n\n{NO_SUMMARY}\n", encoding="utf-8", newline="\n")

    def build(self):
        return build_index.build_all(self.tmp / "root", Path(__file__).resolve().parents[2] / "config")

    def index_files(self):
        return sorted((self.tmp / "root").glob("*.md"))

    def test_every_index_file_is_at_most_40_kb_and_a_big_year_is_split_in_date_order(self):
        long_desc = ["DESCRITOR MUITO LONGO NUMERO %d PARA ENCHER O FICHEIRO" % i for i in range(8)]
        for n in range(1, 701):
            self.decision("stj", n, 2020, long_desc + [f"UNICO {n}"])
        for n in range(1, 4):
            self.decision("stj", 5000 + n, 2019, ["POUCOS"])
            self.decision("trp", n, 2019, ["POUCOS"])
        r = self.build()
        self.assertEqual(r["rows"], 706)
        for f in self.index_files():
            self.assertLessEqual(f.stat().st_size, 40 * 1024, f.name)
        shards = sorted(p.name for p in (self.tmp / "root").glob("indice-stj-2020-*.md"))
        self.assertGreater(len(shards), 1)
        self.assertEqual(shards[:2], ["indice-stj-2020-a.md", "indice-stj-2020-b.md"])
        self.assertTrue((self.tmp / "root" / "indice-stj-2019.md").exists())  # small year: one file, no suffix
        rows = 0
        for s in shards:
            rows += sum(1 for ln in (self.tmp / "root" / s).read_text(encoding="utf-8").splitlines() if ln.startswith("| stj-"))
        self.assertEqual(rows, 700)

    def test_row_format_and_first_six_descritores(self):
        self.decision("stj", 1, 2020, [f"D{i}" for i in range(9)], processo="1571/19.3T8OAZ-E.P1.S1")
        self.build()
        text = (self.tmp / "root" / "indice-stj-2020.md").read_text(encoding="utf-8")
        row = next(ln for ln in text.splitlines() if ln.startswith("| stj-"))
        cells = [c.strip() for c in row.strip("|").split("|")]
        self.assertEqual(cells[0], "stj-1571-19-3t8oaz-e-p1-s1-2020-03-04")
        self.assertEqual(cells[1:4], ["2020-03-04", "1571/19.3T8OAZ-E.P1.S1", "JUIZ INVENTADO"])
        self.assertEqual(cells[4], "D0; D1; D2; D3; D4; D5")
        self.assertEqual(cells[5], "stj/2020/stj-1571-19-3t8oaz-e-p1-s1-2020-03-04.md")

    def test_layers_link_down(self):
        self.decision("stj", 1, 2020, ["A"])
        self.decision("trp", 1, 2021, ["A"])
        self.build()
        root = (self.tmp / "root" / "indice.md").read_text(encoding="utf-8")
        self.assertIn("indice-stj.md", root)
        self.assertIn("indice-trp.md", root)
        self.assertIn("descritores.md", root)
        self.assertIn("indice-stj-2020.md", (self.tmp / "root" / "indice-stj.md").read_text(encoding="utf-8"))

    def test_descritores_are_folded_counted_and_mapped_to_shards(self):
        self.decision("stj", 1, 2020, ["Doação", "RECURSO"])
        self.decision("stj", 2, 2020, ["DOAÇÃO."])
        self.decision("trp", 1, 2021, ["doacao"])
        self.build()
        leaf = (self.tmp / "root" / "descritores-d-1.md").read_text(encoding="utf-8")
        row = next(ln for ln in leaf.splitlines() if ln.startswith("| doacao "))
        self.assertIn("| 3 |", row)
        self.assertIn("stj-2020", row)
        self.assertIn("trp-2021", row)
        self.assertIn("doacao", (self.tmp / "root" / "descritores.md").read_text(encoding="utf-8"))

    def test_descritores_layers_split_when_big(self):
        old = build_index.MAX_INDEX_BYTES
        build_index.MAX_INDEX_BYTES = 1200  # small limit, so that directory levels appear with few files
        self.addCleanup(setattr, build_index, "MAX_INDEX_BYTES", old)
        for n in range(1, 241):
            self.decision("stj", n, 2000 + n % 20, [f"descritor numero {n:05d} com um nome comprido"])
        self.build()
        top = self.tmp / "root" / "descritores.md"
        self.assertLessEqual(top.stat().st_size, 1200)
        for f in self.index_files():
            self.assertLessEqual(f.stat().st_size, 1200, f.name)
        self.assertTrue(list((self.tmp / "root").glob("descritores-d1-*.md")))  # a directory level between top and leaves
        # every link of every descritores file points at a file that exists, and every leaf is reachable from the top
        seen, todo = set(), ["descritores.md"]
        while todo:
            name = todo.pop()
            for link in re.findall(r"\]\((descritores-[^)]+\.md)\)", (self.tmp / "root" / name).read_text(encoding="utf-8")):
                self.assertTrue((self.tmp / "root" / link).exists(), link)
                if link not in seen:
                    seen.add(link)
                    todo.append(link)
        leaves = {p.name for p in (self.tmp / "root").glob("descritores-?-*.md")}
        self.assertTrue(leaves and leaves <= seen)

    def test_suffixes(self):
        self.assertEqual([build_index.suffix(i) for i in (0, 1, 25, 26, 27)], ["a", "b", "z", "aa", "ab"])


if __name__ == "__main__":
    unittest.main()
