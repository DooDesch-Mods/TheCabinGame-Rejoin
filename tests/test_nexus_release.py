"""Exercise prepared early releases, exact upload binding and requirements readback."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import nexus_release as release
import nexus_draft as draft

class NexusReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=TOOLS.parent / "tests")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "dist").mkdir()
        self.archive = self.root / "dist/CabinRejoin-0.1.0.zip"
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("README.md", "Rejoin is in an early development state.\nA complete test with four different Steam accounts has not yet been performed.\n")
        self.config = {"mod": "CabinRejoin", "version": "0.1.0", "sha256": self.sha(), "bundled_runtime": True}
        self.preparation = {"status": "prepared", "sha256": self.sha(), "version": "0.1.0", "publication_authorized": True, "group_validation": "not_measured"}
        self.manifest = {"runtime_accepted": True, "delivery_accepted": True, "release_prepared": True, "group_validation": "not_measured"}
        self.write_preparation()
        (self.root / "acceptance.json").write_text('{"accepted": false}', encoding="utf-8")
        for target, name, value in [(release, "ROOT", self.root), (release, "RECEIPT", self.root / "dist/nexus-release.json"), (release.package, "CONFIG", self.config)]:
            scope = patch.object(target, name, value)
            scope.start()
            self.addCleanup(scope.stop)
        scope = patch.dict(os.environ, {"NEXUS_MOD_ID": "100", "NEXUS_FILE_GROUP_ID": "200", "NEXUSMODS_API_KEY": "fixture-secret", "NEXUS_VERSION_ID": "301"}, clear=True)
        scope.start()
        self.addCleanup(scope.stop)
        scope = patch.object(release.package, "validate", return_value=self.manifest)
        self.package_check = scope.start()
        self.addCleanup(scope.stop)
        self.parent_status = "not_published"
        self.parent_uid = "100"
        self.game_id = "10562"
        self.files = [{"id": "200"}]
        self.versions = [{"id": "299", "file": {"id": "200"}, "category": "main", "position": "1", "version": "old"},
                         {"id": "300", "file": {"id": "200"}, "category": "main", "position": "2", "version": "0.1.0-candidate.abc"}]
        self.definition = {"ranges": [{"target_mod_file": {"id": "400"}, "min_version": {"id": "500", "file": {"id": "400"}}, "max_version": {"id": "501", "file": {"id": "400"}}}]}
        self.dependencies = {"299": [], "300": [copy.deepcopy(self.definition)], "301": []}
        self.dlc = {}
        self.calls = []
        self.ignore_put = False
        scope = patch.object(draft.urllib.request, "urlopen", side_effect=self.http)
        scope.start()
        self.addCleanup(scope.stop)

    def sha(self):
        return hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def write_preparation(self):
        (self.root / "release-preparation.json").write_text(json.dumps(self.preparation), encoding="utf-8")

    def http(self, request, timeout):
        method = request.get_method()
        path = request.full_url.removeprefix(draft.BASE)
        payload = json.loads(request.data) if request.data is not None else None
        self.calls.append((method, path, payload))
        if path == "/mods/batch":
            data = {"data": {"mods": [{"id": self.parent_uid, "game_id": self.game_id, "status": self.parent_status}]}}
        elif path == "/mods/100/files":
            data = {"data": {"mod_files": self.files}}
        elif path == "/mod-files/200/versions":
            data = {"data": {"versions": self.versions}}
        elif path.endswith("/dependencies/dlc"):
            data = {"dlc_dependency_definitions": self.dlc.get(path.split("/")[2], [])}
        elif path.endswith("/dependencies/ranges"):
            version = path.split("/")[2]
            if method == "PUT":
                self.assertEqual(version, "301")
                self.assertEqual(payload, {"dependency_definitions": [{"ranges": [{"min_version_id": "500", "max_version_id": "501"}]}]})
                if not self.ignore_put:
                    self.dependencies[version] = [copy.deepcopy(self.definition)]
                data = None
            else:
                data = {"dependency_definitions": self.dependencies[version]}
        else:
            self.fail(f"unexpected HTTP operation: {method} {path}")
        response = MagicMock()
        response.status = 204 if data is None else 200
        response.headers = {"Content-Type": "application/json"}
        response.read.return_value = b"" if data is None else json.dumps(data).encode()
        response.__enter__.return_value = response
        return response

    def upload(self):
        self.versions[1]["category"] = "archived"
        self.versions.append({"id": "301", "file": {"id": "200"}, "category": "main", "position": "3", "version": "0.1.0"})

    def prepare(self):
        result = release.preflight(self.archive, "0.1.0")
        self.upload()
        return result

    def no_put(self):
        self.assertFalse(any(method == "PUT" for method, _, _ in self.calls))

    def test_ranges_preserved_and_confirmed_readback_does_not_replay_put(self):
        result = self.prepare()
        self.assertTrue(result["release_prepared"])
        self.assertFalse(result["group_accepted"])
        result = release.verify()
        self.assertTrue(result["requirements_confirmed"] and result["parent_identity_confirmed"])
        self.assertEqual(result["confirmed_version_id"], "301")
        self.assertFalse(result["remote_archive_sha256_confirmed"])
        release.verify()
        self.assertEqual(sum(method == "PUT" for method, _, _ in self.calls), 1)
        self.assertNotIn("fixture-secret", release.RECEIPT.read_text())

    def test_published_parent_allowed_and_draft_guard_stays_closed(self):
        self.parent_status = "published"
        self.prepare()
        self.assertEqual(release.verify()["status"], "published")
        with self.assertRaisesRegex(ValueError, "required=not_published"):
            draft.check_parent({"uid": "100", "file": "200", "scoped": "2"}, [{"id": "100", "game_id": "10562", "status": "published"}], {}, [])

    def test_bundled_runtime_allows_empty_dependencies_without_put(self):
        self.dependencies["300"] = []
        self.prepare()
        self.assertTrue(release.verify()["requirements_confirmed"])
        self.no_put()

    def test_unbundled_runtime_still_requires_dependencies(self):
        self.dependencies["300"] = []
        self.config["bundled_runtime"] = False
        with self.assertRaisesRegex(ValueError, "requirements are missing"):
            release.preflight(self.archive, "0.1.0")
        self.assertFalse(release.RECEIPT.exists())

    def test_dlc_blocks_source_and_acknowledged_target_before_put(self):
        self.dlc["300"] = [{"id": "1"}]
        with self.assertRaisesRegex(ValueError, "DLC"):
            release.preflight(self.archive, "0.1.0")
        self.dlc.clear()
        self.prepare()
        self.dlc["301"] = [{"id": "2"}]
        with self.assertRaisesRegex(ValueError, "DLC"):
            release.verify()
        self.no_put()

    def test_missing_previous_foreign_ack_and_wrong_version_category_block(self):
        self.prepare()
        original = copy.deepcopy(self.versions[-1])
        for ack in ("", "300", "999"):
            with patch.dict(os.environ, {"NEXUS_VERSION_ID": ack}), self.subTest(ack=ack), self.assertRaises(ValueError):
                release.verify()
        for change in [{"file": {"id": "999"}}, {"version": "other"}, {"category": "optional"}]:
            self.versions[-1] = dict(original, **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                release.verify()
        self.no_put()

    def test_parent_file_identity_and_requirement_changes_block(self):
        self.prepare()
        self.parent_status = "hidden"
        with self.assertRaisesRegex(ValueError, "published or not_published"):
            release.verify()
        self.parent_status = "published"
        with patch.dict(os.environ, {"NEXUS_MOD_ID": "101"}), self.assertRaisesRegex(ValueError, "identity changed"):
            release.verify()
        self.dependencies["300"][0]["ranges"][0]["min_version"]["id"] = "502"
        with self.assertRaisesRegex(ValueError, "requirements changed"):
            release.verify()
        self.no_put()

    def test_invalid_target_and_existing_version_block_preflight(self):
        self.files = [{"id": "999"}]
        with self.assertRaisesRegex(ValueError, "does not belong"):
            release.preflight(self.archive, "0.1.0")
        self.files = [{"id": "200"}]
        self.versions[-1]["version"] = "0.1.0"
        with self.assertRaisesRegex(ValueError, "no automatic overwrite"):
            release.preflight(self.archive, "0.1.0")
        self.assertFalse(release.RECEIPT.exists())

    def test_uid_game_and_ambiguous_position_block(self):
        for uid, game in [("999", "10562"), ("100", "other")]:
            self.parent_uid, self.game_id = uid, game
            with self.subTest(uid=uid, game=game), self.assertRaises(ValueError):
                release.preflight(self.archive, "0.1.0")
        self.parent_uid, self.game_id = "100", "10562"
        for position in ("2", "NaN", "invalid"):
            self.versions[0]["position"] = position
            with self.subTest(position=position), self.assertRaises(ValueError):
                release.preflight(self.archive, "0.1.0")

    def test_failed_put_is_visible_and_is_not_blindly_replayed(self):
        self.prepare()
        self.ignore_put = True
        with self.assertRaisesRegex(ValueError, "readback differs"):
            release.verify()
        receipt = json.loads(release.RECEIPT.read_text())
        self.assertTrue(receipt["requirements_copy_attempted"])
        self.assertFalse(receipt["requirements_confirmed"])
        with self.assertRaisesRegex(ValueError, "already attempted"):
            release.verify()
        self.assertEqual(sum(method == "PUT" for method, _, _ in self.calls), 1)

    def test_original_http_error_is_redacted_and_retained(self):
        self.prepare()
        cause = draft.urllib.error.HTTPError(draft.BASE + "/mods/batch", 403, "Forbidden", {}, io.BytesIO(b'{"detail":"denied fixture-secret"}'))
        with patch.object(draft.urllib.request, "urlopen", side_effect=cause), self.assertRaisesRegex(RuntimeError, "HTTP 403; denied") as caught:
            release.verify()
        self.assertNotIn("fixture-secret", str(caught.exception))
        self.assertIs(caught.exception.__cause__, cause)

    def test_true_publication_and_disclosures_required_without_faking_acceptance(self):
        self.preparation["publication_authorized"] = False
        self.write_preparation()
        with self.assertRaisesRegex(ValueError, "authorization"):
            release.release_archive()
        self.preparation["publication_authorized"] = True
        self.preparation["group_validation"] = "passed"
        self.write_preparation()
        with self.assertRaisesRegex(ValueError, "preparation is missing"):
            release.release_archive()
        self.assertFalse(json.loads((self.root / "acceptance.json").read_text())["accepted"])

    def test_acceptance_of_another_zip_does_not_claim_group_acceptance(self):
        (self.root / 'acceptance.json').write_text('{"accepted":true,"sha256":"another-build"}')
        receipt = self.prepare()
        self.assertFalse(receipt['group_accepted'])

    def test_invalid_multiline_version_is_blocked_before_api(self):
        self.config['version'] = '0.1.0\nforeign'
        with self.assertRaisesRegex(ValueError, 'SemVer'):
            release.release_archive()
        self.assertEqual(self.calls, [])

    def test_changed_zip_missing_disclosure_and_incomplete_proof_block(self):
        self.prepare()
        with zipfile.ZipFile(self.archive, "w") as zipped:
            zipped.writestr("README.md", "different bytes")
        with self.assertRaisesRegex(ValueError, "preparation is missing"):
            release.verify()
        self.no_put()

    def test_invalid_nexus_target_blocks_github_release_mutation(self):
        self.files = [{"id": "999"}]
        with patch.dict(os.environ, {"PUBLISH_NEXUS": "true", "GITHUB_REPOSITORY": release.REPOSITORY, "GITHUB_SHA": "abc"}), patch.object(release, "require_tag_target"), patch.object(release, "run") as command:
            with self.assertRaisesRegex(ValueError, "does not belong"):
                release.publish_github()
        command.assert_not_called()

    def test_existing_tag_wrong_commit_blocks_github_mutation(self):
        calls = []
        def command(*args):
            calls.append(args)
            if args[-1].endswith('/git/matching-refs/tags/v0.1.0'):
                return '[{"ref":"refs/tags/v0.1.0"}]'
            if args[-1].endswith('/commits/v0.1.0'):
                return '{"sha":"foreign"}'
            self.fail(str(args))
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": release.REPOSITORY, "GITHUB_SHA": "abc"}), patch.object(release, "run", side_effect=command), self.assertRaisesRegex(ValueError, "required=abc"):
            release.publish_github()
        self.assertTrue(all(args[:2] == ("gh", "api") for args in calls))

    def test_github_release_downloaded_zip_checksum_and_output_are_confirmed(self):
        calls = []
        checksum = self.sha() + '  ' + self.archive.name
        def command(*args):
            calls.append(args)
            if args[:3] == ('gh', 'release', 'download'):
                folder = Path(args[args.index('--dir') + 1])
                (folder / self.archive.name).write_bytes(self.archive.read_bytes())
                (folder / 'SHA256SUMS.txt').write_text(checksum + '\n')
                return ''
            path = args[2]
            if '/git/matching-refs/' in path:
                return '[{"ref":"refs/tags/v0.1.0"}]'
            if path.endswith('/commits/v0.1.0'):
                return '{"sha":"abc"}'
            if path.endswith('/releases'):
                return '[[{"tag_name":"v0.1.0","draft":false,"prerelease":false}]]'
            if path.endswith('/releases/tags/v0.1.0'):
                return '{"draft":false,"prerelease":false,"html_url":"https://example.test/release"}'
            self.fail(str(args))
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": release.REPOSITORY, "GITHUB_SHA": "abc"}), patch.object(release, 'run', side_effect=command), patch.object(release, 'write_output') as output:
            release.publish_github()
        self.assertFalse(any(args[:3] == ('gh', 'release', 'create') for args in calls))
        self.assertEqual(output.call_args.args[0]['nexus_ready'], 'false')
        self.assertEqual(output.call_args.args[0]['version'], '0.1.0')

    def test_existing_github_release_wrong_bytes_blocks_success_output(self):
        def command(*args):
            if args[:3] == ('gh', 'release', 'download'):
                folder = Path(args[args.index('--dir') + 1])
                (folder / self.archive.name).write_bytes(b'foreign bytes')
                (folder / 'SHA256SUMS.txt').write_text('foreign hash')
                return ''
            path = args[2]
            if '/git/matching-refs/' in path:
                return '[]'
            if path.endswith('/commits/v0.1.0'):
                return '{"sha":"abc"}'
            if path.endswith('/releases'):
                return '[[{"tag_name":"v0.1.0","draft":false,"prerelease":false}]]'
            if path.endswith('/releases/tags/v0.1.0'):
                return '{"draft":false,"prerelease":false,"html_url":"https://example.test/release"}'
            self.fail(str(args))
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": release.REPOSITORY, "GITHUB_SHA": "abc"}), patch.object(release, 'run', side_effect=command), patch.object(release, 'write_output') as output, self.assertRaisesRegex(ValueError, 'downloaded release ZIP differs'):
            release.publish_github()
        output.assert_not_called()

    def test_workflow_release_is_manual_and_draft_has_no_push_upload(self):
        import yaml
        class Loader(yaml.SafeLoader):
            pass
        Loader.yaml_implicit_resolvers = {key: [(tag, pattern) for tag, pattern in values if tag != 'tag:yaml.org,2002:bool'] for key, values in Loader.yaml_implicit_resolvers.items()}
        root = TOOLS.parent
        workflow = yaml.load((root / '.github/workflows/nexus-release.yml').read_text(), Loader=Loader)
        draft_workflow = yaml.load((root / '.github/workflows/nexus-draft.yml').read_text(), Loader=Loader)
        self.assertEqual(workflow['jobs']['release']['if'], "github.event_name == 'workflow_dispatch'")
        self.assertEqual(workflow['on']['workflow_dispatch']['inputs']['resume_nexus']['default'], 'false')
        target = next(step for step in workflow['jobs']['release']['steps'] if step.get('id') == 'target')
        self.assertEqual(target['env']['RELEASE_PHASE'], "${{ inputs.resume_nexus && 'nexus_only' || 'github' }}")
        self.assertEqual(target['run'], 'python tools/nexus_release.py "$RELEASE_PHASE"')
        self.assertNotIn('push', draft_workflow['on'])
        self.assertEqual(workflow['concurrency']['group'], draft_workflow['concurrency']['group'])
        self.assertEqual(workflow['jobs']['check']['strategy']['matrix']['os'], ['ubuntu-latest', 'windows-latest'])
        step = next(step for step in workflow['jobs']['release']['steps'] if step.get('id') == 'nexus')
        self.assertIn('early development state', step['with']['description'])
        self.assertEqual(step['with']['allow_mod_manager_download'], 'false')
        page = next(step for step in workflow['jobs']['release']['steps'] if step.get('run') == 'python tools/nexus_page.py --execute')
        self.assertEqual(page['if'], "steps.target.outputs.nexus_ready == 'true'")
        self.assertIn('NEXUS_GAME_SCOPED_ID', page['env'])
        draft_page = next(step for step in draft_workflow['jobs']['draft']['steps'] if step.get('run') == 'python tools/nexus_page.py --execute')
        self.assertEqual(draft_page['if'], 'inputs.upload')
        for job in [workflow['jobs']['release'], draft_workflow['jobs']['draft']]:
            artifacts = next(step for step in job['steps'] if step.get('uses', '').startswith('actions/upload-artifact@'))
            self.assertIn('dist/nexus-page.json', artifacts['with']['path'])

    def test_first_github_release_uses_exact_commit_zip_and_checksum(self):
        calls = []
        def command(*args):
            calls.append(args)
            if args[:3] == ('gh', 'release', 'create'):
                self.assertEqual(args[3], 'v0.1.0')
                self.assertIn(str(self.archive), args)
                self.assertIn(str(self.archive.parent / 'SHA256SUMS.txt'), args)
                self.assertEqual(args[args.index('--target') + 1], 'abc')
                self.assertEqual(args[args.index('--repo') + 1], release.REPOSITORY)
                return ''
            if args[:3] == ('gh', 'release', 'download'):
                folder = Path(args[args.index('--dir') + 1])
                (folder / self.archive.name).write_bytes(self.archive.read_bytes())
                (folder / 'SHA256SUMS.txt').write_bytes((self.archive.parent / 'SHA256SUMS.txt').read_bytes())
                return ''
            path = args[2]
            if path.endswith('/releases'):
                return '[]'
            if path.endswith('/commits/v0.1.0'):
                return '{"sha":"abc"}'
            if path.endswith('/releases/tags/v0.1.0'):
                return '{"draft":false,"prerelease":false,"html_url":"https://example.test/first"}'
            self.fail(str(args))
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': release.REPOSITORY, 'GITHUB_SHA': 'abc'}), patch.object(release, 'require_tag_target'), patch.object(release, 'run', side_effect=command), patch.object(release, 'write_output') as output:
            release.publish_github()
        self.assertEqual(sum(args[:3] == ('gh', 'release', 'create') for args in calls), 1)
        self.assertEqual(output.call_args.args[0]['release_url'], 'https://example.test/first')

    def prepare_draft_fixture(self):
        self.config['archive'] = 'artifacts/prepared.zip'
        (self.root / 'artifacts').mkdir()
        (self.root / self.config['archive']).write_bytes(self.archive.read_bytes())
        (self.root / 'package.json').write_text(json.dumps(self.config))
        self.preparation['early_development_state'] = True
        self.write_preparation()

    def test_authorized_draft_uses_public_semver_and_keeps_acceptance_false(self):
        self.prepare_draft_fixture()
        with patch.object(draft, 'ROOT', self.root), patch.object(draft, 'RECEIPT', self.root / 'dist/nexus-draft.json'), patch.object(draft, 'parent', return_value={'status': 'not_published'}), patch.object(draft, 'write_output') as output, patch.object(sys, 'argv', ['nexus_draft.py', 'preflight']), patch.dict(os.environ, {'NEXUS_GAME_SCOPED_ID': '2'}):
            draft.main()
        receipt = json.loads((self.root / 'dist/nexus-draft.json').read_text())
        self.assertFalse(receipt['accepted'])
        self.assertTrue(receipt['release_prepared'])
        self.assertEqual(receipt['version'], '0.1.0')
        self.assertEqual(output.call_args.args[0]['display_name'], 'Rejoin 0.1.0')
        self.assertEqual(Path(receipt['archive']), self.archive)

    def test_draft_build_selects_release_without_any_api_call(self):
        self.prepare_draft_fixture()
        with patch.object(draft, 'ROOT', self.root), patch.object(release.package, 'build', return_value=self.archive) as build, patch.object(sys, 'argv', ['nexus_draft.py', 'build']):
            draft.main()
        build.assert_called_once_with(release=True)
        self.assertEqual(self.calls, [])

    def test_unapproved_draft_remains_candidate_and_wrong_source_hash_blocks(self):
        self.prepare_draft_fixture()
        self.preparation['publication_authorized'] = False
        self.write_preparation()
        with patch.object(draft, 'ROOT', self.root):
            _, accepted, prepared = draft.package_selection()
        self.assertFalse(accepted or prepared)
        self.preparation['publication_authorized'] = True
        self.write_preparation()
        (self.root / self.config['archive']).write_bytes(b'changed source')
        with patch.object(draft, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'public ZIP SHA256 differs'):
            draft.package_selection()

    def recovery_command(self, *args):
        self.recovery_calls.append(args)
        if args[:3] == ('gh', 'release', 'download'):
            folder = Path(args[args.index('--dir') + 1])
            data = b'wrong bytes' if getattr(self, 'recovery_bad_zip', False) else self.archive.read_bytes()
            (folder / self.archive.name).write_bytes(data)
            checksum = 'wrong checksum' if getattr(self, 'recovery_bad_checksum', False) else self.sha() + '  ' + self.archive.name
            (folder / 'SHA256SUMS.txt').write_text(checksum + '\n')
            return ''
        self.assertEqual(args[:2], ('gh', 'api'), 'Recovery must not create, move or upload a GitHub release/tag')
        path = args[2]
        if path.endswith('/releases/tags/v0.1.0'):
            return json.dumps(getattr(self, 'recovery_public', {'tag_name': 'v0.1.0', 'draft': False, 'prerelease': False, 'html_url': 'https://example.test/existing'}))
        if path.endswith('/commits/v0.1.0'):
            return '{"sha":"old-payload-commit"}'
        self.fail(str(args))

    def test_nexus_recovery_new_ci_commit_preserves_existing_github_release(self):
        self.recovery_calls = []
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': release.REPOSITORY, 'GITHUB_SHA': 'new-ci-only-commit', 'PUBLISH_NEXUS': 'true'}), patch.object(release, 'run', side_effect=self.recovery_command), patch.object(release, 'require_tag_target') as tag_guard, patch.object(release, 'write_output') as output:
            release.resume_nexus()
        tag_guard.assert_not_called()
        receipt = json.loads(release.RECEIPT.read_text())
        self.assertEqual(receipt['github_release_tag_commit'], 'old-payload-commit')
        self.assertTrue(receipt['github_download_sha256_confirmed'] and receipt['nexus_only_recovery'])
        self.assertFalse(receipt['group_accepted'])
        self.assertEqual(receipt['sha256'], self.config['sha256'])
        self.assertEqual(output.call_args.args[0]['nexus_ready'], 'true')
        self.no_put()

    def test_nexus_recovery_wrong_zip_or_checksum_blocks_before_nexus_preflight(self):
        for field in ['recovery_bad_zip', 'recovery_bad_checksum']:
            self.recovery_calls = []
            setattr(self, field, True)
            with self.subTest(field=field), patch.dict(os.environ, {'GITHUB_REPOSITORY': release.REPOSITORY, 'PUBLISH_NEXUS': 'true'}), patch.object(release, 'run', side_effect=self.recovery_command), patch.object(release, 'write_output') as output, self.assertRaisesRegex(ValueError, 'ZIP differs|checksum differs'):
                release.resume_nexus()
            output.assert_not_called()
            self.assertFalse(release.RECEIPT.exists())
            self.assertEqual(self.calls, [])
            setattr(self, field, False)

    def test_nexus_recovery_nonpublic_or_wrong_tag_blocks_before_download(self):
        original = {'tag_name': 'v0.1.0', 'draft': False, 'prerelease': False, 'html_url': 'https://example.test/existing'}
        for change in [{'tag_name': 'v0.2.0'}, {'draft': True}, {'prerelease': True}]:
            self.recovery_calls = []
            self.recovery_public = dict(original, **change)
            with self.subTest(change=change), patch.dict(os.environ, {'GITHUB_REPOSITORY': release.REPOSITORY, 'PUBLISH_NEXUS': 'true'}), patch.object(release, 'run', side_effect=self.recovery_command), self.assertRaisesRegex(ValueError, 'existing public GitHub release'):
                release.resume_nexus()
            self.assertEqual(len(self.recovery_calls), 1)
            self.assertEqual(self.calls, [])

    def test_nexus_recovery_existing_version_or_receipt_is_not_replayed(self):
        self.recovery_calls = []
        self.versions[-1]['version'] = '0.1.0'
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': release.REPOSITORY, 'PUBLISH_NEXUS': 'true'}), patch.object(release, 'run', side_effect=self.recovery_command), patch.object(release, 'write_output') as output, self.assertRaisesRegex(ValueError, 'no automatic overwrite'):
            release.resume_nexus()
        self.assertFalse(release.RECEIPT.exists())
        output.assert_not_called()
        release.RECEIPT.write_text('previous failed receipt')
        self.versions[-1]['version'] = 'old'
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': release.REPOSITORY, 'PUBLISH_NEXUS': 'true'}), patch.object(release, 'run', side_effect=self.recovery_command), self.assertRaisesRegex(ValueError, 'receipt already exists'):
            release.resume_nexus()
        self.assertEqual(release.RECEIPT.read_text(), 'previous failed receipt')
        self.no_put()

    def test_nexus_recovery_requires_explicit_nexus_upload(self):
        with patch.object(release, 'run') as command, self.assertRaisesRegex(ValueError, 'requires publish_nexus=true'):
            release.resume_nexus()
        command.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_nexus_recovery_cli_dispatch_is_separate_from_normal_release(self):
        with patch.object(sys, 'argv', ['nexus_release.py', 'nexus_only']), patch.object(release, 'resume_nexus') as recovery, patch.object(release, 'publish_github') as normal:
            release.main()
        recovery.assert_called_once_with()
        normal.assert_not_called()

if __name__ == "__main__":
    unittest.main()
