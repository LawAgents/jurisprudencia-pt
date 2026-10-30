import json
import unittest
from pathlib import Path

from helpers import TmpCase, VIEW, latin1, list_html, page_html, tribunais, unid
import convert
import dgsi_html
from common import NO_SUMMARY, MAX_SUMMARY_CHARS, gz_bytes, parse_frontmatter, read_gz
from fetch import Raw


class ListParser(unittest.TestCase):
    def test_rows_and_next_link(self):
        html = list_html("jstj", [(unid(1), "1571/19.3T8OAZ-E.P1.S1", "MARIA INVENTADA", ["RECURSO", "DOAÇÃO"], "10/20/2026"),
                                  (unid(2), "5/20.1T8LSB", "JUIZ INVENTADO", [], "01/05/2020")], next_start=151)
        rows, nxt = dgsi_html.parse_list(html)
        self.assertEqual(nxt, "/jstj.nsf?OpenDatabase&Start=151")
        self.assertEqual([r["unid"] for r in rows], [unid(1), unid(2)])
        self.assertEqual(rows[0]["data"], "2026-10-20")  # month/day/year
        self.assertEqual(rows[0]["relator"], "MARIA INVENTADA")
        self.assertEqual(rows[0]["descritores"], ["RECURSO", "DOAÇÃO"])
        self.assertEqual(rows[0]["path"], f"/jstj.nsf/{VIEW}/{unid(1)}")
        self.assertEqual(rows[1]["data"], "2020-01-05")

    def test_last_page_has_no_next_link(self):
        rows, nxt = dgsi_html.parse_list(list_html("jstj", [(unid(1), "1/20.1T8LSB", "X", [], "01/05/2020")]))
        self.assertIsNone(nxt)

    def test_list_without_header_and_with_size_instead_of_processo(self):
        # Tribunal Constitucional: date, link text '3kB', descritor
        html = ('<html><body><table><tr valign="top"><td><font size="2">10/05/1998</font></td><td><font size="2">'
                f'<a href="/atco1.nsf/{VIEW}/{unid(7)}?OpenDocument">3kB</a></font></td><td><font size="2">ELEIÇÃO.</font></td></tr></table></body></html>')
        rows, _ = dgsi_html.parse_list(latin1(html))
        self.assertEqual(rows[0]["processo"], "")
        self.assertEqual(rows[0]["descritores"], ["ELEIÇÃO."])
        self.assertEqual(rows[0]["data"], "1998-10-05")

    def test_parties_column_is_never_copied(self):
        html = ('<html><body><table><tr><th>DATA DECISÃO</th><th>PROCESSO</th><th>REU</th><th>CONTRATO</th></tr>'
                f'<tr><td>03/17/2025</td><td><a href="/jdgpj.nsf/{VIEW}/{unid(3)}?OpenDocument">116/23.5T8FLG</a></td><td>EMPRESA INVENTADA SA</td><td>CONTRATO DE SEGURO</td></tr></table></body></html>')
        rows, _ = dgsi_html.parse_list(latin1(html))
        self.assertNotIn("EMPRESA", json.dumps(rows))
        self.assertEqual(rows[0]["descritores"], [])


class PageParser(unittest.TestCase):
    def setUp(self):
        self.stj = tribunais("stj")["stj"]

    def test_fields_and_summary(self):
        d = convert.parse_decision(page_html(), self.stj)
        self.assertEqual(d["processo"], "1571/19.3T8OAZ-E.P1.S1")
        self.assertEqual(d["relator"], "MARIA INVENTADA SILVA")
        self.assertEqual(d["data"], "2026-10-20")
        self.assertEqual(d["votacao"], "UNANIMIDADE")
        self.assertEqual(d["meio_processual"], "REVISTA")
        self.assertEqual(d["decisao"], "NEGADA A REVISTA")
        self.assertEqual(d["descritores"], ["RECURSO DE REVISTA", "DOAÇÃO"])
        self.assertEqual(d["texto_integral"], "S")
        self.assertEqual(d["privacidade"], "1")
        self.assertEqual(d["sumario"], ["I - A doação de imóveis exige escritura pública.",
                                        "II - A falta de forma torna o negócio nulo – art. 947.º."])

    def test_latin1_accents_and_numeric_entities(self):
        raw = page_html(sumario=("Sumário com ç, ã, º e travessão – e aspas “x”.",))
        self.assertIn(b"&#8211;", raw)  # outside latin-1: sent as an entity
        self.assertIn("ç".encode("latin-1"), raw)
        self.assertEqual(convert.parse_decision(raw, self.stj)["sumario"], ["Sumário com ç, ã, º e travessão – e aspas “x”."])

    def test_cp1252_bytes_in_0x80_0x9f(self):
        raw = page_html(sumario=("aspas XX fim",)).replace(b"XX", b"\x93x\x94")
        self.assertEqual(convert.parse_decision(raw, self.stj)["sumario"], ["aspas “x” fim"])

    def test_missing_summary(self):
        d = convert.parse_decision(page_html(with_sumario=False), self.stj)
        self.assertEqual(d["sumario"], [])

    def test_full_text_and_parties_never_reach_the_result(self):
        d = convert.parse_decision(page_html(), self.stj)
        self.assertNotIn("Manuel Exemplo", json.dumps(d, ensure_ascii=False))
        self.assertNotIn("Acordam", json.dumps(d, ensure_ascii=False))

    def test_secondary_label_colour_does_not_leak_into_the_summary(self):
        d = convert.parse_decision(page_html(), self.stj)
        self.assertFalse(any("Reclama" in p for p in d["sumario"]))

    def test_texto_integral_other_than_s_n_is_left_out(self):
        d = convert.parse_decision(page_html(texto_integral="peca.pdf"), self.stj)
        self.assertEqual(d["texto_integral"], "")

    def test_summary_that_is_the_full_text_is_replaced(self):
        d = convert.parse_decision(page_html(sumario=("palavra " * (MAX_SUMMARY_CHARS // 7 + 10),)), self.stj)
        self.assertEqual(d["sumario"], [])
        self.assertTrue(d["sumario_replaced"])

    def test_date_from_document_number_when_the_date_field_is_missing(self):
        raw = page_html(extra_fields=(("Nº do Documento", "SJ200710250033442"),)).replace("Data do Acórdão".encode("latin-1"), b"Outra")
        self.assertEqual(convert.parse_decision(raw, self.stj)["data"], "2007-10-25")

    def test_no_processo_is_unusable(self):
        with self.assertRaises(convert.Unusable):
            convert.parse_decision(b"<html><body>nada</body></html>", self.stj)

    def test_ecli_only_where_the_pattern_was_confirmed(self):
        t = tribunais()
        self.assertEqual(convert.ecli_for(t["trp"], "1442/22.6SPPRT.P1", "2023-05-02"), "ECLI:PT:TRP:2023:1442.22.6SPPRT.P1")
        self.assertEqual(convert.ecli_for(t["trl"], "4/26.3YIPRT.L1-8", "2026-10-15"), "ECLI:PT:TRL:2026:4.26.3YIPRT.L1.8")
        self.assertEqual(convert.ecli_for(t["stj"], "047739", "1995-03-01"), "ECLI:PT:STJ:1995:047739")
        self.assertIsNone(convert.ecli_for(t["sta"], "0218/25.3BALSB-A", "2026-10-15"))
        self.assertIsNone(convert.ecli_for(t["trc"], "(…)", "2026-06-11"))  # placeholder processo: no ECLI


class Files(TmpCase):
    def raw_with(self, db, items):
        """items: [(unid, page bytes, list date or None)]"""
        raw = Raw(self.tmp / "raw")
        rows = {}
        for u, body, d in items:
            raw.write_page(db, u, body)
            rows[u] = {"path": f"/{db}.nsf/{VIEW}/{u}", "processo": "", "relator": "", "descritores": [], "data": d}
        raw.write_list({"db": db, "complete": True, "next": None, "expected": len(rows), "rows": rows})
        return raw

    def run_convert(self, retirada=""):
        cfg = self.config_dir(retirada)
        out = self.tmp / "out"
        res = convert.convert_all(self.tmp / "raw", out, cfg)
        return res, out

    def test_file_layout_front_matter_and_body(self):
        self.raw_with("jstj", [(unid(1), page_html(), None)])
        (written, excluded, retired), out = self.run_convert()
        p = out / "stj" / "2026" / "stj-1571-19-3t8oaz-e-p1-s1-2026-10-20.md"
        self.assertTrue(p.exists(), list(out.rglob("*")))
        meta, body = parse_frontmatter(p.read_text(encoding="utf-8"))
        self.assertEqual(meta["id"], "stj-1571-19-3t8oaz-e-p1-s1-2026-10-20")
        self.assertEqual(meta["tribunal"], "stj")
        self.assertEqual(meta["data"], "2026-10-20")
        self.assertEqual(meta["source"], f"https://www.dgsi.pt/jstj.nsf/{VIEW}/{unid(1)}?OpenDocument")
        self.assertEqual(meta["ecli"], "ECLI:PT:STJ:2026:1571.19.3T8OAZ.E.P1.S1")
        self.assertIs(meta["ecli_confirmed"], True)
        self.assertEqual(meta["text_version"], "sumário e metadados, sem texto integral")
        self.assertEqual(meta["descritores"], ["RECURSO DE REVISTA", "DOAÇÃO"])
        self.assertEqual(meta["texto_integral"], "S")
        self.assertRegex(meta["retrieved"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(body.startswith("\n# Supremo Tribunal de Justiça, processo 1571/19.3T8OAZ-E.P1.S1, 2026-10-20\n\n## Sumário\n\n"))
        self.assertIn("I - A doação de imóveis exige escritura pública.\n\nII - A falta", body)
        text = p.read_text(encoding="utf-8")
        self.assertNotIn("Manuel Exemplo", text)
        self.assertNotIn("Acordam", text)
        self.assertEqual(written, {"stj": 1, **{k: 0 for k in tribunais() if k != "stj"}})

    def test_unconfirmed_ecli_court(self):
        self.raw_with("jsta", [(unid(1), page_html(processo="0218/25.3BALSB-A"), None)])
        _, out = self.run_convert()
        meta, _ = parse_frontmatter(next(out.rglob("*.md")).read_text(encoding="utf-8"))
        self.assertIs(meta["ecli_confirmed"], False)
        self.assertNotIn("ecli", meta)

    def test_no_summary_gets_the_fixed_sentence_only(self):
        self.raw_with("jstj", [(unid(1), page_html(with_sumario=False), None)])
        _, out = self.run_convert()
        body = next(out.rglob("*.md")).read_text(encoding="utf-8").split("\n---\n", 1)[1]
        self.assertTrue(body.endswith(f"## Sumário\n\n{NO_SUMMARY}\n"))
        self.assertEqual(NO_SUMMARY, "Sem sumário publicado. Texto integral na fonte.")

    def test_same_process_same_day_gets_a_hash_only_on_collision(self):
        a, b = unid(0xA1), unid(0xB2)
        self.raw_with("jstj", [(b, page_html(sumario=("segunda",)), None), (a, page_html(sumario=("primeira",)), None),
                               (unid(3), page_html(processo="999/20.1T8LSB"), None)])
        (written, *_), out = self.run_convert()
        names = sorted(p.name for p in out.rglob("*.md"))
        self.assertEqual(len(names), 3)
        self.assertIn("stj-1571-19-3t8oaz-e-p1-s1-2026-10-20.md", names)
        self.assertIn(f"stj-1571-19-3t8oaz-e-p1-s1-2026-10-20-{b[:8]}.md", names)
        self.assertIn("stj-999-20-1t8lsb-2026-10-20.md", names)  # no hash without collision
        plain = (out / "stj" / "2026" / "stj-1571-19-3t8oaz-e-p1-s1-2026-10-20.md").read_text(encoding="utf-8")
        self.assertIn("primeira", plain)  # smallest unid keeps the plain id

    def test_date_falls_back_to_the_list(self):
        raw = page_html().replace("Data do Acórdão".encode("latin-1"), b"Outra")
        self.raw_with("jstj", [(unid(1), raw, "2019-03-04")])
        _, out = self.run_convert()
        self.assertTrue(any(out.rglob("stj-1571-19-3t8oaz-e-p1-s1-2019-03-04.md")))

    def test_page_without_date_anywhere_is_excluded_and_reported(self):
        raw = page_html().replace("Data do Acórdão".encode("latin-1"), b"Outra")
        self.raw_with("jstj", [(unid(1), raw, None)])
        (written, excluded, _), out = self.run_convert()
        self.assertEqual(excluded[0]["reason"], "sem data")
        self.assertFalse(excluded[0]["kept"])
        self.assertEqual(list(out.rglob("*.md")), [])

    def test_retirada_ids_are_never_written(self):
        self.raw_with("jstj", [(unid(1), page_html(), None), (unid(2), page_html(processo="999/20.1T8LSB"), None)])
        (written, _, retired), out = self.run_convert(retirada="# nota\nstj-1571-19-3t8oaz-e-p1-s1-2026-10-20\n")
        self.assertEqual(retired, 1)
        self.assertEqual([p.name for p in out.rglob("*.md")], ["stj-999-20-1t8lsb-2026-10-20.md"])

    def test_retirada_covers_a_hashed_collision_id_too(self):
        b = unid(0xB2)
        self.raw_with("jstj", [(unid(0xA1), page_html(), None), (b, page_html(), None)])
        (_, _, retired), out = self.run_convert(retirada=f"stj-1571-19-3t8oaz-e-p1-s1-2026-10-20-{b[:8]}\n")
        self.assertEqual(retired, 1)
        self.assertEqual(len(list(out.rglob("*.md"))), 1)

    def test_replaced_long_summary_is_kept_with_the_fixed_sentence_and_reported(self):
        self.raw_with("jstj", [(unid(1), page_html(sumario=("palavra " * 4000,)), None)])
        (_, excluded, _), out = self.run_convert()
        self.assertTrue(excluded[0]["kept"])
        self.assertIn(NO_SUMMARY, next(out.rglob("*.md")).read_text(encoding="utf-8"))

    def test_retrieved_date_comes_from_the_gzip_header(self):
        raw = Raw(self.tmp / "raw")
        (self.tmp / "raw" / "pages" / "jstj").mkdir(parents=True)
        (raw.page_path("jstj", unid(1))).write_bytes(gz_bytes(page_html(), mtime=1700000000))  # 2023-11-14
        raw.write_list({"db": "jstj", "complete": True, "next": None, "expected": 1,
                        "rows": {unid(1): {"path": f"/jstj.nsf/{VIEW}/{unid(1)}", "data": None}}})
        _, out = self.run_convert()
        meta, _ = parse_frontmatter(next(out.rglob("*.md")).read_text(encoding="utf-8"))
        self.assertEqual(str(meta["retrieved"]), "2023-11-14")


if __name__ == "__main__":
    unittest.main()
