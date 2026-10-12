"""Validate and copy a sealed Rejoin artifact without changing its bytes."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile
ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
def validate(source):
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != CONFIG["sha256"]:
        raise ValueError(f"sealed candidate SHA256 differs; measured={actual}; required={CONFIG['sha256']}")
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise ValueError("sealed candidate CRC failed")
        manifest = json.loads(archive.read("manifest.json"))
        for item in manifest["install_files"]:
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
        if acceptance.get("accepted") is not True or acceptance.get("sha256") != CONFIG["sha256"] or manifest.get("runtime_accepted") is not True or manifest.get("delivery_accepted") is not True:
            raise ValueError("Rejoin game/delivery acceptance is pending; release blocked")
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
