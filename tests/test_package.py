"""Reject installer leftovers and broken manual-install paths in the sealed mod ZIP."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import package

class ManualPackageTests(unittest.TestCase):
    def changed_archive(self, change):
        source = ROOT / package.CONFIG['archive']
        with zipfile.ZipFile(source) as zipped:
            files = {name: zipped.read(name) for name in zipped.namelist()}
        manifest = json.loads(files.pop('README.manifest.json'))
        change(files, manifest)
        files['README.manifest.json'] = json.dumps(manifest).encode()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        archive = Path(directory.name) / 'changed.zip'
        with zipfile.ZipFile(archive, 'w') as zipped:
            for name, data in files.items():
                zipped.writestr(name, data)
        config = package.CONFIG | {'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
        return archive, config

    def test_normal_archive_has_direct_files_and_separate_loader(self):
        manifest = package.validate(ROOT / package.CONFIG['archive'])
        self.assertEqual(manifest['installation'], 'manual')
        self.assertFalse(manifest['bundled_runtime'])
        self.assertEqual(len(manifest['install_files']), 69)

    def test_installer_leftover_cannot_be_declared_as_an_archive_member(self):
        def change(files, manifest):
            files['Installieren.bat'] = b'old installer'
            manifest['files']['Installieren.bat'] = hashlib.sha256(files['Installieren.bat']).hexdigest()
        archive, config = self.changed_archive(change)
        with patch.object(package, 'CONFIG', config), self.assertRaisesRegex(ValueError, 'unexpected installer'):
            package.validate(archive)

    def test_missing_container_companion_is_rejected(self):
        def change(files, manifest):
            name = 'the_cabin_game/Content/Paks/CabinRejoinBootstrap_P.utoc'
            files.pop(name)
            manifest['files'].pop(name)
            manifest['install_files'] = [row for row in manifest['install_files'] if row['source'] != name]
        archive, config = self.changed_archive(change)
        with patch.object(package, 'CONFIG', config), self.assertRaisesRegex(ValueError, 'runtime inventory is missing'):
            package.validate(archive)

    def test_wrong_manual_copy_target_is_rejected(self):
        def change(files, manifest):
            manifest['install_files'][0]['target'] = 'wrong-folder/main.dll'
        archive, config = self.changed_archive(change)
        with patch.object(package, 'CONFIG', config), self.assertRaisesRegex(ValueError, 'manual copy target differs'):
            package.validate(archive)

    def test_changed_runtime_bytes_are_rejected(self):
        archive, config = self.changed_archive(lambda files, manifest: files.update({'Mods/CabinRejoin/Scripts/main.lua': b'changed'}))
        with patch.object(package, 'CONFIG', config), self.assertRaisesRegex(ValueError, 'ZIP member differs'):
            package.validate(archive)

if __name__ == '__main__':
    unittest.main()
