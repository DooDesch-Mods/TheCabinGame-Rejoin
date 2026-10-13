# Changelog

## 0.1.1 - 2026-10-13

- Use the same manual installation layout as the other Cabin mods.
- Include the finished mod containers directly in the download.
- Require the separate UE4SS download.
- Remove the test installer, BAT, asset recipes and bundled loader from the release archive.
- Keep the previously tested gameplay and mod container bytes unchanged.

## 0.1.0 - 2026-10-13

First release, using the tested V21 mod files.

- Add a manual `Rejoin` card to the left of the main menu, with a `Reconnect` entry on the reverse side.
- Keep the hosted session in a background process when the host's game client closes unexpectedly.
- Reopen the host's main menu after a client crash and let the player choose whether to reconnect.
- Restore the retained player, cards, turn and room state on reconnect.
- Keep the reconnect card visible until the menu is left and restore normal hover behavior for the other cards.
- Correct room restoration for removed furniture and individual heater components, including the cellar.
- End the host's old session when `Quit Game` or a new hosted session is chosen.
- Bundle UE4SS and install into the existing Steam game through one `Installieren.bat`.

Validated locally on Steam build 25553694. A full four-account group test and an actual AMD driver-crash test remain outstanding.
