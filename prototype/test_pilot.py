"""Regression tests for integration boundaries and pilot measurements; no network."""
import copy
from datetime import datetime, timezone
from http.client import IncompleteRead
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import event_router as er
import pilot
from test_event_router import ROW, pdl_response


class IntegrationRegressions(unittest.TestCase):
    def test_pdl_malformed_optional_data_is_not_evidence(self):
        raw = pdl_response()
        raw['data'].update(summary={'email': 'DO_NOT_RETAIN'}, skills=[{'private': 'DO_NOT_RETAIN'}, 'python'],
                           experience=[{'company': 'broken', 'title': [], 'summary': {'private': 'DO_NOT_RETAIN'}},
                                       {'company': {'name': 'GE'}, 'title': None}, None])
        http = Mock()
        http.request.return_value = raw
        identity, profile = er.resolve(http, ROW, 'test', 8)
        self.assertEqual(identity['status'], 'high_confidence_match')
        self.assertIsNone(profile['summary'])
        self.assertEqual(profile['skills'], ['python'])
        self.assertEqual(len(profile['experience']), 1)
        self.assertNotIn('DO_NOT_RETAIN', json.dumps(er.evidence_for(profile, identity, [])))
        raw['data']['experience'] = {'bad': 'shape'}
        self.assertEqual(er.resolve(http, ROW, 'test', 8)[1]['experience'], [])

    def test_identity_rejects_empty_normalized_company(self):
        http = Mock()
        http.request.return_value = pdl_response('LLC')
        row = {**ROW, 'Current Company': 'Inc'}
        self.assertEqual(er.resolve(http, row, 'test', 8)[0]['status'], 'needs_review')

    def test_pdl_malformed_match_array_fails_closed(self):
        http = Mock()
        raw = pdl_response()
        raw['matched'] = ['name', 'company', {}]
        http.request.return_value = raw
        with self.assertRaisesRegex(er.PipelineError, 'pdl_invalid_response'):
            er.resolve(http, ROW, 'test', 8)

    def test_bad_profile_url_does_not_raise(self):
        for url in ('https://[broken/in/foo', 'linkedin.com/in/foo%ZZ', 'linkedin.com/in/%'):
            self.assertIsNone(er.linkedin_url(url))

    def test_posts_validate_source_and_sort_actual_instants(self):
        target = 'https://www.linkedin.com/in/alex-demo'
        base = {'type': 'post', 'author': {'linkedinUrl': target}, 'content': 'Example',
                'postedAt': {'date': '2026-10-01T23:00:00-02:00'},
                'linkedinUrl': 'https://www.linkedin.com/posts/newer?tracking=1'}
        older = copy.deepcopy(base)
        older.update(postedAt={'date': '2026-10-02T00:00:00Z'}, linkedinUrl='https://www.linkedin.com/posts/older')
        invalid = []
        for source in ('http://www.linkedin.com/posts/a', 'https://evil@www.linkedin.com/posts/a',
                       'https://www.linkedin.com/in/alex-demo', 'https://[bad/posts/a'):
            invalid.append({**base, 'linkedinUrl': source})
        result = er.normalize_posts(invalid + [older, base], target, datetime(2026, 10, 3, tzinfo=timezone.utc))
        self.assertEqual([p['url'] for p in result], ['https://www.linkedin.com/posts/newer', 'https://www.linkedin.com/posts/older'])

    @patch('event_router.time.sleep')
    def test_incomplete_http_read_retries_but_paid_post_does_not(self, sleep):
        client = er.HTTP(interval=0, attempts=2)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.side_effect = [IncompleteRead(b'partial'), b'{}']
        client.opener = Mock()
        client.opener.open.return_value = response
        self.assertEqual(client.request('pdl', 'https://example.test', {}), {})
        self.assertEqual(client.usage['pdl']['request_attempts'], 2)
        response.read.side_effect = IncompleteRead(b'partial')
        with self.assertRaisesRegex(er.PipelineError, 'apify_transport_error'):
            client.request('apify', 'https://example.test', {}, payload={}, safe_retry=False)
        self.assertEqual(client.usage['apify']['request_attempts'], 1)

    def test_http_token_meter_includes_observed_response_usage(self):
        client = er.HTTP(interval=0)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}'
        client.opener = Mock()
        client.opener.open.return_value = response
        client.request('openai', 'https://example.test', {}, payload={})
        self.assertEqual(client.openai_tokens['total_tokens'], 12)

    def test_null_model_message_becomes_safe_pipeline_error(self):
        http = Mock()
        http.request.return_value = {'choices': [{'message': None}]}
        with self.assertRaisesRegex(er.PipelineError, 'model_invalid_response'):
            er.score(http, [], er.DEFAULT_ICP, 'test', 'test')

    def test_fatal_scoring_preserves_identity_and_pending_rows(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'PDL_API_KEY': 'test', 'OPENAI_API_KEY': 'test'}):
            source, output, cache = [Path(folder)/x for x in ('input.json', 'output.json', 'cache.db')]
            source.write_text(json.dumps([ROW, {**ROW, 'Attendee Name': 'Second Person'}]))
            with patch.object(er.HTTP, 'request', side_effect=[pdl_response(), er.FatalError('openai_auth_or_quota')]):
                self.assertEqual(er.main([str(source), '--output', str(output), '--cache', str(cache)]), 2)
            matrix = json.loads(output.read_text())
            first, second = matrix['review_and_errors']
            self.assertEqual(first['identity']['status'], 'high_confidence_match')
            self.assertTrue(first['evidence'])
            self.assertEqual(first['status'], 'error')
            self.assertIsNone(first['score'])
            self.assertEqual(second['status'], 'not_processed')
            self.assertEqual(matrix['processed_unique_attendees'], 1)
            self.assertEqual(matrix['top_candidate_ids'], [])

    def test_all_checkpoints_account_for_every_input(self):
        snapshots = []
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'in.json', Path(folder)/'out.json'
            source.write_text(json.dumps([ROW, {**ROW, 'Attendee Name': 'Second Person'}]))
            with patch.object(er, 'atomic_json', side_effect=lambda path, value: snapshots.append(copy.deepcopy(value))):
                self.assertEqual(er.main([str(source), '--output', str(output), '--demo']), 0)
        self.assertEqual(len(snapshots), 4)
        self.assertEqual(len(snapshots[0]['review_and_errors']), 2)
        for snapshot in snapshots:
            self.assertEqual(len(pilot.records(snapshot)), 2)
            self.assertIsNotNone(snapshot['run_id'])


class PilotTests(unittest.TestCase):
    def matrix(self):
        first = er.demo_record(ROW, er.DEFAULT_ICP)
        second = er.demo_record({**ROW, 'attendee_id': 'second'}, er.DEFAULT_ICP)
        return er.output_matrix([first, second], [], 2, er.DEFAULT_ICP,
                                SimpleNamespace(demo=True, model='test', top_k=10), 'complete')

    def test_unknown_labels_are_not_negative(self):
        matrix = self.matrix()
        review = pilot.review_template(matrix)
        review['attendees'][0].update(useful_to_meet=True, icebreaker_supported=False, reviewer='Founder')
        result = pilot.summarize(matrix, review)
        quality = result['shortlist_quality']['top_5']
        self.assertEqual(quality['useful_among_reviewed']['fraction'], 1)
        self.assertEqual(quality['confirmed_useful_among_available']['fraction'], .5)
        self.assertEqual(quality['unreviewed'], 1)
        self.assertEqual(result['unsupported_hooks_among_reviewed']['numerator'], 1)

    def test_review_binding_labels_and_duplicates(self):
        matrix = self.matrix()
        for mutation in ('digest', 'duplicate', 'bad_label', 'missing_reviewer'):
            review = pilot.review_template(matrix)
            if mutation == 'digest':
                review['output_digest'] = 'other'
            elif mutation == 'duplicate':
                review['attendees'].append(review['attendees'][0])
            elif mutation == 'bad_label':
                review['attendees'][0]['useful_to_meet'] = 'yes'
            else:
                review['attendees'][0]['useful_to_meet'] = True
            with self.assertRaises(er.PipelineError):
                pilot.summarize(matrix, review)

    def test_coverage_denominators_exclude_invalid_and_unprocessed(self):
        matrix = self.matrix()
        first = matrix['ranked_attendees'].pop()
        first.update(status='error', score=None, identity={'status': 'high_confidence_match'})
        matrix['ranked_attendees'] = []
        matrix['review_and_errors'] = [first, {**ROW, 'status': 'not_processed_limit'}, {'status': 'invalid_input'}]
        result = pilot.summarize(matrix)
        self.assertEqual(result['resolved_coverage'], pilot.fraction(1, 1))
        self.assertEqual(result['error_coverage'], pilot.fraction(1, 1))
        self.assertIsNone(result['unsupported_hooks_among_reviewed']['fraction'])

    def test_preflight_never_calls_network_or_reveals_keys(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'PDL_API_KEY': 'secret-sentinel'}), patch.object(er.HTTP, 'request', side_effect=AssertionError('network forbidden')):
            source = Path(folder)/'in.json'
            source.write_text(json.dumps([ROW]))
            result = pilot.preflight(source)
            self.assertTrue(result['credentials_present']['PDL_API_KEY'])
            self.assertFalse(result['pilot_size_ok'])
            self.assertNotIn('secret-sentinel', json.dumps(result))

    def test_review_export_does_not_overwrite_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'in.json', Path(folder)/'review.json'
            source.write_text(json.dumps(self.matrix()))
            self.assertEqual(pilot.main(['review', str(source), '--output', str(output)]), 0)
            saved = output.read_bytes()
            self.assertEqual(pilot.main(['review', str(source), '--output', str(output)]), 2)
            self.assertEqual(output.read_bytes(), saved)

class FurtherRegressions(unittest.TestCase):
    def test_company_normalization_preserves_meaningful_punctuation(self):
        self.assertEqual(er.company_norm('Example Tools, Inc.'), er.company_norm('EXAMPLE Tools'))
        self.assertNotEqual(er.company_norm('C++'), er.company_norm('C'))
        http = Mock()
        http.request.return_value = pdl_response('C')
        self.assertEqual(er.resolve(http, {**ROW, 'Current Company': 'C++'}, 'test', 8)[0]['status'], 'needs_review')

    def test_distinct_input_titles_not_collapsed(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'input.json'
            source.write_text(json.dumps([{**ROW, 'Job Title': 'C++ Developer'}, {**ROW, 'Job Title': 'C# Developer'}]))
            self.assertEqual(len(er.ingest(source)[0]), 2)

    def test_cached_posts_rechecked_for_age_without_new_paid_call(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = er.Cache(Path(folder)/'cache.db')
            url = 'https://www.linkedin.com/in/demo'
            cache.put(er.digest([er.VERSION, 'posts', url]), [
                {'text': 'Stale', 'url': 'https://www.linkedin.com/posts/stale', 'posted_at': '2000-01-01T00:00:00+00:00'}], 86400)
            http = Mock()
            self.assertEqual(er.fetch_posts(http, cache, url, 'test'), [])
            http.request.assert_not_called()
            cache.close()


class SuppliedProfileTests(unittest.TestCase):
    def test_supplied_urls_preserved_and_conflicts_not_deduplicated(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'input.json'
            source.write_text(json.dumps([{**ROW, 'LinkedIn URL': 'linkedin.com/in/alex-demo'},
                                          {**ROW, 'LinkedIn URL': 'linkedin.com/in/other'},
                                          {**ROW, 'LinkedIn URL': 'https://evil.test/in/demo'}]))
            rows, rejected, total = er.ingest(source)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['profile_url_source'], 'user_supplied_input')
            self.assertEqual(len(rejected), 1)

    def test_provider_url_conflict_skips_model_even_with_cached_identity(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'PDL_API_KEY': 'test'}):
            cache = er.Cache(Path(folder)/'cache.db')
            http = Mock()
            http.request.return_value = pdl_response()
            row = {**ROW, 'LinkedIn URL': 'https://www.linkedin.com/in/other'}
            args = SimpleNamespace(min_likelihood=8, cache_hours=24)
            for _ in range(2):
                result = er.process(row, http, cache, er.DEFAULT_ICP, args)
                self.assertEqual(result['status'], 'needs_review')
                self.assertIn('supplied_profile_url_mismatch', result['identity']['review_reasons'])
                self.assertIsNone(result['score'])
            self.assertEqual(http.request.call_count, 1)
            cache.close()

if __name__ == '__main__':
    unittest.main()
