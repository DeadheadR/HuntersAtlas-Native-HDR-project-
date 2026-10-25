# Hunter's Atlas 3.1

[Download the Windows ZIP](https://github.com/MikeTat1988/HuntersAtlas/releases/download/v3.1/Hunters-Atlas-3.1-Windows.zip)

All 16 supported areas are precompiled and included. Continuous paths use
game-authored navigation geometry, with illustrated surroundings, a separate
legend and player-height focus for overlapping passages. No map generation,
compiler or separately installed launcher is needed to play. Atlas includes its
own Windows runtime, Python and required DLLs.

## Install and play

1. Close the game and launcher. Extract the whole Windows ZIP into a new permanent folder.
2. Run **Install.cmd**. Select your **CUSA00207 Bloodborne 1.09** folder if asked.
3. Open **HuntersAtlas.exe**. Atlas is enabled under **Mods & patches**.
4. Press **Play**, then **Continue**. Press **M** to open the map.

Keep/select your existing save folder in the launcher. Game files, saves and
personal profiles are not included in the download. Installation does not
overwrite your game files. Extract updates into a new folder and run Install.cmd.

## Map and controls

- Ordinary slopes remain continuous. Auto follows player height at actual
  overlapping passages; Upper/Lower offer local passage overrides.
- Mouse wheel, keyboard **+ / -** and mapped controller **RT / LT** zoom use
  the same resolution-scaled limits. Pan with mouse drag or the right stick.
- Resizing preserves world coverage. Taller and ultrawide screens keep a
  centered, proportionally scaled layout without stretching.
- For faster mouse-look: **Inputs → Mouse look → Sensitivity → Save**.
  Try 2.0 instead of 1.0. Right-stick emulation retains the game's turn-speed limit.

The drawings are decorative context, not surveyed building/tree positions.
The October launcher cache-recovery fix and runtime integrity checks are retained.

## Verification

The illustrated runtime passed 28 native offscreen cases across 1280×720,
1920×1080, 2560×1440, 3840×2160, 1920×1200, 3440×1440 and 5120×1440.
Each case checked zoom controls and limits, live resize coverage, canvas bounds,
legend alignment and visible framebuffer output. All 16 maps also passed native
render and private visual review. Test reports accompany the release.

These checks do not certify every live display/GPU combination or every player-only
roof, ladder, drop or dynamic door. See [QA](docs/QA.md) and [release notes](docs/releases/v3.1.md).

**Atlas 3.1 is supported. Earlier versions are legacy and unsupported.**
