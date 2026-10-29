"""Offline contract tests for revision boundaries, JSON splicing and scope locks.

No browser, AWS, report-generation or remote publication entry point is invoked.
"""
import builtins
import copy
import datetime as dt
import importlib.util
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / 'build_revisions.py'


def load_builder():
    spec = importlib.util.spec_from_file_location('retail_builder_tested', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b = load_builder()


class OfflineImportTests(unittest.TestCase):
    def test_import_needs_no_optional_browser_or_remote_services(self):
        original_import = builtins.__import__

        def stdlib_only(name, *args, **kwargs):
            if name.split('.')[0] in {'playwright', 'pypdf', 'boto3', 'bs4', 'requests'}:
                raise AssertionError('Optional dependency imported by pure builder module: ' + name)
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, '__import__', side_effect=stdlib_only), \
             patch.object(socket, 'create_connection', side_effect=AssertionError('Network attempted')), \
             patch.object(subprocess, 'check_output', side_effect=AssertionError('External command attempted')):
            module = load_builder()
            self.assertEqual(module.replace_sequence(['macro', 'old', 'footer'], ['old'], ['new']),
                             ['macro', 'new', 'footer'])


class SequenceTests(unittest.TestCase):
    def test_unique_sequence_splice_preserves_adjacent_and_nested_values(self):
        prefix = {'section': 'macro', 'paragraphs': ['unchanged', {'number': 4.25}]}
        suffix = {'section': 'footer', 'body': 'literal \\n and actual\nnewline'}
        values = [prefix, 'lead', {'text': 'old side'}, suffix]
        before = copy.deepcopy(values)
        result = b.replace_sequence(values, ['lead', {'text': 'old side'}], ['new lead'])
        self.assertEqual(result, [prefix, 'new lead', suffix])
        self.assertEqual(values, before)

    def test_missing_sequence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not uniquely found'):
            b.replace_sequence(['macro', 'current', 'footer'], ['stale'], ['replacement'])

    def test_repeated_and_overlapping_sequences_are_ambiguous(self):
        for values, original in [(['old', 'x', 'old'], ['old']), (['a', 'a', 'a'], ['a', 'a'])]:
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, 'not uniquely found'):
                b.replace_sequence(values, original, ['replacement'])

    def test_empty_original_sequence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Empty original'):
            b.replace_sequence(['macro', 'footer'], [], ['retail'])

    def test_shortening_can_remove_an_unchanged_retail_sequence(self):
        self.assertEqual(b.replace_sequence(['macro', 'repeated side', 'footer'], ['repeated side'], []),
                         ['macro', 'footer'])


class BoundsTests(unittest.TestCase):
    def test_heading_and_first_following_footer_boundary(self):
        prefix = '<html><body><hr><h2>Other section</h2><p>macro stays</p>\n'
        fragment = '<H2 id="retail" style="color:#ff6b35">🔥 What Retail Is Playing </H2>\n<div>retail</div>\n'
        suffix = '<HR class="footer"><p>disclaimer stays</p></body></html>'
        page = prefix + fragment + suffix
        start, end = b.bounds(page)
        self.assertEqual(page[:start], prefix)
        self.assertEqual(page[start:end], fragment)
        self.assertEqual(page[end:], suffix)
        revised = page[:start] + '<h2>replacement</h2>' + page[end:]
        self.assertTrue(revised.startswith(prefix))
        self.assertTrue(revised.endswith(suffix))

    def test_body_close_fallback_keeps_document_closing_bytes(self):
        prefix = '<!doctype html><body><p>prior body</p>'
        fragment = '<h2>What Retail Is Playing</h2><p>retail without a footer rule</p>\n'
        suffix = '</BODY  >\n</html>'
        start, end = b.bounds(prefix + fragment + suffix)
        self.assertEqual((prefix + fragment + suffix)[start:end], fragment)
        self.assertEqual((prefix + fragment + suffix)[end:], suffix)

    def test_footer_before_heading_is_not_used_as_end_boundary(self):
        page = '<hr><h2>What Retail Is Playing</h2><p>last section</p></body>'
        start, end = b.bounds(page)
        self.assertGreater(start, 0)
        self.assertEqual(page[end:], '</body>')

    def test_missing_retail_heading_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Retail heading not found'):
            b.bounds('<body><h2>Some other report section</h2><hr></body>')

    def test_missing_footer_and_body_close_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Retail/footer boundary not found'):
            b.bounds('<h2>What Retail Is Playing</h2><div>truncated document</div>')


class PatchJsonTests(unittest.TestCase):
    def fixture(self):
        old = {'subheadings': ['old retail lead', 'old retail side'],
               'body': [{'text': 'old lead prose'}, {'text': 'old side prose'}]}
        new = {'subheadings': ['new retail lead'], 'body': [{'text': 'new lead prose'}]}
        original = {'report_date': '2026-03-27', 'generated_at': '2026-10-26T21:38:29Z',
                    'news_cutoff_utc': '2026-03-27T00:00:00Z',
                    'sections': [{'title': 'Whole report',
                                  'subheadings': ['Macro', *old['subheadings'], 'Evidence ledger'],
                                  'body': [{'text': 'macro with fixed close 4.25'}, *old['body'],
                                           {'text': 'footer evidence must remain'}],
                                  'untouched': {'nested': [None, True, 'literal\\n', 'real\nnewline']}}],
                    'evidence': {'macro-source': {'published_at': '2026-03-26T12:00:00Z'}},
                    'unknown_metadata': None}
        fragments = {'old': [old], 'new': [new]}
        parser = SimpleNamespace(sections=lambda fragment: copy.deepcopy(fragments[fragment]))
        return original, fragments, parser

    def test_splice_preserves_unrelated_json_body_cutoff_and_generation(self):
        original, fragments, parser = self.fixture()
        untouched = copy.deepcopy(original)
        result = b.patch_json(original, 'old', 'new', parser)
        expected = copy.deepcopy(original)
        expected['sections'][0]['subheadings'] = ['Macro', 'new retail lead', 'Evidence ledger']
        expected['sections'][0]['body'] = [{'text': 'macro with fixed close 4.25'}, {'text': 'new lead prose'},
                                         {'text': 'footer evidence must remain'}]
        timestamp = result.pop('retail_revised_at_utc')
        self.assertIsNotNone(dt.datetime.fromisoformat(timestamp).tzinfo)
        self.assertIn('original report cutoff preserved', result.pop('retail_revision_scope'))
        self.assertEqual(result, expected)
        self.assertEqual(original, untouched)
        # The output must not alias unrelated nested data from the input object.
        result['sections'][0]['untouched']['nested'].append('output edit')
        self.assertEqual(original, untouched)
        self.assertEqual(fragments['old'][0]['body'], [{'text': 'old lead prose'}, {'text': 'old side prose'}])

    def test_missing_original_cutoff_is_not_invented(self):
        original, _, parser = self.fixture()
        del original['news_cutoff_utc']
        result = b.patch_json(original, 'old', 'new', parser)
        self.assertNotIn('news_cutoff_utc', result)
        self.assertEqual(result['generated_at'], original['generated_at'])

    def test_ambiguous_body_is_rejected_without_partial_input_mutation(self):
        original, fragments, parser = self.fixture()
        original['sections'][0]['body'] += copy.deepcopy(fragments['old'][0]['body'])
        snapshot = copy.deepcopy(original)
        with self.assertRaisesRegex(ValueError, 'not uniquely found'):
            b.patch_json(original, 'old', 'new', parser)
        self.assertEqual(original, snapshot)

    def test_missing_heading_sequence_is_rejected_without_input_mutation(self):
        original, _, parser = self.fixture()
        original['sections'][0]['subheadings'] = ['Macro', 'different retail', 'Evidence ledger']
        snapshot = copy.deepcopy(original)
        with self.assertRaisesRegex(ValueError, 'not uniquely found'):
            b.patch_json(original, 'old', 'new', parser)
        self.assertEqual(original, snapshot)

    def test_nonunique_heading_sequence_is_rejected(self):
        original, fragments, parser = self.fixture()
        original['sections'][0]['subheadings'] += fragments['old'][0]['subheadings']
        with self.assertRaisesRegex(ValueError, 'not uniquely found'):
            b.patch_json(original, 'old', 'new', parser)

    def test_unexpected_parser_or_original_section_shapes_are_rejected(self):
        for part, count in [('old', 0), ('old', 2), ('new', 0), ('new', 2), ('original', 0), ('original', 2)]:
            with self.subTest(part=part, count=count):
                original, fragments, parser = self.fixture()
                if part == 'original':
                    original['sections'] *= count
                else:
                    fragments[part] *= count
                with self.assertRaisesRegex(ValueError, 'section shape'):
                    b.patch_json(original, 'old', 'new', parser)


EXPECTED_TIMING_PATHS = {
    '2025-12-11': ('n5045', ['sectors', 8, 'parts', 1, 1]),
    '2025-12-19': ('n3727', ['sectors', 8, 'parts', 0, 1]),
    '2025-12-30': ('n2738', ['anticipatory', 2, 'parts', 1, 1]),
}


def assign(document, path, value):
    node = document
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


class ScopeTests(unittest.TestCase):
    def fixture(self, date):
        source, path = EXPECTED_TIMING_PATHS[date]
        before = {'date': date, 'generated_at': 'generation stays byte exact', 'news_cutoff_utc': date + 'T00:00:00Z',
                  'sectors': [{'parts': [['Narrative', 'untouched narrative'], ['Reported', 'untouched result']]}
                              for _ in range(9)],
                  'anticipatory': [{'parts': [['What Is Priced', 'untouched scenario'],
                                              ['Conditional Expression', 'untouched expression']]}
                                  for _ in range(3)],
                  'retail': ['old retail'], 'retail_intro': 'old intro'}
        old_value = 'Late outcome must be removed [[' + source + ']]'
        new_value = 'Earlier supported or conditional evidence replaces the late outcome.'
        assign(before, path, old_value)
        after = copy.deepcopy(before)
        assign(after, path, new_value)
        after['retail'] = ['revised retail']
        row = {'date': date, 'path': copy.deepcopy(path), 'removed_source_ids': [source],
               'before': old_value, 'after': new_value}
        return before, after, row

    def test_retail_fields_can_change_without_mutating_inputs(self):
        before = {'date': '2025-09-01', 'retail': ['old'], 'retail_intro': 'old intro', 'other': {'same': None}}
        after = copy.deepcopy(before)
        after['retail'] = ['new lead', 'new side']
        after['retail_intro'] = 'new intro'
        snapshot = copy.deepcopy((before, after))
        self.assertEqual(b.validate_spec_scope(before, after, before['date'], []), [])
        self.assertEqual((before, after), snapshot)

    def test_only_exact_three_reviewed_timing_scopes_are_approved(self):
        self.assertEqual(b.TIMING_PATHS, EXPECTED_TIMING_PATHS)
        for date in EXPECTED_TIMING_PATHS:
            with self.subTest(date=date):
                before, after, row = self.fixture(date)
                snapshot = copy.deepcopy((before, after, row))
                self.assertEqual(b.validate_spec_scope(before, after, date, [row]), [row])
                self.assertEqual((before, after, row), snapshot)

    def test_unlogged_nonretail_value_or_metadata_changes_are_rejected(self):
        before, _, _ = self.fixture('2025-12-11')
        for path, replacement in [(['sectors', 0, 'parts', 0, 1], 'changed macro claim'),
                                  (['generated_at'], 'different generation'),
                                  (['news_cutoff_utc'], '2025-12-12T00:00:00Z')]:
            with self.subTest(path=path):
                after = copy.deepcopy(before)
                assign(after, path, replacement)
                with self.assertRaisesRegex(ValueError, 'Non-retail spec changed'):
                    b.validate_spec_scope(before, after, '2025-12-11', [])

    def test_approved_repair_does_not_allow_an_additional_nonretail_change(self):
        before, after, row = self.fixture('2025-12-11')
        after['sectors'][0]['parts'][0][1] = 'unlogged extra change'
        with self.assertRaisesRegex(ValueError, 'Non-retail spec changed'):
            b.validate_spec_scope(before, after, '2025-12-11', [row])

    def test_unapproved_path_source_or_date_cannot_authorise_a_change(self):
        for kind in ['path', 'source', 'date']:
            with self.subTest(kind=kind):
                before, after, row = self.fixture('2025-12-11')
                if kind == 'path':
                    row['path'] = ['sectors', 7, 'parts', 1, 1]
                elif kind == 'source':
                    row['removed_source_ids'] = ['n9999']
                else:
                    row['date'] = '2025-12-12'
                with self.assertRaises(ValueError):
                    b.validate_spec_scope(before, after, '2025-12-11', [row])

    def test_logged_before_and_after_must_match_reviewed_values(self):
        for field in ['before', 'after']:
            with self.subTest(field=field):
                before, after, row = self.fixture('2025-12-19')
                row[field] = 'audit value does not match the document'
                with self.assertRaisesRegex(ValueError, 'exact reviewed values'):
                    b.validate_spec_scope(before, after, '2025-12-19', [row])

    def test_removed_source_cannot_remain_in_reviewed_replacement(self):
        before, after, row = self.fixture('2025-12-30')
        row['after'] += ' [[n2738]]'
        assign(after, row['path'], row['after'])
        with self.assertRaisesRegex(ValueError, 'exact reviewed values'):
            b.validate_spec_scope(before, after, '2025-12-30', [row])

    def test_duplicate_timing_repair_rows_are_rejected(self):
        before, after, row = self.fixture('2025-12-11')
        with self.assertRaisesRegex(ValueError, 'exact reviewed values'):
            b.validate_spec_scope(before, after, '2025-12-11', [row, copy.deepcopy(row)])

    def test_missing_and_null_unrelated_metadata_are_distinct(self):
        before = {'retail': ['old'], 'retail_intro': 'old intro', 'nullable_metadata': None}
        cases = []
        removed = copy.deepcopy(before)
        del removed['nullable_metadata']
        cases.append(removed)
        added = copy.deepcopy(before)
        added['unlogged_new_key'] = None
        cases.append(added)
        for after in cases:
            with self.subTest(after=after), self.assertRaisesRegex(ValueError, 'Non-retail spec changed'):
                b.validate_spec_scope(before, after, '2025-09-01', [])

    def test_other_date_repair_rows_do_not_change_current_scope(self):
        before = {'date': '2025-09-01', 'retail': ['old'], 'other': 'unchanged'}
        after = copy.deepcopy(before)
        after['retail'] = ['new']
        _, _, row = self.fixture('2025-12-11')
        self.assertEqual(b.validate_spec_scope(before, after, '2025-09-01', [row]), [])


if __name__ == '__main__':
    unittest.main()
