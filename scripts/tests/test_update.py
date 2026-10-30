import json
import shutil
import subprocess
import unittest
from pathlib import Path

from helpers import FakeClock, FakeServer, REPO, TmpCase, page_html, unid
import check_size
import fetch
import run_update
from common import gz_bytes


class Update(TmpCase):
    def setUp(self):
        super().setUp()
        self.clock = FakeClock()
        self.server = FakeServer(self.clock, per_page=3)
        self.repo, self.raw = self.tmp / "repo", self.tmp / "raw"
        (self.repo / "config").mkdir(parents=True)
        for f in ("tribunais.txt", "retirada.txt"):
            shutil.copy(REPO / "config" / f, self.repo / "config" / f)
        self.server.add("jstj", 7)
        self.server.add("jtrp", 4, start=100)

    def run_u(self, mode, budget=None, **kw):
        self.server.requests.clear()
        return run_update.run(mode, self.raw, self.repo, budget, client=self.server.client(), workers=1, clock=self.clock, **kw)

    def repo_files(self):
        return sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*.md") if "config" not in p.parts)

    def test_initial_builds_decisions_and_indices(self):
        self.assertEqual(self.run_u("initial"), 0)
        files = self.repo_files()
        self.assertEqual(len([f for f in files if f.startswith("stj/")]), 7)
        self.assertEqual(len([f for f in files if f.startswith("trp/")]), 4)
        for name in ("indice.md", "indice-stj.md", "indice-trp.md", "descritores.md"):
            self.assertIn(name, files)
        self.assertEqual(json.loads((self.raw / "excluded.json").read_text(encoding="utf-8")), [])

    def test_weekly_with_nothing_new_changes_nothing(self):
        self.run_u("initial")
        before = {f: (self.repo / f).read_bytes() for f in self.repo_files()}
        self.assertEqual(self.run_u("weekly"), 0)
        self.assertEqual(before, {f: (self.repo / f).read_bytes() for f in self.repo_files()})

    def test_weekly_adds_new_decisions_and_reports_changed(self):
        self.run_u("initial")
        self.server.dbs["jstj"].insert(0, {"unid": unid(50), "processo": "50/26.1T8LSB", "relator": "X", "data": "10/21/2026", "descritores": ["NOVO"]})
        self.assertEqual(self.run_u("weekly"), 0)
        self.assertIn("stj/2026/stj-50-26-1t8lsb-2026-10-21.md", self.repo_files())
        self.assertTrue(any("| novo |" in p.read_text(encoding="utf-8") for p in self.repo.glob("descritores-*.md")))

    def test_retirada_removes_the_decision_from_the_repo_and_indices(self):
        self.run_u("initial")
        victim = "stj-1-20-1t8lsb-2026-10-27"
        self.assertTrue((self.repo / "stj" / "2026" / f"{victim}.md").exists())
        (self.repo / "config" / "retirada.txt").write_text(f"{victim}\n", encoding="utf-8")
        self.assertEqual(self.run_u("weekly"), 0)
        self.assertFalse((self.repo / "stj" / "2026" / f"{victim}.md").exists())
        self.assertNotIn(victim, (self.repo / "indice-stj-2026.md").read_text(encoding="utf-8"))

    def test_failure_leaves_the_repo_untouched(self):
        self.run_u("initial")
        before = {f: (self.repo / f).read_bytes() for f in self.repo_files()}
        # a page the converter cannot read (no Processo field) in more than 0.5% of the pages
        fetch.Raw(self.raw).write_page("jstj", unid(1), b"<html><body>sem campos</body></html>")
        self.assertEqual(self.run_u("weekly"), 1)
        self.assertEqual(before, {f: (self.repo / f).read_bytes() for f in self.repo_files()})
        err = json.loads((self.raw / "errors.json").read_text(encoding="utf-8"))
        self.assertEqual(err["stage"], "convert")

    def test_validation_failure_blocks_publication(self):
        self.run_u("initial")
        # a full-text-looking sumário written by hand into the raw page must not get through validate
        raw = fetch.Raw(self.raw)
        raw.write_page("jstj", unid(2), page_html(processo="2/20.1T8LSB", data="10/26/2026",
                                                   sumario=("I - x", "Decisão Texto Integral"), full_text="x"))
        before = {f: (self.repo / f).read_bytes() for f in self.repo_files()}
        self.assertEqual(self.run_u("weekly"), 1)
        self.assertEqual(before, {f: (self.repo / f).read_bytes() for f in self.repo_files()})
        self.assertEqual(json.loads((self.raw / "errors.json").read_text(encoding="utf-8"))["stage"], "validate")

    def test_incomplete_raw_cache_never_empties_the_repo(self):
        self.run_u("initial")
        shutil.rmtree(self.raw / "pages")
        shutil.rmtree(self.raw / "lists")
        self.server.dbs = {"jstj": self.server.dbs["jstj"][:3], "jtrp": []}  # weekly would see only a few decisions
        n = len(self.repo_files())
        self.assertEqual(self.run_u("weekly"), 1)
        self.assertEqual(len(self.repo_files()), n)
        self.assertEqual(json.loads((self.raw / "errors.json").read_text(encoding="utf-8"))["errors"][0]["code"], "raw_cache_incomplete")

    def test_time_budget_exit_code_2_and_repo_untouched(self):
        self.assertEqual(self.run_u("initial", budget=1), 2)
        self.assertEqual(self.repo_files(), [])

    def test_fetch_errors_exit_code_1(self):
        self.server.errors["jstj.nsf?OpenDatabase"] = [500, 500, 500]
        self.assertEqual(self.run_u("initial"), 1)
        self.assertEqual(self.repo_files(), [])

    def test_size_gate(self):
        self.assertEqual(self.run_u("initial", size_limit=1000), 1)
        self.assertEqual(json.loads((self.raw / "errors.json").read_text(encoding="utf-8"))["stage"], "size")
        self.assertEqual(self.repo_files(), [])

    def test_check_size_counts_the_tree(self):
        d = self.tmp / "measured"
        d.mkdir()
        self.assertTrue(check_size.check(d, d, 10)[0])
        (d / "big.txt").write_text("x" * 100)
        self.assertFalse(check_size.check(d, d, 10)[0])


if __name__ == "__main__":
    unittest.main()
