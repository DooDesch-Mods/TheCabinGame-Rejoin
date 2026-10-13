# Rejoin publishing

Rejoin is in an **early development state**. Local host crash, automatic main menu and manual Rejoin have measured evidence. A complete test with four different Steam accounts has not yet been performed. Publication is authorized independently from that unmeasured group acceptance; `acceptance.json` stays false until the actual complete group test passes.

The release uses the exact sealed ZIP configured in `package.json`, not a rebuilt game payload. `tools/package.py --release` retains the six exact locally generated asset bindings and all bundled-runtime/license checks. The matching `release-preparation.json` must declare `status=prepared`, the version and ZIP SHA, `group_validation=not_measured` and `publication_authorized=true`. The ZIP must carry the real local runtime/delivery evidence, release-prepared marker and both early-development and four-account disclosures. These fields do not establish group acceptance.

`nexus-release.yml` tests on Windows and Linux for pushes and pull requests. Publishing runs only on `workflow_dispatch`. It validates the release, binds the tag to the workflow commit, publishes or reuses an exact GitHub release and downloads its ZIP/checksum for readback. Enable `publish_nexus` to update the existing Nexus Main File. A mismatched Nexus parent or file group blocks before GitHub release mutation. The repository is pinned to `DooDesch-Mods/TheCabinGame-Rejoin`.

## Repository configuration

| Variable or secret | Required binding |
|---|---|
| `vars.NEXUS_MOD_ID` | Unique Mod ID `45363444580354` |
| `vars.NEXUS_FILE_GROUP_ID` | Existing API File ID `8139033` |
| `vars.NEXUS_GAME_SCOPED_ID` | Page ID `2`, used by the manual unpublished draft workflow |
| `secrets.NEXUSMODS_API_KEY` | Existing organization secret; never print or commit its value |
| `github.token` | Automatic workflow token with release-job `contents: write` permission |

The API confirms the parent UID, The Cabin Game ID and file-group ownership. The release updater allows `published` and `not_published`; the draft workflow still accepts only `not_published`. API description updates do not publish an initial mod page. Initial page publication remains a separate actual Nexus action after the prepared file and description exist.

Both workflows share one Nexus concurrency group. The draft workflow is manual only; it cannot upload on a push. Later published releases use the release workflow. The release updater rejects an existing version or retained preflight receipt to block automatic upload replay. After a timed-out or failed upload inspect Nexus and the saved receipt before starting another job.

With `upload=true`, the manual draft workflow runs `tools/nexus_page.py --execute` before initial upload. With `upload=false`, it never mutates page text. Its build selects the public archive and plain SemVer when the exact hash/version-bound preparation declares publication authorization and early development; `accepted=false` remains unchanged. After staging `0.1.0` on an unpublished page, use `publish_nexus=false` for the first matching GitHub release. The release updater refuses a second Nexus upload of the same version; later file updates need a new SemVer.

The release workflow also updates the configured Nexus description with the same helper, only when `publish_nexus=true` and the exact parent/file preflight succeeds. Both page-update paths use the existing organization key and scoped page variable; a GitHub-only release performs no Nexus page mutation.

The acknowledged upload must be the exact new latest Main version with the configured file ID and declared version. Existing file-to-file dependency ranges are copied and read back. An empty list is permitted only because Rejoin bundles UE4SS. Nonempty requirements retain their exact range/file guards. DLC dependencies block pending a supported mapping. A failed requirements PUT is recorded before the request and is not blindly repeated. The receipt explicitly leaves remote Nexus ZIP SHA confirmation unmeasured; API version acknowledgement is not a remote byte-hash claim.

Vortex downloads stay disabled because this distribution uses `Installieren.bat` and has no actual Nexus/Vortex deployment proof. No Discord notification or Sentry integration is enabled. The workflow does not send messages or change gameplay.

Local checks: `python -m unittest discover -s tests -v`. Workflow files and API effects are covered with YAML inspection, temporary fixtures and mocked HTTP/GitHub commands. Actual hosted CI and Nexus publication remain separate evidence.
