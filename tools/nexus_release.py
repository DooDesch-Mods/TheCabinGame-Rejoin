"""Publish declared early Rejoin releases and preserve Nexus file requirements."""
from decimal import Decimal, InvalidOperation
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

import package
from nexus_draft import api, ranges, require, write_output

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "dist/nexus-release.json"
REPOSITORY = "DooDesch-Mods/TheCabinGame-Rejoin"

def release_archive():
    config = package.CONFIG
    require(re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", config["version"]), "Rejoin release version is not SemVer")
    archive = ROOT / "dist" / f"{config['mod']}-{config['version']}.zip"
    manifest = package.validate(archive)
    acceptance = json.loads((ROOT / "acceptance.json").read_text(encoding="utf-8"))
    preparation = json.loads((ROOT / "release-preparation.json").read_text(encoding="utf-8"))
    require(preparation.get("publication_authorized") is True, "Rejoin publication authorization is missing")
    accepted = acceptance.get("accepted") is True and acceptance.get("sha256") == config["sha256"]
    with zipfile.ZipFile(archive) as zipped:
        readme = zipped.read("README.md")
    prepared = (preparation.get("status") == "prepared" and preparation.get("sha256") == config["sha256"]
                and preparation.get("version") == config["version"] and manifest.get("release_prepared") is True
                and preparation.get("group_validation") == manifest.get("group_validation") == "not_measured"
                and b"A complete test with four different Steam accounts has not yet been performed." in readme)
    require((accepted or prepared) and manifest.get("runtime_accepted") is True and manifest.get("delivery_accepted") is True,
            "Rejoin runtime/delivery proof or declared release preparation is missing")
    require(b"early development state" in readme.lower(), "Rejoin early development state disclosure is missing")
    return archive

def identity():
    target = {"uid": os.environ.get("NEXUS_MOD_ID", ""), "file": os.environ.get("NEXUS_FILE_GROUP_ID", "")}
    require(all(value.isascii() and value.isdecimal() and int(value) > 0 for value in target.values()), "release Nexus target IDs are missing or invalid")
    return target

def parent(target):
    rows = api("POST", "/mods/batch", {"mod_ids": [target["uid"]]})["mods"]
    require(len(rows) == 1 and str(rows[0].get("id")) == target["uid"], "release Nexus parent UID is unconfirmed")
    require(str(rows[0].get("game_id")) == "10562", "release Nexus game differs from The Cabin Game")
    require(rows[0].get("status") in {"published", "not_published"}, "release Nexus parent must be published or not_published")
    files = api("GET", f"/mods/{target['uid']}/files")["mod_files"]
    require(sum(str(row.get("id")) == target["file"] for row in files) == 1, "release Nexus file group does not belong to the configured mod")
    return rows[0]

def latest_main(target):
    versions = api("GET", f"/mod-files/{target['file']}/versions")["versions"]
    active = [row for row in versions if row.get("category") == "main"]
    require(bool(active), "release Nexus file has no Main version")
    require(all(str(row.get("file", {}).get("id")) == target["file"] for row in active), "release Nexus Main version belongs to another file group")
    try:
        positions = [Decimal(row["position"]) for row in active]
        require(all(value.is_finite() for value in positions), "release Nexus Main position is not finite")
        latest = [row for row, position in zip(active, positions) if position == max(positions)]
    except (InvalidOperation, KeyError, TypeError, ValueError) as cause:
        raise ValueError("release Nexus Main position is invalid") from cause
    require(len(latest) == 1, "release Nexus latest Main version is ambiguous")
    return latest[0], versions

def save(receipt):
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

def read_ranges(version_id, allow_missing=False):
    definitions = api("GET", f"/mod-file-versions/{version_id}/dependencies/ranges")["dependency_definitions"]
    bundled = package.CONFIG.get("bundled_runtime") is True
    if allow_missing and not definitions and not bundled:
        return None
    try:
        return ranges(definitions, allow_empty=bundled)
    except (ValueError, KeyError, TypeError) as cause:
        raise ValueError(f"release Nexus requirements version={version_id}: {cause}") from cause

def require_no_dlc(version_id):
    dlc = api("GET", f"/mod-file-versions/{version_id}/dependencies/dlc")["dlc_dependency_definitions"]
    require(not dlc, "release Nexus DLC dependencies need an explicit supported mapping")

def preflight(archive, version):
    require(archive.resolve() == release_archive().resolve() and version == package.CONFIG["version"], "release Nexus archive/version differs from the prepared package")
    require(not RECEIPT.exists(), "release Nexus preflight receipt already exists; inspect current state before retry")
    target = identity()
    current_parent = parent(target)
    previous, versions = latest_main(target)
    require(not any(row.get("version") == version for row in versions), "release Nexus version already exists; no automatic overwrite or upload replay")
    previous_id = str(previous.get("id", ""))
    require(previous_id.isascii() and previous_id.isdecimal() and int(previous_id) > 0, "release Nexus previous Main version ID is invalid")
    dependencies = read_ranges(previous_id)
    require_no_dlc(previous_id)
    acceptance = json.loads((ROOT / "acceptance.json").read_text(encoding="utf-8"))
    receipt = {"identity": target, "archive": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
               "version": version, "previous_version_id": previous_id, "dependencies": dependencies,
               "status": current_parent["status"], "release_prepared": True, "group_accepted": acceptance.get("accepted") is True and acceptance.get("sha256") == package.CONFIG["sha256"],
               "requirements_confirmed": False, "requirements_copy_attempted": False, "remote_archive_sha256_confirmed": False}
    save(receipt)
    print(f"info: release Nexus preflight confirmed mod={target['uid']} file_group={target['file']}; Main requirements captured")
    return receipt

def verify():
    target = identity()
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(receipt["identity"] == target, "release Nexus identity changed after preflight")
    require(receipt.get("release_prepared") is True and receipt["version"] == package.CONFIG["version"], "release Nexus receipt is not for the prepared current release")
    archive = release_archive()
    require(str(archive) == receipt["archive"] and hashlib.sha256(archive.read_bytes()).hexdigest() == receipt["sha256"], "release Nexus ZIP changed after preflight")
    uploaded_id = os.environ.get("NEXUS_VERSION_ID", "")
    require(uploaded_id.isascii() and uploaded_id.isdecimal() and int(uploaded_id) > 0, "release Nexus upload returned no valid version acknowledgement; inspect Nexus before retry")
    require(uploaded_id != receipt["previous_version_id"], "release Nexus acknowledgement names the previous version")
    parent(target)
    latest, versions = latest_main(target)
    matches = [row for row in versions if str(row.get("id")) == uploaded_id]
    require(len(matches) == 1, "release Nexus acknowledged version is unconfirmed")
    uploaded = matches[0]
    require(uploaded.get("version") == receipt["version"] and uploaded.get("category") == "main"
            and str(uploaded.get("file", {}).get("id")) == target["file"], "release Nexus acknowledged version/file/category differs")
    require(str(latest["id"]) == uploaded_id, "release Nexus acknowledgement is not the latest Main version")
    require_no_dlc(receipt["previous_version_id"])
    require_no_dlc(uploaded_id)
    source = read_ranges(receipt["previous_version_id"])
    require(source == receipt["dependencies"], "release Nexus previous requirements changed after preflight")
    actual = read_ranges(uploaded_id, allow_missing=True)
    if receipt["requirements_confirmed"]:
        require(str(receipt["confirmed_version_id"]) == uploaded_id and actual == receipt["dependencies"], "release Nexus confirmed requirements/version changed; no automatic overwrite")
    elif actual != receipt["dependencies"]:
        require(not receipt["requirements_copy_attempted"], "release Nexus requirements PUT was already attempted; inspect Nexus before retry")
        receipt["requirements_copy_attempted"] = True
        save(receipt)
        api("PUT", f"/mod-file-versions/{uploaded_id}/dependencies/ranges", receipt["dependencies"])
        actual = read_ranges(uploaded_id)
    require(actual == receipt["dependencies"], "release Nexus file-to-file requirements readback differs")
    current_parent = parent(target)
    receipt.update(confirmed_version_id=uploaded_id, requirements_confirmed=True, parent_identity_confirmed=True, status=current_parent["status"])
    save(receipt)
    print(f"info: release Nexus version={uploaded_id} confirmed; file-to-file requirements read back; remote ZIP hash unmeasured")
    return receipt

def run(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(args[:3])} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout

def require_tag_target(repository, tag, commit):
    refs = json.loads(run("gh", "api", f"repos/{repository}/git/matching-refs/tags/{tag}"))
    if any(ref["ref"] == "refs/tags/" + tag for ref in refs):
        actual = json.loads(run("gh", "api", f"repos/{repository}/commits/{tag}"))["sha"]
        require(actual == commit, f"existing tag {tag} targets {actual}; required={commit}")

def publish_github():
    archive = release_archive()
    repository = os.environ["GITHUB_REPOSITORY"]
    require(repository == REPOSITORY, "Rejoin GitHub repository differs")
    version = package.CONFIG["version"]
    tag = "v" + version
    require_tag_target(repository, tag, os.environ["GITHUB_SHA"])
    nexus = os.environ.get("PUBLISH_NEXUS") == "true"
    if nexus:
        preflight(archive, version)
    checksum = f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}"
    sums = archive.parent / "SHA256SUMS.txt"
    sums.write_text(checksum + "\n", encoding="utf-8")
    pages = json.loads(run("gh", "api", f"repos/{repository}/releases", "--paginate", "--slurp"))
    existing = next((release for page in pages for release in page if release["tag_name"] == tag), None)
    if existing is None:
        run("gh", "release", "create", tag, str(archive), str(sums), "--repo", repository,
            "--target", os.environ["GITHUB_SHA"], "--title", f"Rejoin {version}", "--notes-file", str(ROOT / "README.md"))
    else:
        require(not existing["draft"] and not existing["prerelease"], "existing release is draft/prerelease; no automatic overwrite")
    published = json.loads(run("gh", "api", f"repos/{repository}/releases/tags/{tag}"))
    require(not published["draft"] and not published["prerelease"], "GitHub published release is unconfirmed")
    actual = json.loads(run("gh", "api", f"repos/{repository}/commits/{tag}"))["sha"]
    require(actual == os.environ["GITHUB_SHA"], "GitHub release tag commit differs")
    with tempfile.TemporaryDirectory() as folder:
        run("gh", "release", "download", tag, "--repo", repository, "--pattern", archive.name, "--pattern", sums.name, "--dir", folder)
        downloaded = Path(folder) / archive.name
        package.validate(downloaded)
        require(hashlib.sha256(downloaded.read_bytes()).hexdigest() == hashlib.sha256(archive.read_bytes()).hexdigest(), "GitHub downloaded release ZIP differs")
        require((Path(folder) / sums.name).read_text().strip() == checksum, "GitHub downloaded release checksum differs")
    write_output({"version": version, "asset": archive, "display_name": f"Rejoin {version}", "nexus_ready": str(nexus).lower(), "release_url": published["html_url"]})
    print(f"info: GitHub release tag, downloaded ZIP and checksum confirmed: {published['html_url']}")

def resume_nexus():
    require(os.environ.get("PUBLISH_NEXUS") == "true", "Nexus-only recovery requires publish_nexus=true")
    archive = release_archive()
    repository = os.environ["GITHUB_REPOSITORY"]
    require(repository == REPOSITORY, "Rejoin GitHub repository differs")
    version = package.CONFIG["version"]
    tag = "v" + version
    published = json.loads(run("gh", "api", f"repos/{repository}/releases/tags/{tag}"))
    require(published.get("tag_name") == tag and published.get("draft") is False and published.get("prerelease") is False,
            "Nexus recovery requires the exact existing public GitHub release")
    tag_commit = json.loads(run("gh", "api", f"repos/{repository}/commits/{tag}"))["sha"]
    require(bool(tag_commit), "Existing GitHub release tag commit is unconfirmed")
    checksum = f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}"
    with tempfile.TemporaryDirectory() as folder:
        run("gh", "release", "download", tag, "--repo", repository, "--pattern", archive.name,
            "--pattern", "SHA256SUMS.txt", "--dir", folder)
        downloaded = Path(folder) / archive.name
        package.validate(downloaded)
        require(hashlib.sha256(downloaded.read_bytes()).hexdigest() == hashlib.sha256(archive.read_bytes()).hexdigest(),
                "Nexus recovery downloaded GitHub ZIP differs")
        require((Path(folder) / "SHA256SUMS.txt").read_text().strip() == checksum, "Nexus recovery GitHub checksum differs")
    receipt = preflight(archive, version)
    receipt.update(nexus_only_recovery=True, github_release_tag=tag, github_release_tag_commit=tag_commit,
                   github_release_url=published["html_url"], github_download_sha256_confirmed=True)
    save(receipt)
    (archive.parent / "SHA256SUMS.txt").write_text(checksum + "\n", encoding="utf-8")
    write_output({"version": version, "asset": archive, "display_name": f"Rejoin {version}",
                  "nexus_ready": "true", "release_url": published["html_url"]})
    print(f"info: Nexus-only recovery confirmed existing GitHub tag={tag} commit={tag_commit}; ZIP/checksum exact; GitHub unchanged")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["preflight", "verify", "github", "nexus_only"])
    phase = parser.parse_args().phase
    if phase == "preflight":
        archive = release_archive()
        preflight(archive, package.CONFIG["version"])
    elif phase == "verify":
        verify()
    elif phase == "nexus_only":
        resume_nexus()
    else:
        publish_github()

if __name__ == "__main__":
    try:
        main()
    except Exception as cause:
        raise SystemExit(f"error: Rejoin release: {cause}") from cause
