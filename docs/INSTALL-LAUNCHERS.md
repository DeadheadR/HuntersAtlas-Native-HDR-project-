# Installing Hunter's Atlas 3.1

Choose the edition you want:

| Download | Included launcher/runtime |
| --- | --- |
| `Hunters-Atlas-3.1-Windows.zip` | Bloodborne for Windows v1.9 (Supermedo) |
| `Hunters-Atlas-3.1-Lantern.zip` | Modified Atlas edition based on Awakenchan's Lantern Engine v0.9.37 |

Each ZIP contains a complete Atlas edition. Keep each edition in its own folder.
Your existing installation can stay in place.

## First installation

1. Close the game and launchers.
2. Extract the **entire ZIP** into a new, permanent folder. Use separate folders
   for the Windows and Lantern editions, such as `HuntersAtlas-Windows` and
   `HuntersAtlas-Lantern`.
3. Open the extracted folder and run **Install.cmd**.
4. Select your **CUSA00207 Bloodborne 1.09 game folder**, containing `eboot.bin`.
   Choose your dumped DLC folder too if you use The Old Hunters. Game files and
   DLC are supplied separately by the player.
5. Check the **save folder** before playing. Select the parent folder that
   contains `savedata`, rather than `savedata` itself or an individual save file.
   Select the same save folder used by your working installation to keep your
   progress. Keep a backup of that folder before your first session.
6. Enable Atlas:
   - **Windows edition:** **Mods & patches → Hunter's Atlas**.
   - **Lantern edition:** **Settings → Hunter's Atlas 3.1 → Enable Hunter's Atlas**.
     You should see the **Hunter's Atlas 3.1** section and its enabled toggle.
     Atlas is integrated into this edition's runtime, so a separate Atlas entry
     in Lantern's ordinary **Mods** list is not required.
7. Press **Play**, then **Continue**. Open the in-game menu and choose its **Map**
   tile, or press **M** to toggle the map. The map background, live player marker,
   legend and navigation controls should appear together.

For map travel, open the map from the in-game menu, choose an eligible discovered
lamp, and confirm **Travel**. Locked destinations remain unavailable. Map travel
can be disabled independently in the launcher.

## Installing an update

Extract the complete matching Atlas ZIP into a new folder, run **Install.cmd**,
and select the same game and save folders. Keep the previous edition until the
new one has loaded your character successfully. Launcher preferences belong to
each extracted edition and may need to be set again.

Keep the two ZIPs separate when updating. The Lantern edition protects its Atlas
runtime from stock engine replacement; use a complete Atlas update for it.
The game, saves, shader caches and personal launcher profiles are not included
in either download.

## If the game does not start or Continue is missing

- Recheck the selected game and save folders first. This adapter supports the
  verified CUSA00207 1.09 executable; another region/version is refused.
- Keep your existing saves intact and correct the folder selection. A save file
  does not need conversion merely to switch between these two editions.
- Extract a fresh complete copy if a runtime integrity check reports changed or
  mixed files.

Lantern Engine by Awaken (https://github.com/Awakenchan/LanternEngine).
The Lantern download is modified for Hunter's Atlas and is not an official
Lantern Engine release.
