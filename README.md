# Rejoin

> 🛟 **Need help or found a bug?** Get support at [support.doodesch.de/rejoin](https://support.doodesch.de/rejoin).

Adds a **Rejoin** card to the main menu when a previous session is available. Flip it and select **Reconnect** to return to your round.

The round keeps running if the host's game crashes. The host's main menu opens again, and guests can restart through Steam. Reconnecting restores your cards, turn and room changes. You choose whether to return.

**Early development state.** Host crash and reconnect have been tested locally. A full four-player test and a real AMD driver-crash test are still pending. Bugs may occur.

Works with **Mod Settings**. Rejoin stays on the far left; the **Mods** card stays on the far right. Both cards keep their own actions.

## Requirements

- Windows and the Steam version of the cabin game.
- Supported Steam build: **25553694**.
- Everyone in the group should install the same Rejoin version.
- [UE4SS for the cabin game](https://www.nexusmods.com/thecabingame/mods/4), installed separately. Supported baseline: `v3.0.1-1164-g5e627997`.

## Install or update

1. Close the game and install [UE4SS for the cabin game](https://www.nexusmods.com/thecabingame/mods/4).
2. Copy both `CabinRejoin` and `CabinNativeProbe` from the ZIP's `Mods` folder into `the_cabin_game/Binaries/Win64/ue4ss/Mods`.
3. Copy the ZIP's `the_cabin_game/Content/Paks` files into the matching game folder. Keep each `.pak`, `.utoc` and `.ucas` set together, with the same subfolders.
4. Start the game normally through Steam.

Install the same Rejoin version on every player's PC. Both mod folders and both container sets are required.

## Reconnect

1. If a guest's client closes, start the game again through Steam. After a host-client crash, wait for the main menu to reopen.
2. Hover over the leftmost `Rejoin` card.
3. Select `Reconnect` on its reverse side.

The mod restores the retained player and round state. The camera and local viewing modes may return to the normal view. The menu card stays visible while the connection is being attempted.

## Known limits

**A complete four-player test and recovery from a real AMD driver crash are still pending.** Rejoin does not prevent driver crashes.

The background session lives on the host's PC. A PC shutdown or a crash of the background server loses the round. Full rounds are not saved to disk. The host's `Quit Game` also ends the round intentionally. Starting a new hosted session ends the host's old session.

Other mods that replace the main-menu cards or change player/session handling may conflict. Compatibility with mods other than Mod Settings has not been tested.

## Uninstall

1. End the hosted session with `Quit Game` and close the game.
2. In `the_cabin_game/Binaries/Win64/ue4ss/Mods/`, remove only `CabinRejoin` and `CabinNativeProbe`.
3. In `the_cabin_game/Content/Paks/`, remove `CabinRejoinBootstrap_P.pak`, `.utoc` and `.ucas`. In `Mods/CabinRejoinMenu/` under that folder, remove `CabinRejoinMenuV4_P.pak`, `.utoc` and `.ucas`.
4. If `ue4ss/Mods/mods.txt` contains entries for `CabinRejoin` or `CabinNativeProbe`, remove those entries.

If you installed UE4SS only for Rejoin and use no other UE4SS mods, you can also remove `dwmapi.dll` and the `ue4ss` folder from `the_cabin_game/Binaries/Win64/`. Keep them if other mods use them. Keep your game saves and the install-backup folder.

## Troubleshooting

If Rejoin does not load, check that UE4SS is installed and that both mod folders and all six container files are in their matching game folders.

For an in-game problem, include your Rejoin version, whether you hosted or joined, the action that failed and the visible result. Relevant logs are `the_cabin_game/Binaries/Win64/ue4ss/UE4SS.log` and `ue4ss/CabinRejoinAuthority/UE4SS.log`. Check logs before sharing them because they can contain local paths and Steam identifiers.

## Credits and license

Rejoin by **DooDesch**. Uses [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS). Mod containers are built with [retoc](https://github.com/trumank/retoc).

Rejoin's terms are in `LICENSE.md`. Third-party components retain their own licenses. The mod containers contain the modified menu and startup Blueprints; the game and UE4SS runtime are not included.
