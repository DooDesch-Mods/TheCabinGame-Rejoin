# Rejoin publishing

Rejoin is in an **early development state**. Local host crash, automatic main menu and manual Rejoin have measured evidence. A complete test with four different Steam accounts has not yet been performed. Publication is authorized independently from that unmeasured group acceptance; `acceptance.json` stays false until the actual complete group test passes.

The release uses the exact sealed ZIP configured in `package.json`. Version 0.1.1 ships the two mod folders at `Mods/` and the six finished mod container files at their existing game-relative paths. It contains no installer, asset recipes, game executable or UE4SS runtime. The separate game-specific UE4SS Basic build matches the previously tested loader bytes. `tools/package.py --release` validates every included file and manual copy target, the six exact accepted overlay bindings and licenses. The matching `release-preparation.json` must declare `status=prepared`, version/ZIP SHA, `group_validation=not_measured` and `publication_authorized=true`. Local runtime and manual layout evidence remain separate from the unmeasured four-player acceptance.

`nexus-release.yml` tests on Windows and Linux for pushes and pull requests. Publishing runs only on `workflow_dispatch`. It validates the release, binds the tag to the workflow commit, publishes or reuses an exact GitHub release and downloads its ZIP/checksum for readback. Enable `publish_nexus` to update the existing Nexus Main File. A mismatched Nexus parent or file group blocks before GitHub release mutation. The repository is pinned to `DooDesch-Mods/TheCabinGame-Rejoin`.

Use `resume_nexus=true` together with `publish_nexus=true` only when a retained failed run proves that its Nexus upload never executed. This route downloads and checks the existing GitHub release without changing its tag or files. It still rejects an already uploaded Nexus version. Inspect the failed step and saved receipts before resuming; a green GitHub release alone is not evidence that Nexus upload did not execute.

## Repository configuration

| Variable or secret | Required binding |
|---|---|
| `vars.NEXUS_MOD_ID` | Unique Mod ID `45363444580354` |
| `vars.NEXUS_FILE_GROUP_ID` | Existing API File ID `8139033` |
| `vars.NEXUS_GAME_SCOPED_ID` | Page ID `2`, used by both description-update workflows |
| `secrets.NEXUSMODS_API_KEY` | Existing organization secret; never print or commit its value |
| `github.token` | Automatic workflow token with release-job `contents: write` permission |

The API confirms the parent UID, The Cabin Game ID and file-group ownership. The release updater allows `published` and `not_published`; the draft workflow still accepts only `not_published`. API description updates do not publish an initial mod page. Initial page publication remains a separate actual Nexus action after the prepared file and description exist.

Both workflows share one Nexus concurrency group. The draft workflow is manual only; it cannot upload on a push. Later published releases use the release workflow. The release updater rejects an existing version or retained preflight receipt to block automatic upload replay. After a timed-out or failed upload inspect Nexus and the saved receipt before starting another job.

With `upload=true`, the manual draft workflow runs `tools/nexus_page.py --execute` before initial upload. With `upload=false`, it never mutates page text. Its build selects the public archive and plain SemVer when the exact hash/version-bound preparation declares publication authorization and early development; `accepted=false` remains unchanged. After staging `0.1.0` on an unpublished page, use `publish_nexus=false` for the first matching GitHub release. The release updater refuses a second Nexus upload of the same version; later file updates need a new SemVer.

The release workflow also updates the configured Nexus description with the same helper, only when `publish_nexus=true` and the exact parent/file preflight succeeds. Both page-update paths use the existing organization key and scoped page variable; a GitHub-only release performs no Nexus page mutation.

For description edits after a file upload, use the manual `nexus-page.yml` workflow. It changes page text only and retains `nexus-page.json`; it does not upload files or change a release tag. The default is read-only. Set `execute=true` for the authorized edit. Its explicit unpublished-text replacement mode records a PATCH acknowledgment separately from full text readback. Inspect the retained receipt before retrying an unknown or failed write.

Description readback uses the v1 full-text endpoint; the v3 game-scoped endpoint returns identity only. For the unpublished first page, v1 omitted full text. `docs/nexus-page-ack.json` retains the latest successful text-only PATCH acknowledgment with its source run, commit and exact description hash. The helper can adopt this acknowledgment only while the page is unpublished and the desired hash still matches. It reports that full text readback is unconfirmed and does not replay the write. A published page requires full text readback. This acknowledgment does not prove initial page publication.

The acknowledged upload must be the exact new latest Main version with the configured file ID and declared version. Existing file-to-file dependency ranges are retained. Version 0.1.1 adds the separately published game-specific UE4SS Basic build as a requirement. The previously confirmed bundled 0.1.0 version is the only permitted empty-source migration; the receipt binds old and desired requirements separately. The helper resolves and verifies Nexus page 4, its file group and the exact loader build before publication and after upload. DLC dependencies block pending a supported mapping. A failed requirements PUT is recorded before the request and is not blindly repeated. The receipt leaves remote Nexus ZIP SHA confirmation unmeasured; API version acknowledgement is not a remote byte-hash claim.

Vortex downloads stay disabled until an actual Nexus/Vortex deployment passes. The normal archive is installed manually in the same layout as the other Cabin mods. No Discord notification or Sentry integration is enabled. The workflow does not send messages or change gameplay.

Local checks: `python -m unittest discover -s tests -v`. Workflow files and API effects are covered with YAML inspection, temporary fixtures and mocked HTTP/GitHub commands. Actual hosted CI and Nexus publication remain separate evidence.
