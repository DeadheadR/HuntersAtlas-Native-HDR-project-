# Hunter's Atlas 3.0

[Download the Windows ZIP](https://github.com/MikeTat1988/HuntersAtlas/releases/download/v3.0/Hunters-Atlas-3.0-Windows.zip)

All 16 supported areas and 602 floors are already baked into compact vector data.
No map generation, compiler, map download or separately installed launcher is needed.
Atlas includes its own tested Windows runtime, Python and required DLLs.

## Install and play

1. Close the game and launcher. Extract the whole ZIP into a new permanent folder.
2. Run **Install.cmd**. Select your Bloodborne **CUSA00207 1.09** game folder if asked.
3. Open **HuntersAtlas.exe**. Hunter's Atlas is enabled under **Mods & patches**.
4. Press **Play**, then **Continue** in the game. Press **M** to open the map.

Game files and saves are not included. Keep your existing save folder and select it
in the launcher if it was not detected automatically. Installation does not change
your game files. Extract updates to a new folder and run that folder's Install.cmd.

## Mouse and display

For faster camera turning: **Inputs → Mouse look → Sensitivity**, then **Save**.
The default is 1.0; try 2.0 and adjust to taste. Mouse-look emulates the right
stick, so Bloodborne's maximum stick turn speed still applies.

The map scales proportionally to the display and keeps its world coverage when
the window is resized. Ultrawide and taller screens use a centered layout without
stretching. Mouse-wheel, keyboard and controller zoom use matching scaled limits.

## What's new

- All map shapes, outlines and decorative geometry are compiled once offline.
- The game loads compact map data and draws it directly; no collision extraction
  or map triangulation runs while playing.
- Correct area names, live position, floors, pan/zoom and discovered-lamp travel.
- Works independently of the version of any separately installed launcher.

Renderer checks covered 720p, 1080p, 1440p, 4K, 1920×1200, 3440×1440 and
5120×1440, plus resizing and zoom. These are offscreen renderer checks; every
resolution has not been tested through a live game's display mode switch.
