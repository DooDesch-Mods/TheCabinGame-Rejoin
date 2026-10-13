"""Validate and copy a sealed Rejoin artifact without changing its bytes."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile
ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
LOCALLY_GENERATED_SOURCES = {'Payload/the_cabin_game/Content/Paks/CabinRejoinBootstrap_P.pak': '75e7144577253917f6da7312ef5e585b12fb728226a22b0938323751a6b555cd', 'Payload/the_cabin_game/Content/Paks/CabinRejoinBootstrap_P.ucas': 'ef8227b2bd2d086f822b3bce4ff335dffd6f19263e5bdc7525dc28462c3b1622', 'Payload/the_cabin_game/Content/Paks/CabinRejoinBootstrap_P.utoc': '53959f1e6395c0a04dedcf46cbf5fb2bf9c734e1cda2fa955659532a07b43b09', 'Payload/the_cabin_game/Content/Paks/Mods/CabinRejoinMenu/CabinRejoinMenuV4_P.pak': '75e7144577253917f6da7312ef5e585b12fb728226a22b0938323751a6b555cd', 'Payload/the_cabin_game/Content/Paks/Mods/CabinRejoinMenu/CabinRejoinMenuV4_P.ucas': '196a8a7254716a693b08429f00ff2517b0a221f446e8a7a0529149c506196439', 'Payload/the_cabin_game/Content/Paks/Mods/CabinRejoinMenu/CabinRejoinMenuV4_P.utoc': '2a0dfbbf631ac53aebd150f27b35e2762376830659cf66e232b5f6141fe448df'}
def validate(source):
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != CONFIG["sha256"]:
        raise ValueError(f"sealed candidate SHA256 differs; measured={actual}; required={CONFIG['sha256']}")
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise ValueError("sealed candidate CRC failed")
        manifest = json.loads(archive.read("manifest.json"))
        for item in manifest["install_files"]:
            if item["source"] in LOCALLY_GENERATED_SOURCES:
                if item["sha256"] != LOCALLY_GENERATED_SOURCES[item["source"]] or item["source"] in archive.namelist():
                    raise ValueError("local generated container binding differs: " + item["source"])
                continue
            if hashlib.sha256(archive.read(item["source"])).hexdigest() != item["sha256"]:
                raise ValueError("sealed install payload differs: " + item["source"])
        required = ("LICENSE.md", "Payload/the_cabin_game/Binaries/Win64/ue4ss/UE4SS.dll", "Payload/the_cabin_game/Binaries/Win64/ue4ss/LICENSE")
        if not all(name in archive.namelist() for name in required):
            raise ValueError("bundled runtime or licenses are missing")
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
                    and b"A complete test with four different Steam accounts has not yet been performed." in readme)
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
