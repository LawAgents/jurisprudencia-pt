import unittest
from pathlib import Path

from helpers import TmpCase, tribunais, VIEW, unid
import validate
from common import LEGAL_NOTICE, NO_SUMMARY, TEXT_VERSION, format_frontmatter

SRC = f"https://www.dgsi.pt/jstj.nsf/{VIEW}/{unid(1)}?OpenDocument"


def meta(**kw):
    m = {"id": "stj-1-20-1t8lsb-2020-03-04", "title": "Supremo Tribunal de Justiça, processo 1/20.1T8LSB, 2020-03-04",
         "tribunal": "stj", "processo": "1/20.1T8LSB", "relator": "JUIZ INVENTADO", "data": "2020-03-04", "descritores": ["A", "B"],
         "source": SRC, "ecli": "ECLI:PT:STJ:2020:1.20.1T8LSB", "ecli_confirmed": True, "retrieved": "2026-10-22",
         "text_version": TEXT_VERSION, "legal_notice": LEGAL_NOTICE}
    m.update(kw)
    return {k: v for k, v in m.items() if v is not None}


class Validate(TmpCase):
    def write(self, m=None, body=None, rel=None, **kw):
        m = m or meta(**kw)
        if body is None:
            body = f"# {m.get('title', 'x')}\n\n## Sumário\n\nI - Sumário inventado.\n"
        p = Path(self.tmp / "root") / (rel or f"{m['tribunal']}/{str(m.get('data', '2020'))[:4]}/{m['id']}.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(format_frontmatter(m) + "\n\n" + body, encoding="utf-8", newline="\n")
        return p

    def run_v(self, retirada=(), expected=None):
        return validate.validate(self.tmp / "root", tribunais(), set(retirada), expected)[0]

    def codes(self, **kw):
        return {e["code"] for e in self.run_v(**kw)}

    def test_valid_file_passes(self):
        self.write()
        self.assertEqual(self.run_v(), [])

    def test_no_summary_sentence_is_valid(self):
        m = meta()
        self.write(m, body=f"# {m['title']}\n\n## Sumário\n\n{NO_SUMMARY}\n")
        self.assertEqual(self.run_v(), [])

    def test_missing_required_fields_are_rejected(self):
        for field in ("title", "processo", "data", "source", "retrieved", "text_version", "legal_notice"):
            with self.subTest(field=field):
                p = self.write(**{field: None})
                self.assertIn("missing_field", self.codes())
                p.unlink()

    def test_full_text_body_is_rejected(self):
        m = meta()
        self.write(m, body=f"# {m['title']}\n\n## Sumário\n\nI - x\n\n## Decisão Texto Integral\n\nAcordam em conferência.\n")
        self.assertIn("full_text", self.codes())

    def test_full_text_heading_variant_is_rejected(self):
        m = meta()
        self.write(m, body=f"# {m['title']}\n\n## Sumário\n\nI - x\n\n## Texto integral\n\nAcordam.\n")
        self.assertIn("full_text", self.codes())

    def test_summary_missing_or_empty(self):
        m = meta()
        self.write(m, body=f"# {m['title']}\n\nSem secção.\n")
        self.assertIn("no_summary_section", self.codes())
        self.write(m, body=f"# {m['title']}\n\n## Sumário\n\n\n")
        self.assertIn("empty_summary", self.codes())

    def test_mixed_summary_and_fixed_sentence(self):
        m = meta()
        self.write(m, body=f"# {m['title']}\n\n## Sumário\n\nI - x\n\n{NO_SUMMARY}\n")
        self.assertIn("summary_mixed", self.codes())

    def test_duplicate_ids(self):
        self.write()
        self.write(rel="stj/2020/outro.md")
        self.assertIn("duplicate_id", self.codes())

    def test_id_must_match_file_name_and_tribunal(self):
        self.write(rel="stj/2020/errado.md")
        self.assertIn("id_filename", self.codes())

    def test_dates_must_be_real_iso_dates(self):
        self.write(data="2020-02-30", id="stj-1-20-1t8lsb-2020-02-30", title="x")
        self.assertIn("bad_date", self.codes())

    def test_unknown_tribunal(self):
        self.write(tribunal="xxx", id="xxx-1", rel="stj/2020/xxx-1.md")
        self.assertIn("unknown_tribunal", self.codes())

    def test_unknown_folder_is_rejected(self):
        self.write(rel="outro/2020/x.md")
        self.assertIn("unknown_folder", self.codes())

    def test_source_must_be_a_dgsi_link_of_the_same_database(self):
        self.write(source="https://example.com/x")
        self.assertIn("bad_source", self.codes())
        self.write(source=f"https://www.dgsi.pt/jsta.nsf/{VIEW}/{unid(1)}?OpenDocument")
        self.assertIn("bad_source", self.codes())

    def test_ecli_rules(self):
        self.write(ecli=None)
        self.assertIn("ecli", self.codes())
        self.write(ecli_confirmed=False)
        self.assertIn("ecli_confirmed", self.codes())

    def test_file_must_be_under_60_kb(self):
        m = meta()
        self.write(m, body=f"# {m['title']}\n\n## Sumário\n\n" + ("palavra " * 9000) + "\n")
        self.assertIn("file_too_big", self.codes())

    def test_retired_ids_are_rejected(self):
        self.write()
        self.assertIn("retired", self.codes(retirada=["stj-1-20-1t8lsb-2020-03-04"]))

    def test_expected_count(self):
        self.write()
        self.assertIn("count", self.codes(expected=2))
        self.assertEqual(self.run_v(expected=1), [])

    def test_wrong_folder(self):
        self.write(rel="stj/1999/stj-1-20-1t8lsb-2020-03-04.md")
        self.assertIn("path", self.codes())


if __name__ == "__main__":
    unittest.main()
