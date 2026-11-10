"""Run from the project folder:   python -m unittest discover -s tests -v
(also works with pytest)."""
import io
import itertools
import json
import math
import os
import random
import sys
import unittest

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import core  # noqa: E402

DATA = os.path.join(ROOT, "data")


def demo():
    return core.load_demo_projects(os.path.join(DATA, "demo_projects.csv"))


class FinanceTests(unittest.TestCase):
    def test_annuity_matches_loop(self):
        for cf, r, n in [(100, 0.10, 5), (250.5, 0.07, 12), (10, 0.0, 4)]:
            loop = sum(cf / (1 + r) ** t for t in range(1, n + 1))
            self.assertAlmostEqual(core.annuity_pv(cf, r, n), loop, places=6)

    def test_irr_simple(self):
        self.assertAlmostEqual(core.irr([-100, 110]), 0.10, places=6)
        self.assertIsNone(core.irr([100, 100, 100]))  # no sign change

    def test_discounted_payback(self):
        self.assertIsNone(core.discounted_payback(1000, 10, 0.1, 5))
        v = core.discounted_payback(100, 60, 0.0, 5)
        self.assertAlmostEqual(v, 100 / 60, places=6)

    def test_consistency_demo_statuses(self):
        chk = core.add_consistency_columns(demo()).set_index("Project")["check"]
        self.assertEqual(chk["Automation Line A"], "Consistent")
        self.assertEqual(chk["Quality Inspection System"], "Inconsistent")  # planted
        self.assertEqual(chk["Warehouse Conveyor"], "Review")                # planted
        self.assertEqual(chk["Lighting Retrofit"], "Consistent")             # negative NPV, honestly stated

    def test_consistency_sign_flip_and_missing(self):
        r = core.consistency_check(80000, 35000, 5.0, 8, 5)  # the old sample data
        self.assertEqual(r["status"], "Inconsistent")
        self.assertLess(r["implied_npv"], 0)
        self.assertEqual(core.consistency_check(80000, None, 5.0, 8, 5)["status"], "Not checkable")
        self.assertEqual(core.consistency_check(0, 1, 1, 8, 5)["status"], "Not checkable")

    def test_consistency_payback_longer_than_life(self):
        r = core.consistency_check(100000, -80000, 6.0, 8, 5)
        self.assertIn("never pays back", r["note"])

    def test_scenarios(self):
        sc = core.scenario_table(500000, 3.5, 10, 5)
        base = sc.iloc[0]["NPV"]
        implied = core.consistency_check(500000, 0, 3.5, 10, 5)["implied_npv"]
        self.assertAlmostEqual(base, implied, places=4)
        by = sc.set_index("Scenario")["NPV"]
        self.assertLess(by["Cost overrun +20%"], base)
        self.assertLess(by["Discount rate +5 pp"], by["Discount rate +2 pp"])
        self.assertLess(sc.iloc[-1]["NPV"], by["Cost overrun +20%"])

    def test_breakeven_savings_cut_zeroes_npv(self):
        cost, pb, r, life = 750000, 3.2, 10, 8
        k = core.breakeven_savings_cut(cost, pb, r, life) / 100
        cf = cost / pb * (1 - k)
        self.assertAlmostEqual(core.annuity_pv(cf, r / 100, life) - cost, 0.0, places=4)

    def test_tornado_sorted(self):
        t = core.tornado_table(500000, 3.5, 10, 5)
        self.assertTrue(t["Swing"].is_monotonic_decreasing)
        self.assertEqual(set(t["Variable"]), {"Discount rate", "Annual savings", "Capital cost", "Useful life"})


class ScoringTests(unittest.TestCase):
    def test_single_project_not_auto_perfect(self):
        one = demo().iloc[[0]]
        scored, _ = core.score_aim(one, core.DEFAULT_AIM_WEIGHTS["New growth"])
        self.assertAlmostEqual(scored.loc[0, "Score"], 0.5, places=6)

    def test_ranking_direction(self):
        df = demo()
        bucket = df[df["Aim"] == "New growth"]
        scored, eff = core.score_aim(bucket, core.DEFAULT_AIM_WEIGHTS["New growth"])
        self.assertAlmostEqual(sum(eff.values()), 1.0)
        self.assertTrue(scored["Score"].is_monotonic_decreasing)
        # lower payback / cost / risk should be rewarded
        n = core.normalize_column(pd.Series([1.0, 2.0, 3.0]), "lower")
        self.assertEqual(list(n), [1.0, 0.5, 0.0])

    def test_incomplete_rows_are_excluded_not_zeroed(self):
        df = demo()
        df.loc[0, "payback"] = float("nan")
        ok, bad = core.split_complete(df)
        self.assertEqual(len(bad), 1)
        self.assertEqual(len(ok), len(df) - 1)

    def test_empty_portfolio_has_float_numeric_columns(self):
        e = core.normalize_projects(pd.DataFrame(columns=core.PROJECT_COLUMNS))
        for c in core.NUMERIC_COLS:
            self.assertEqual(str(e[c].dtype), "float64", c)

    def test_normalize_projects_keeps_nan(self):
        raw = pd.DataFrame({"Project": ["x"], "Aim": ["New growth"], "cost": [None]})
        out = core.normalize_projects(raw)
        self.assertTrue(pd.isna(out.loc[0, "cost"]))
        self.assertFalse(out.loc[0, "scores_reviewed"])

    def test_breakdown_sums_to_score(self):
        df = demo()
        bucket = df[df["Aim"] == "Improve performance"]
        scored, eff = core.score_aim(bucket, core.DEFAULT_AIM_WEIGHTS["Improve performance"])
        name = scored.loc[1, "Project"]
        bd = core.score_breakdown(scored, name, eff)
        self.assertAlmostEqual(bd["Contribution"].sum(), scored.loc[1, "Score"], places=9)


class BudgetTests(unittest.TestCase):
    def test_knapsack_is_optimal_vs_bruteforce(self):
        rnd = random.Random(7)
        for _ in range(60):
            n = rnd.randint(1, 9)
            costs = [rnd.randint(1, 20) for _ in range(n)]
            vals = [rnd.random() for _ in range(n)]
            budget = rnd.randint(1, 60)
            idx, best = core.knapsack_select(costs, vals, budget, unit=1.0)
            brute = max(sum(vals[i] for i in c)
                        for k in range(n + 1) for c in itertools.combinations(range(n), k)
                        if sum(costs[i] for i in c) <= budget)
            self.assertAlmostEqual(best, brute, places=9)
            self.assertLessEqual(sum(costs[i] for i in idx), budget)
            g_idx, g_val = core.greedy_select(costs, vals, budget)
            self.assertGreaterEqual(best + 1e-9, g_val)

    def test_knapsack_where_greedy_loses(self):
        costs, vals = [60, 50, 50], [10, 9, 9]   # greedy-by-order takes the first, optimal takes two
        g, gv = core.greedy_select(costs, vals, 100)
        o, ov = core.knapsack_select(costs, vals, 100, unit=1.0)
        self.assertEqual(g, [0])
        self.assertEqual(o, [1, 2])
        self.assertGreater(ov, gv)

    def test_allocate_budget_mandatory_first_and_within_budget(self):
        df = demo()
        scored = {}
        for aim in core.AIMS:
            b = df[df["Aim"] == aim]
            scored[aim], _ = core.score_aim(b, core.DEFAULT_AIM_WEIGHTS[aim])
        total = 1_500_000
        out, meta = core.allocate_budget(scored, total, {a: 25 for a in core.AIMS})
        reg = out[core.MANDATORY_AIM]
        self.assertEqual(reg["mode"], "mandatory")
        self.assertEqual(set(reg["funded"]), set(scored[core.MANDATORY_AIM]["Project"]))
        spent = sum(v["spent"] for v in out.values())
        self.assertLessEqual(spent, total + 1e-6)
        for a, v in out.items():
            if v["mode"] != "mandatory":
                self.assertLessEqual(v["spent"], v["budget"] + 1e-6)
                self.assertGreaterEqual(v["optimal_score"] + 1e-9, v["greedy_score"])

    def test_mandatory_shortfall_reported(self):
        df = demo()
        scored = {core.MANDATORY_AIM: core.score_aim(df[df["Aim"] == core.MANDATORY_AIM],
                                                     core.DEFAULT_AIM_WEIGHTS[core.MANDATORY_AIM])[0]}
        out, meta = core.allocate_budget(scored, 100000, {})
        self.assertGreater(meta["mandatory_shortfall"], 0)


class SiteDealTests(unittest.TestCase):
    def test_hand_calculation(self):
        df, m = core.site_deal(capex=100, years=2, anchor_rent_month=1, tenant2_year=0, tenant3_year=0,
                               coloc_factor=1, tenant_esc_pct=0, ground_rent_month=0, ground_esc_pct=0,
                               opex_year1=2, opex_esc_pct=0, discount_rate_pct=10)
        self.assertEqual(list(df["NOI"]), [10.0, 10.0])
        self.assertAlmostEqual(m["npv"], -100 + 10 / 1.1 + 10 / 1.21, places=9)
        self.assertEqual(m["peak_tenants"], 1)

    def test_second_tenant_adds_revenue(self):
        base, _ = core.site_deal(300000, 10, 2000, 0, 0, 0.8, 3, 600, 2, 12000, 3, 8)
        more, mm = core.site_deal(300000, 10, 2000, 3, 0, 0.8, 3, 600, 2, 12000, 3, 8)
        self.assertEqual(base.loc[1, "Revenue"], more.loc[1, "Revenue"])          # before tenant 2
        self.assertAlmostEqual(more.loc[2, "Revenue"], base.loc[2, "Revenue"] * 1.8, places=6)
        self.assertEqual(mm["peak_tenants"], 2)

    def test_breakevens(self):
        exact, whole = core.breakeven_added_tenants(12000, 100, 0, 0, 5)
        self.assertAlmostEqual(exact, 2.0)
        self.assertEqual(whole, 2)
        self.assertEqual(core.breakeven_added_tenants(12001, 100, 0, 0, 5)[1], 3)
        self.assertAlmostEqual(core.breakeven_rent(12000, 2, 0, 0, 5), 100.0)
        self.assertEqual(core.breakeven_added_tenants(1000, 10, 0, 0, 5, opex_per_tenant_year=1000)[1], None)


class VerificationTests(unittest.TestCase):
    DOC = ("Total capital cost: $750,000. NPV is ($48,000) at 9.5% over 8 years. Payback in roughly 42 months. "
           "Budget $0.38 million; later 2 years and 8 months. Lines | Capital cost | 96,500")

    def check(self, value, evidence):
        return core.verify_field(value, evidence, self.DOC)

    def test_statuses(self):
        self.assertEqual(self.check(750000, "Total capital cost: $750,000"), "verified")
        self.assertEqual(self.check(-48000, "NPV is ($48,000) at 9.5%"), "verified")
        self.assertEqual(self.check(48000, "NPV is ($48,000) at 9.5%"), "sign_mismatch")
        self.assertEqual(self.check(3.5, "Payback in roughly 42 months"), "verified")
        self.assertEqual(self.check(380000, "Budget $0.38 million"), "verified")
        self.assertEqual(self.check(2 + 8 / 12, "2 years and 8 months"), "verified")
        self.assertEqual(self.check(96500, "Capital cost 96,500"), "verified")          # pipes/spacing tolerated
        self.assertEqual(self.check(9.5, "9.5% over 8 years"), "verified")
        self.assertEqual(self.check(750001000, "Total capital cost: $750,000"), "number_mismatch")
        self.assertEqual(self.check(750000, "The capex is $750,000 exactly"), "quote_not_found")  # invented quote
        self.assertEqual(self.check(750000, None), "no_evidence")
        self.assertEqual(self.check(None, None), "absent")

    def test_unverifiable_words(self):
        doc = "Finance expects the investment to pay for itself in three and a half years."
        self.assertEqual(core.verify_field(3.5, "pay for itself in three and a half years", doc), "unverifiable")

    def test_parse_json_variants(self):
        self.assertEqual(core.parse_llm_json('```json\n{"a": 1}\n```')["a"], 1)
        self.assertEqual(core.parse_llm_json('Sure! {"a": 2} hope that helps')["a"], 2)
        with self.assertRaises(ValueError):
            core.parse_llm_json("no json here")


class ExtractionFlowTests(unittest.TestCase):
    DOC = "Capital cost: $750,000. Payback: 3.2 years. Discount rate 10%. Useful life 8 years."

    def fake_llm(self, prompt):
        return json.dumps({
            "project_name": "Line 4", "suggested_aim": "New growth",
            "cost": {"value": 750000, "evidence": "Capital cost: $750,000"},
            "npv": {"value": 500000, "evidence": "NPV of $500,000"},           # invented quote
            "roi": {"value": None, "evidence": None},
            "payback": {"value": 3.2, "evidence": "Payback: 3.2 years"},
            "discount_rate_pct": {"value": 10, "evidence": "Discount rate 10%"},
            "useful_life_yrs": {"value": 8, "evidence": "Useful life 8 years"},
        })

    def test_extract_and_statuses(self):
        res = core.extract_project(self.DOC, self.fake_llm)
        self.assertTrue(res["ok"])
        self.assertEqual(res["fields"]["cost"]["status"], "verified")
        self.assertEqual(res["fields"]["npv"]["status"], "quote_not_found")
        self.assertEqual(res["fields"]["roi"]["status"], "absent")
        self.assertFalse(res["truncated"])

    def test_truncation_flag_and_errors_do_not_raise(self):
        res = core.extract_project("x" * 50, self.fake_llm, max_chars=10)
        self.assertTrue(res["truncated"])
        self.assertEqual(res["chars_read"], 10)

        def boom(_):
            raise RuntimeError("The model `llama3-8b-8192` has been decommissioned")
        bad = core.extract_project(self.DOC, boom)
        self.assertFalse(bad["ok"])
        self.assertIn("retired", bad["error"])

    def test_prompt_has_no_subjective_scores(self):
        p = core.build_prompt("doc")
        self.assertNotIn("strategic", p.lower())
        self.assertIn("VERBATIM", p)


class BenchmarkTests(unittest.TestCase):
    def truth(self):
        return pd.read_csv(os.path.join(DATA, "business_cases", "ground_truth.csv"))

    def cases(self):
        folder = os.path.join(DATA, "business_cases")
        out = {}
        for f in sorted(os.listdir(folder)):
            if f.endswith(".txt"):
                with open(os.path.join(folder, f), encoding="utf-8") as fh:
                    out[f[:-4]] = fh.read()
        return out

    def test_ground_truth_is_supported_by_documents(self):
        """Every labelled number must be readable from its document (except spelled-out words)."""
        exceptions = {("case_03", "payback")}
        for _, t in self.truth().iterrows():
            text = self.cases()[t["case_id"]]
            cands = core.candidate_values(text)
            for f in core.BENCH_FIELDS:
                v = core.parse_number(t[f])
                if v is None or (t["case_id"], f) in exceptions:
                    continue
                self.assertTrue(any(core._close(v, c) for c in cands), f"{t['case_id']} {f}={v} not found in document")

    def test_absent_fields_really_absent(self):
        cases = self.cases()
        self.assertNotIn("%", cases["case_10"])
        self.assertNotIn("payback", cases["case_10"].replace("No financial", ""))

    def _perfect(self):
        truth = self.truth()
        res = {}
        for _, t in truth.iterrows():
            fields = {}
            for f in core.BENCH_FIELDS:
                v = core.parse_number(t[f])
                fields[f] = {"value": v, "evidence": "x" if v is not None else None,
                             "status": "verified" if v is not None else "absent"}
            res[t["case_id"]] = {"ok": True, "suggested_aim": t["aim"], "fields": fields}
        return truth, res

    def test_perfect_extractor_scores_100(self):
        truth, res = self._perfect()
        detail, s = core.evaluate_extraction(res, truth)
        self.assertEqual(s["accuracy"], 1.0)
        self.assertEqual(s["verified_wrong"], 0)
        self.assertEqual(s["aim_accuracy"], 1.0)
        self.assertEqual(s["fields_scored"], 60)

    def test_errors_are_classified(self):
        truth, res = self._perfect()
        res["case_01"]["fields"]["cost"]["value"] = 999999          # wrong but "verified"
        res["case_02"]["fields"]["npv"]["value"] = 1234             # hallucinated
        res["case_05"]["fields"]["roi"]["value"] = None             # missed
        res["case_05"]["fields"]["roi"]["status"] = "absent"
        detail, s = core.evaluate_extraction(res, truth)
        self.assertEqual((s["wrong"], s["hallucinated"], s["missed"]), (1, 1, 1))
        self.assertEqual(s["verified_wrong"], 1)   # the wrong-but-verified one
        res["case_03"] = {"ok": False, "error": "x"}
        _, s2 = core.evaluate_extraction(res, truth)
        self.assertEqual(s2["cases_failed"], 1)


class DocumentReadingTests(unittest.TestCase):
    def test_txt_csv_xlsx_docx(self):
        text, w = core.read_document("a.txt", b"hello 123")
        self.assertIn("hello", text)
        text, _ = core.read_document("a.csv", b"cost,750000\npayback,3.2\n")
        self.assertIn("750000", text)
        buf = io.BytesIO()
        pd.DataFrame([["cost", 750000], ["payback", 3.2]]).to_excel(buf, index=False, header=False)
        text, _ = core.read_document("a.xlsx", buf.getvalue())
        self.assertIn("750000", text)
        from docx import Document
        d = Document()
        d.add_paragraph("Capital cost: $750,000")
        t = d.add_table(rows=1, cols=2)
        t.rows[0].cells[0].text, t.rows[0].cells[1].text = "Payback", "3.2 years"
        b = io.BytesIO()
        d.save(b)
        text, _ = core.read_document("a.docx", b.getvalue())
        self.assertIn("750,000", text)
        self.assertIn("Payback | 3.2 years", text)

    def test_empty_and_bad_files_warn(self):
        text, w = core.read_document("a.txt", b"   ")
        self.assertTrue(w)
        text, w = core.read_document("broken.pdf", b"not a pdf")
        self.assertTrue(w)


if __name__ == "__main__":
    unittest.main()
