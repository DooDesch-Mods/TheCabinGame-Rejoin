"""Validate the normal UE4SS mod archive and copy its sealed bytes."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile
ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
REQUIRED_OVERLAYS = {
    'the_cabin_game/Content/Paks/CabinRejoinBootstrap_P.pak': '75e7144577253917f6da7312ef5e585b12fb728226a22b0938323751a6b555cd',
    'the_cabin_game/Content/Paks/CabinRejoinBootstrap_P.ucas': 'ef8227b2bd2d086f822b3bce4ff335dffd6f19263e5bdc7525dc28462c3b1622',
    'the_cabin_game/Content/Paks/CabinRejoinBootstrap_P.utoc': '53959f1e6395c0a04dedcf46cbf5fb2bf9c734e1cda2fa955659532a07b43b09',
    'the_cabin_game/Content/Paks/Mods/CabinRejoinMenu/CabinRejoinMenuV4_P.pak': '75e7144577253917f6da7312ef5e585b12fb728226a22b0938323751a6b555cd',
    'the_cabin_game/Content/Paks/Mods/CabinRejoinMenu/CabinRejoinMenuV4_P.ucas': '196a8a7254716a693b08429f00ff2517b0a221f446e8a7a0529149c506196439',
    'the_cabin_game/Content/Paks/Mods/CabinRejoinMenu/CabinRejoinMenuV4_P.utoc': '2a0dfbbf631ac53aebd150f27b35e2762376830659cf66e232b5f6141fe448df',
}
DOCUMENTS = {'README.md', 'LICENSE.md', 'CHANGELOG.md'}

def allowed_payload(name):
    if name in REQUIRED_OVERLAYS:
        return True
    if name in {'Mods/CabinNativeProbe/enabled.txt', 'Mods/CabinNativeProbe/dlls/main.dll',
                'Mods/CabinRejoin/enabled.txt', 'Mods/CabinRejoin/LICENSE.md'}:
        return True
    return name.startswith('Mods/CabinRejoin/Scripts/') and name.endswith('.lua') and '/' not in name[len('Mods/CabinRejoin/Scripts/'):]

def validate(source):
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != CONFIG["sha256"]:
        raise ValueError(f"sealed candidate SHA256 differs; measured={actual}; required={CONFIG['sha256']}")
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise ValueError("sealed candidate CRC failed")
        names = archive.namelist()
        if len(names) != len(set(names)) or 'README.manifest.json' not in names:
            raise ValueError('normal mod manifest is missing or ZIP has duplicate entries')
        manifest = json.loads(archive.read('README.manifest.json'))
        if manifest.get('version') != CONFIG['version'] or manifest.get('installation') != 'manual' or manifest.get('bundled_runtime') is not False:
            raise ValueError('normal mod identity/layout or separate UE4SS requirement differs')
        expected = manifest['files']
        if set(names) != set(expected) | {'README.manifest.json'}:
            raise ValueError('normal mod ZIP inventory differs')
        for name, digest in expected.items():
            if name not in DOCUMENTS and not allowed_payload(name):
                raise ValueError('unexpected installer, loader or runtime file: ' + name)
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError('normal mod ZIP member differs: ' + name)
        if not DOCUMENTS <= set(names):
            raise ValueError('normal mod documentation/license is missing')
        for item in manifest["install_files"]:
            name = item['source']
            target = ('the_cabin_game/Binaries/Win64/ue4ss/' + name) if name.startswith('Mods/') else name
            if not allowed_payload(name) or item['target'] != target:
                raise ValueError('manual copy target differs: ' + name)
            if hashlib.sha256(archive.read(item["source"])).hexdigest() != item["sha256"]:
                raise ValueError("sealed install payload differs: " + item["source"])
        installed = {item['source'] for item in manifest['install_files']}
        required = {'Mods/CabinRejoin/Scripts/main.lua', 'Mods/CabinRejoin/enabled.txt',
                    'Mods/CabinNativeProbe/dlls/main.dll', 'Mods/CabinNativeProbe/enabled.txt'} | set(REQUIRED_OVERLAYS)
        if not required <= installed or installed != set(expected) - DOCUMENTS or len(installed) != len(manifest['install_files']):
            raise ValueError('normal mod runtime inventory is missing or repeated')
        for name, digest in REQUIRED_OVERLAYS.items():
            if expected.get(name) != digest:
                raise ValueError('tested overlay binding differs: ' + name)
        return manifest
def build(release=False):
    source = ROOT / CONFIG["archive"]
    manifest = validate(source)
    if release:
        acceptance = json.loads((ROOT / "acceptance.json").read_text(encoding="utf-8"))
        preparation_path = ROOT / "release-preparation.json"
        preparation = json.loads(preparation_path.read_text(encoding="utf-8")) if preparation_path.is_file() else {}
        with zipfile.ZipFile(source) as archive:
            readme = archive.read("README.md")
        accepted = acceptance.get("accepted") is True and acceptance.get("sha256") == CONFIG["sha256"]
        prepared = (preparation.get("status") == "prepared" and preparation.get("sha256") == CONFIG["sha256"]
                    and preparation.get("version") == CONFIG["version"] and manifest.get("release_prepared") is True
                    and preparation.get("group_validation") == manifest.get("group_validation") == "not_measured"
                    and b"A full four-player test and a real AMD driver-crash test are still pending." in readme
                    and b"early development state" in readme.lower())
        if not (accepted or prepared) or manifest.get("runtime_accepted") is not True or manifest.get("delivery_accepted") is not True:
            raise ValueError("Rejoin runtime/delivery proof or declared release preparation is missing")
    output = ROOT / "dist" / (CONFIG["mod"] + "-" + CONFIG["version"] + ("" if release else "-candidate") + ".zip")
    output.parent.mkdir(exist_ok=True)
    shutil.copyfile(source, output)
    return output
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    archive = build(args.release)
    print("info: sealed Rejoin archive validated and copied: " + str(archive))
