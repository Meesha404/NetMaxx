"""Offline contract and failure-path tests. No paid API calls."""
import copy
import io
import json
import tempfile
import unittest
from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import event_router as er


ROW = {"Attendee Name": "Alex Demo", "Current Company": "Example Tools", "Job Title": "Founder", "attendee_id": "demo", "source_rows": [1]}


def pdl_response(company="Example Tools"):
    return {"status": 200, "likelihood": 9, "matched": ["name", "company"], "data": {
        "full_name": "Alex Demo", "linkedin_url": "linkedin.com/in/alex-demo",
        "job_company_name": company, "job_title": "Founder", "summary": "Building AI coding tools.",
        "experience": [{"company": {"name": "GE"}, "title": {"name": "Product Lead"}}]}}


class RouterTests(unittest.TestCase):
    def test_ingest_deduplicates_preserves_rows_and_rejects_invalid(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "in.json"
            path.write_text(json.dumps([ROW, ROW, {"Attendee Name": None}]))
            rows, rejected, total = er.ingest(path)
            self.assertEqual(total, 3)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source_rows"], [1, 2])
            self.assertEqual(rejected[0]["row"], 3)

    def test_csv_bom_and_header_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "in.csv"
            path.write_text('\ufeffAttendee Name,Current Company,Job Title\nAlex Demo,Example Tools,Founder\n')
            self.assertEqual(len(er.ingest(path)[0]), 1)
            path.write_text("name,company\nAlex,Example\n")
            with self.assertRaises(er.FatalError):
                er.ingest(path)

    def test_identity_rejects_former_employer(self):
        http = Mock()
        http.request.return_value = pdl_response("Other Company")
        identity, _ = er.resolve(http, ROW, "test", 8)
        self.assertEqual(identity["status"], "needs_review")
        self.assertFalse(identity["verified"])

    def test_identity_requires_both_input_matches(self):
        http = Mock()
        response = pdl_response()
        response["matched"] = ["name"]
        http.request.return_value = response
        self.assertEqual(er.resolve(http, ROW, "test", 8)[0]["status"], "needs_review")

    def test_identity_accepts_high_confidence_and_maps_about(self):
        http = Mock()
        http.request.return_value = pdl_response()
        identity, profile = er.resolve(http, ROW, "test", 8)
        self.assertEqual(identity["status"], "high_confidence_match")
        self.assertEqual(profile["about"], profile["summary"])

    def test_url_spoof_rejected(self):
        for url in ["https://linkedin.com.evil.test/in/alex", "https://linkedin.com@evil.test/in/alex", "https://www.linkedin.com/company/test", "http://linkedin.com/in/alex"]:
            self.assertIsNone(er.linkedin_url(url))
        self.assertEqual(er.linkedin_url("linkedin.com/in/alex?track=1"), "https://www.linkedin.com/in/alex")

    def test_posts_reject_wrong_author_and_stale(self):
        target = "https://www.linkedin.com/in/alex-demo"
        good = {"type": "post", "content": "Looking for AI dev tools", "linkedinUrl": "https://www.linkedin.com/posts/alex-123", "author": {"linkedinUrl": target}, "postedAt": {"date": "2026-10-01T00:00:00Z"}}
        wrong = copy.deepcopy(good)
        wrong["author"]["linkedinUrl"] = "https://www.linkedin.com/in/other"
        old = copy.deepcopy(good)
        old["postedAt"]["date"] = "2020-01-01T00:00:00Z"
        actual = er.normalize_posts([wrong, old, good, good], target, datetime(2026,10,2,tzinfo=timezone.utc))
        self.assertEqual(len(actual), 1)

    def test_bad_evidence_and_boolean_rating_rejected(self):
        result = er.demo_record(ROW, er.DEFAULT_ICP)
        assessment = {k: result[k] for k in er.SCHEMA["properties"]}
        assessment["hook_evidence_ids"] = ["invented"]
        with self.assertRaises(er.PipelineError):
            er.validate_score(assessment, result["evidence"])
        assessment["hook_evidence_ids"] = ["e1"]
        assessment["dimensions"]["role_fit"]["rating"] = True
        with self.assertRaises(er.PipelineError):
            er.validate_score(assessment, result["evidence"])

    def test_refusal_not_silently_scored(self):
        http = Mock()
        http.request.return_value = {"choices": [{"finish_reason": "stop", "message": {"refusal": "No"}}]}
        with self.assertRaisesRegex(er.PipelineError, "model_refusal"):
            er.score(http, [], er.DEFAULT_ICP, "gpt-4o", "test")

    def test_truncation_not_scored(self):
        http = Mock()
        http.request.return_value = {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
        with self.assertRaisesRegex(er.PipelineError, "model_incomplete"):
            er.score(http, [], er.DEFAULT_ICP, "gpt-4o", "test")

    @patch("event_router.time.sleep")
    def test_retry_429_then_success(self, sleep):
        client = er.HTTP(interval=0)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"ok": true}'
        error = HTTPError("https://example.test", 429, "rate limit", {"Retry-After": "2"}, io.BytesIO(b'{}'))
        client.opener = Mock()
        client.opener.open.side_effect = [error, response]
        self.assertEqual(client.request("test", "https://example.test", {}), {"ok": True})
        self.assertEqual(client.opener.open.call_count, 2)
        sleep.assert_called_once()

    @patch("event_router.time.sleep")
    def test_long_retry_after_deferred_not_ignored(self, sleep):
        client = er.HTTP(interval=0)
        client.opener = Mock()
        client.opener.open.side_effect = HTTPError("https://example.test", 429, "rate", {"Retry-After": "900"}, io.BytesIO(b'{}'))
        with self.assertRaisesRegex(er.PipelineError, "deferred_retry_after"):
            client.request("test", "https://example.test", {})
        sleep.assert_not_called()

    def test_quota_stops_without_retry(self):
        client = er.HTTP(interval=0)
        client.opener = Mock()
        client.opener.open.side_effect = HTTPError("https://example.test", 429, "quota", {}, io.BytesIO(b'{"error":{"code":"insufficient_quota"}}'))
        with self.assertRaises(er.FatalError):
            client.request("openai", "https://example.test", {})
        self.assertEqual(client.opener.open.call_count, 1)

    def test_paid_posts_not_replayed_after_uncertain_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = er.Cache(Path(folder)/"cache.db")
            http = Mock()
            http.request.side_effect = er.PipelineError("timeout")
            with self.assertRaises(er.PipelineError):
                er.fetch_posts(http, cache, "https://www.linkedin.com/in/demo", "test")
            with self.assertRaisesRegex(er.PipelineError, "previous_run_uncertain"):
                er.fetch_posts(http, cache, "https://www.linkedin.com/in/demo", "test")
            self.assertEqual(http.request.call_count, 1)
            cache.close()

    def test_cache_expiry(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = er.Cache(Path(folder)/"cache.db")
            cache.put("x", {"a": 1}, -1)
            self.assertIsNone(cache.get("x"))
            cache.put("x", {"a": 1}, 100)
            self.assertEqual(cache.get("x"), {"a": 1})
            cache.close()

    def test_end_to_end_demo_no_network(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(er.HTTP, "request", side_effect=AssertionError("network forbidden")):
            source, output = Path(folder)/"in.json", Path(folder)/"out.json"
            source.write_text(json.dumps([ROW]))
            self.assertEqual(er.main([str(source), "--output", str(output), "--demo"]), 0)
            result = json.loads(output.read_text())
            self.assertEqual(result["mode"], "synthetic_demo")
            self.assertEqual(len(result["ranked_attendees"]), 1)
            self.assertIsNone(result["ranked_attendees"][0]["identity"]["linkedin_url"])

    def test_live_mock_recovery_from_cache_and_sorted_output(self):
        demo = er.demo_record(ROW, er.DEFAULT_ICP)
        assessment = {k: demo[k] for k in er.SCHEMA["properties"]}
        model_response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(assessment)}}], "model": "test-model", "usage": {"total_tokens": 100}}
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {"PDL_API_KEY": "test", "OPENAI_API_KEY": "test"}):
            source, output, cache = [Path(folder)/p for p in ("in.json", "out.json", "cache.db")]
            source.write_text(json.dumps([ROW]))
            argv = [str(source), "--output", str(output), "--cache", str(cache)]
            with patch.object(er.HTTP, "request", side_effect=[pdl_response(), model_response]) as request:
                self.assertEqual(er.main(argv), 0)
                self.assertEqual(request.call_count, 2)
            with patch.object(er.HTTP, "request", side_effect=AssertionError("cache missed")):
                self.assertEqual(er.main(argv), 0)
            result = json.loads(output.read_text())
            self.assertEqual(result["ranked_attendees"][0]["model"], "test-model")

    def test_fatal_auth_writes_partial_matrix(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {"PDL_API_KEY": "test", "OPENAI_API_KEY": "test"}):
            source, output, cache = [Path(folder)/p for p in ("in.json", "out.json", "cache.db")]
            source.write_text(json.dumps([ROW]))
            with patch.object(er.HTTP, "request", side_effect=er.FatalError("pdl_auth_or_quota")):
                self.assertEqual(er.main([str(source), "--output", str(output), "--cache", str(cache)]), 2)
            result = json.loads(output.read_text())
            self.assertEqual(result["run_status"], "incomplete")
            self.assertEqual(result["review_and_errors"][0]["status"], "error")
            self.assertEqual(result["review_and_errors"][0]["error"], "pdl_auth_or_quota")

    def test_ranking_threshold_deduplication_and_exclusion(self):
        first = er.demo_record(ROW, er.DEFAULT_ICP)
        first.update(attendee_id="first", score=9, status="scored")
        first["identity"]["linkedin_url"] = "https://www.linkedin.com/in/example"
        duplicate = copy.deepcopy(first)
        duplicate.update(attendee_id="duplicate", score=8)
        excluded = copy.deepcopy(first)
        excluded.update(attendee_id="excluded", status="excluded", score=10)
        weak = copy.deepcopy(first)
        weak.update(attendee_id="weak", score=3)
        weak["identity"]["linkedin_url"] = "https://www.linkedin.com/in/weak"
        args = SimpleNamespace(top_k=10, demo=False, model="test")
        result = er.output_matrix([weak, duplicate, excluded, first], [], 4, er.DEFAULT_ICP, args, "complete")
        self.assertEqual([r["score"] for r in result["ranked_attendees"]], [9, 8, 3])
        self.assertEqual(result["top_candidate_ids"], ["first"])
        self.assertEqual(result["review_and_errors"][0]["attendee_id"], "excluded")

    def test_ambiguous_identity_skips_model(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {"PDL_API_KEY": "test"}):
            cache = er.Cache(Path(folder)/"cache.db")
            http = Mock()
            http.request.return_value = pdl_response("Former Employer")
            result = er.process(ROW, http, cache, er.DEFAULT_ICP, SimpleNamespace(min_likelihood=8, cache_hours=24))
            self.assertEqual(result["status"], "needs_review")
            self.assertIsNone(result["score"])
            self.assertEqual(http.request.call_count, 1)
            cache.close()


if __name__ == "__main__":
    unittest.main()
