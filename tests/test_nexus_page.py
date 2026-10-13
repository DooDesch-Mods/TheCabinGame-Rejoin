import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('rejoin_nexus_page', TOOLS / 'nexus_page.py')
page = importlib.util.module_from_spec(spec)
spec.loader.exec_module(page)

class PageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        (root / 'docs').mkdir()
        (root / 'docs/nexus-summary.txt').write_text('Early development state: manual Rejoin.', encoding='utf-8')
        (root / 'docs/nexus-description.bbcode').write_text('[b]Early development state.[/b] Four-account test remains outstanding.', encoding='utf-8')
        self.root = root
        self.detail = {'id': '45363444580354', 'game_id': '10562', 'game_scoped_id': '2', 'summary': 'Old', 'description': 'Old'}
        self.parent = {'mods': [{'id': '45363444580354', 'status': 'not_published'}]}
        for helper in [patch.object(page, 'ROOT', root), patch.dict(page.os.environ, {'NEXUS_MOD_ID': '45363444580354', 'NEXUS_GAME_SCOPED_ID': '2'}, clear=True), patch.object(sys, 'argv', ['nexus_page.py', '--execute'])]:
            helper.start()
            self.addCleanup(helper.stop)

    def run_page(self, api):
        detail = self.detail | {'summary': 'Early development state: manual Rejoin.', 'description': '[b]Early development state.[/b] Four-account test remains outstanding.'}
        with patch.object(page, 'read_text', return_value=detail), patch.object(page, 'api', side_effect=api) as calls, contextlib.redirect_stdout(io.StringIO()):
            page.main()
        return calls

    def test_other_mod_configuration_never_reaches_api(self):
        with patch.dict(page.os.environ, {'NEXUS_MOD_ID': '45363444580355'}), patch.object(page, 'api') as calls:
            with self.assertRaisesRegex(ValueError, 'identity differs'):
                page.main()
            calls.assert_not_called()

    def test_other_page_readback_cannot_be_patched(self):
        with patch.object(page, 'api', return_value=self.detail | {'game_scoped_id': '3'}) as calls:
            with self.assertRaisesRegex(ValueError, 'page identity differs'):
                page.main()
            self.assertEqual(calls.call_count, 1)

    def test_current_description_has_no_mutation(self):
        detail = self.detail | {'summary': 'Early development state: manual Rejoin.', 'description': '[b]Early development state.[/b] Four-account test remains outstanding.'}
        calls = self.run_page([detail, self.parent])
        self.assertEqual(calls.call_count, 2)
        self.assertTrue(json.loads((self.root / 'dist/nexus-page.json').read_bytes())['confirmed'])

    def test_patch_requires_exact_saved_text(self):
        with patch.object(page, 'read_text', side_effect=[self.detail, self.detail]), patch.object(page, 'api', side_effect=[self.detail, self.parent, None, self.detail]):
            with self.assertRaisesRegex(ValueError, 'readback differs'):
                page.main()
        receipt = json.loads((self.root / 'dist/nexus-page.json').read_bytes())
        self.assertTrue(receipt['attempted'])
        self.assertFalse(receipt['confirmed'])
        self.assertTrue(receipt['failure']['retry_requires_readback'])

    def test_exact_patch_readback_confirms_disclosure(self):
        detail = self.detail | {'summary': 'Early development state: manual Rejoin.', 'description': '[b]Early development state.[/b] Four-account test remains outstanding.'}
        with patch.object(page, 'read_text', side_effect=[self.detail, detail]), patch.object(page, 'api', side_effect=[self.detail, self.parent, None, self.detail]) as calls, contextlib.redirect_stdout(io.StringIO()):
            page.main()
        self.assertEqual(calls.call_args_list[2].args[:2], ('PATCH', '/mods/45363444580354'))
        self.assertTrue(json.loads((self.root / 'dist/nexus-page.json').read_bytes())['confirmed'])

    def test_legacy_breaks_and_entities_preserve_text(self):
        self.assertEqual(page.canonical_text('A &amp; B\r<br />Second line'), 'A & B\nSecond line')
        self.assertNotEqual(page.canonical_text('Early development state'), page.canonical_text('Stable release'))

    def test_unpublished_missing_text_adopts_only_same_ack_without_patch(self):
        import hashlib
        description = '[b]Early development state.[/b] Four-account test remains outstanding.'
        ack = {'uid': '45363444580354', 'scoped': '2', 'patch_acknowledged': True,
               'description_sha256': hashlib.sha256(description.encode()).hexdigest(), 'source_run': 'retained-run'}
        (self.root / 'docs/nexus-page-ack.json').write_text(json.dumps(ack), encoding='utf-8')
        with patch.object(page, 'read_text', return_value={'text_available': False}), patch.object(page, 'api', side_effect=[self.detail, self.parent]) as calls, contextlib.redirect_stdout(io.StringIO()):
            page.main()
        self.assertEqual(calls.call_count, 2)
        receipt = json.loads((self.root / 'dist/nexus-page.json').read_bytes())
        self.assertTrue(receipt['patch_acknowledged'])
        self.assertFalse(receipt['description_readback_confirmed'])

    def test_missing_text_and_wrong_ack_never_writes(self):
        ack = {'uid': '45363444580354', 'scoped': '2', 'patch_acknowledged': True, 'description_sha256': 'different'}
        (self.root / 'docs/nexus-page-ack.json').write_text(json.dumps(ack), encoding='utf-8')
        with patch.object(page, 'read_text', return_value={'text_available': False}), patch.object(page, 'api', side_effect=[self.detail, self.parent]) as calls:
            with self.assertRaisesRegex(ValueError, 'acknowledgment differs'):
                page.main()
        self.assertEqual(calls.call_count, 2)

    def test_authorized_new_unpublished_text_retains_ack_without_claiming_readback(self):
        ack = {'uid': '45363444580354', 'scoped': '2', 'patch_acknowledged': True, 'description_sha256': 'previous-text'}
        (self.root / 'docs/nexus-page-ack.json').write_text(json.dumps(ack), encoding='utf-8')
        with patch.object(sys, 'argv', ['nexus_page.py', '--execute', '--replace-unpublished-text']), patch.object(page, 'read_text', return_value={'text_available': False}), patch.object(page, 'api', side_effect=[self.detail, self.parent, None]) as calls, contextlib.redirect_stdout(io.StringIO()):
            page.main()
        self.assertEqual(calls.call_args_list[2].args[:2], ('PATCH', '/mods/45363444580354'))
        receipt = json.loads((self.root / 'dist/nexus-page.json').read_bytes())
        self.assertTrue(receipt['patch_acknowledged'])
        self.assertTrue(receipt['confirmed'])
        self.assertFalse(receipt['description_readback_confirmed'])

    def test_failed_new_unpublished_text_patch_remains_failed(self):
        ack = {'uid': '45363444580354', 'scoped': '2', 'patch_acknowledged': True, 'description_sha256': 'previous-text'}
        (self.root / 'docs/nexus-page-ack.json').write_text(json.dumps(ack), encoding='utf-8')
        with patch.object(sys, 'argv', ['nexus_page.py', '--execute', '--replace-unpublished-text']), patch.object(page, 'read_text', return_value={'text_available': False}), patch.object(page, 'api', side_effect=[self.detail, self.parent, RuntimeError('retained HTTP failure')]):
            with self.assertRaisesRegex(RuntimeError, 'retained HTTP failure'):
                page.main()
        receipt = json.loads((self.root / 'dist/nexus-page.json').read_bytes())
        self.assertTrue(receipt['attempted'])
        self.assertFalse(receipt['confirmed'])
        self.assertNotIn('patch_acknowledged', receipt)
        self.assertTrue(receipt['failure']['retry_requires_readback'])

if __name__ == '__main__':
    unittest.main()
