import ast
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import html as html_lib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("retail_quality", ROOT / "retail_quality.py")
q = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = q
spec.loader.exec_module(q)


def source(key="n0001", stamp="2025-08-30T12:00:00Z", url="https://news.test/old"):
    return {"id": key, "published_at": stamp, "url": url, "title": "Specific company development"}


def entry(asset="GLD", key="n0001", price="100", words=100):
    text = ("Investors choose insurance because monetary uncertainty raises the appeal of an independent asset. " * (words // 14 + 1))
    return {"title": f"Gold / {asset} — a narrative", "parts": [["Why Retail Is Here", text + f"The close was ${price}. [[{key}]]"]]}


def report(date, item, sources):
    return {"date": date, "retail": [item], "feed": {"date": date, "items": sources}}


class QualityTests(unittest.TestCase):
    def test_aliases_and_family_avoid_cosmetic_rotation(self):
        self.assertEqual(q.asset_id("Gold — an insurance story"), "GLD")
        self.assertEqual(q.asset_id("Silver / SLV — catch up"), "SLV")
        self.assertEqual(q.family_id("Gold / GLD — one"), q.family_id("Silver / SLV — two"))
        self.assertEqual(q.family_id("Rigetti / RGTI — one"), q.family_id("Quantum computing / IONQ — two"))
        self.assertEqual(q.asset_id("Nike (NKE) — turnaround"), "NKE")
        self.assertEqual(q.asset_id("Nvidia — momentum"), "NVDA")
        self.assertEqual(q.family_id("QuantumScape / QS — a battery partnership"), "battery-technology")
        self.assertNotEqual(q.family_id("QuantumScape — battery technology"), "quantum")
        self.assertEqual(q.asset_id("Bitcoin miners as AI landlords / IREN, CIFR — a customer contract"), "IREN")
        self.assertEqual(q.family_id("Bitcoin miners as AI landlords / IREN, CIFR — a customer contract"), "ai-capacity")
        self.assertNotEqual(q.asset_id('"Bad News Is Good News" Rate-Cut Plays — weak jobs'), "unknown")

    def test_price_changes_do_not_hide_recycled_angle_or_source(self):
        a = report("2025-09-01", entry(price="100"), [source()])
        # IDs are local to each feed, while the underlying story is unchanged.
        b = report("2025-09-02", entry(key="n0044", price="900"), [source(key="n0044")])
        output = q.audit_reports([a, b])
        codes = {x["code"] for x in output["flags"]}
        self.assertIn("no_new_catalyst", codes)
        self.assertIn("recycled_angle", codes)
        self.assertEqual(output["reports"][1]["entries"][0]["price_stripped_similarity"], 1.0)

    def test_fresh_catalyst_and_specific_review_can_support_persistence(self):
        a = report("2025-09-01", entry(), [source()])
        b = report("2025-09-02", entry(key="n0044"), [source("n0044", "2025-09-01T13:00:00Z", "https://news.test/new-result")])
        first = q.audit_reports([a, b])
        decisions = {flag["flag_id"]: {"disposition": "material_update", "changed_angle": "The newly reported result changes the earnings case and requires a different risk assessment.", "evidence_ids": ["n0044"], "reviewer": "test-editor"} for flag in first["flags"]}
        final = q.audit_reports([a, b], decisions)
        self.assertTrue(final["review_gate_passed"])
        self.assertNotIn("no_new_catalyst", {x["code"] for x in final["flags"]})

    def test_old_evidence_cannot_be_asserted_as_material_update(self):
        a = report("2025-09-01", entry(), [source()])
        b = report("2025-09-02", entry(), [source()])
        first = q.audit_reports([a, b])
        decisions = {flag["flag_id"]: {"disposition": "material_update", "changed_angle": "This is claimed as a fresh catalyst but merely cites an older unchanged story.", "evidence_ids": ["n0001"], "reviewer": "test-editor"} for flag in first["flags"]}
        final = q.audit_reports([a, b], decisions)
        self.assertFalse(final["review_gate_passed"])
        self.assertTrue(any("new source" in str(x.get("decision_errors")) for x in final["flags"]))

    def test_missing_or_invalid_or_at_cutoff_sources_fail(self):
        for sources, expected in [([], "missing_citation"), ([source(stamp="not-a-date")], "invalid_timestamp"), ([source(stamp="2025-09-01T00:00:00Z")], "after_cutoff"), ([source(stamp="2025-08-30T12:00:00")], "invalid_timestamp")]:
            with self.subTest(expected=expected):
                output = q.audit_reports([report("2025-09-01", entry(), sources)])
                self.assertFalse(output["evidence_checks_passed"])
                self.assertIn(expected, {x["code"] for x in output["hard_failures"]})

    def test_decision_cannot_use_uncited_evidence(self):
        current = {"sources": [{"id": "n0001"}], "fresh_evidence_ids": ["n0001"], "position": 0, "text": "small"}
        decision = {"disposition": "material_update", "changed_angle": "A sufficiently specific explanation of an alleged new company catalyst.", "reviewer": "editor", "evidence_ids": ["n9999"]}
        errors = q.validate_decision({"code": "recycled_angle"}, decision, current)
        self.assertTrue(any("cited" in x for x in errors))

    def test_rankings_need_explicit_measurement_scope(self):
        item = entry()
        item["parts"][0][1] += " This is the number-one retail trade."
        output = q.audit_reports([report("2025-09-01", item, [source()])])
        flag = next(x for x in output["flags"] if x["code"] == "ranking_claim")
        decision = {"disposition": "reviewed_selection", "changed_angle": "The editor thinks this is popular, but the source does not define a measurement population.", "reviewer": "editor", "evidence_ids": ["n0001"]}
        errors = q.validate_decision(flag, decision, {"sources": [{"id": "n0001"}], "fresh_evidence_ids": ["n0001"], "position": 0, "text": q.prose(item)})
        self.assertTrue(any("measurement scope" in x for x in errors))
        self.assertIsNotNone(q.RANKING.search("The #1 retail trade"))

    def test_future_reports_do_not_change_earlier_selection_flags(self):
        a = report("2025-09-01", entry(), [source()])
        b = report("2025-09-02", entry(), [source()])
        alone, later = q.audit_reports([a]), q.audit_reports([a, b])
        self.assertEqual(alone["reports"][0], later["reports"][0])
        self.assertEqual(alone["flags"], [x for x in later["flags"] if x["date"] == "2025-09-01"])

    def test_legacy_cutoff_preserved_and_missing_source_proof_not_passed(self):
        legacy = {"date": "2026-08-28", "cutoff_utc": "2026-08-28T19:00:00Z", "retail": [entry()], "feed": {"items": [source(stamp="2026-08-28T18:00:00Z")]}}
        self.assertTrue(q.audit_reports([legacy])["evidence_checks_passed"])
        legacy["feed"] = None
        output = q.audit_reports([legacy])
        self.assertIsNone(output["evidence_checks_passed"])
        self.assertFalse(output["review_gate_passed"])
        self.assertEqual(output["reports"][0]["cutoff_utc"], "2026-08-28T19:00:00Z")

    def test_html_parser_uses_span_boundary_and_stops_at_next_section(self):
        html = '<h2>Other</h2><h3>Ignored</h3><h2>🔥 What Retail Is Playing</h2><h3>Gold <span>the most obvious hedge</span></h3><p><strong>Why:</strong> A dated story <a href="https://news.test/story">source</a>.</p><h4>Nike (NKE)<span>The turnaround</span></h4><p>Second narrative.</p><h2>Sources</h2><h3>Ignored too</h3>'
        rows = q.parse_retail_html(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(q.asset_id(rows[0]["title"]), "GLD")
        self.assertEqual(q.asset_id(rows[1]["title"]), "NKE")
        self.assertEqual(rows[0]["citation_urls"], ["https://news.test/story"])


class RetrospectiveHistoryTests(unittest.TestCase):
    """Compile only the helper AST, never import the live module or credentials."""
    def helper(self):
        tree = ast.parse((ROOT / "retrospective_context.py").read_text())
        node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "_load_recent_retail_history")
        ns = {"datetime": dt.datetime, "timedelta": dt.timedelta, "re": re, "html_lib": html_lib, "REPORTS_PREFIX": "reports", "S3_BUCKET": "test"}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "isolated_history_helper", "exec"), ns)
        return ns[node.name]

    def test_history_reads_only_before_report_and_closes_body(self):
        class Fake:
            def __init__(self): self.keys, self.bodies = [], []
            def get_object(self, **kwargs):
                self.keys.append(kwargs["Key"])
                body = io.BytesIO(b'<h2>What Retail Is Playing</h2><h3>Gold</h3><p>Prior narrative.</p>')
                self.bodies.append(body)
                return {"Body": body}
        fake = Fake()
        rows = self.helper()("2025-09-03", fake, max_reports=2)
        self.assertEqual([x["report_date"] for x in rows], ["2025-09-01", "2025-09-02"])
        self.assertTrue(all("2025-09-03" not in x for x in fake.keys))
        self.assertTrue(all(body.closed for body in fake.bodies))

    def test_permission_failure_does_not_silently_remove_history(self):
        class Denied(Exception):
            response = {"Error": {"Code": "AccessDenied"}}
        class Fake:
            def get_object(self, **kwargs): raise Denied()
        with self.assertRaisesRegex(RuntimeError, "prior retail selection history"):
            self.helper()("2025-09-03", Fake())


if __name__ == "__main__":
    unittest.main()
