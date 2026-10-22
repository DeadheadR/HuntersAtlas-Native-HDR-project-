# Compatibility

Windows 10/11 x64. Verified game: CUSA00207 1.09.
Included Windows runtime: 1.9. A separate launcher installation is not required.

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
