# Native+ HDR in Hunter's Atlas

The Lantern edition of Hunter's Atlas includes **Native+ HDR** by LRF17
([LanternEngine-NativePlusHDR](https://github.com/LRF17/LanternEngine-NativePlusHDR)).
Native+ keeps the light of the game's scene all the way to the screen and tone maps it to your
display's peak. Two tone mappers:

- **Vanilla+** (default), by **souperman9**, from his RenoDX Bloodborne mod: the game's own image,
  with brighter highlights up to your display's peak.
- **PsychoV**: RenoDX's PsychoV-30 with Vanilla+'s highlights, bloom and hues: deeper blacks and
  more detail near the peak.

> **Unofficial, AI-assisted.** Native+ is not a RenoDX mod and is not affiliated with or endorsed
> by RenoDX or its authors. It reuses RenoDX's MIT-licensed code (PsychoV-30, its grading, hue
> correction, roll-off and gamut bridge) and souperman9's Vanilla+. Please do not report its
> issues to RenoDX or to souperman9.

## Quick start

1. Turn on HDR in Windows: *Settings > System > Display > Use HDR*. Running the Windows **HDR
   Calibration** app once gives the game your display's real peak.
2. In the launcher's **Display** page, turn on **HDR output**. The **HDR source** is **Native+**
   in a new installation. Entering or leaving Native+ needs a game restart.
3. Keep the game's own **Brightness** option (in the game's settings) at **5**.
4. Open the in-game menu with **Insert** (or L3+R3). The HDR section's first line should say
   **Native+: active**. Every setting there applies live and is saved in `lantern.ini`.

A good starting point: Preset #1, Vanilla+, Peak Brightness from your display, Game Brightness and
UI Brightness at 203 nits, everything else at its default. `nativeplus-example.ini` lists these
settings.

The Atlas map is drawn in the same layer as the in-game menu.

## Upscalers and frame generation

Lantern's upscalers work in Native+ (the scene is upscaled in 16-bit), and so do DLSS and FSR 3.1
frame generation. With FSR 3.1 frame generation, keep **UI Brightness** equal to **Game
Brightness**, or the HUD flickers.

## Source

`nativeplus-engine.patch` and `nativeplus-launcher.patch` come from LanternEngine-NativePlusHDR
`556131e` (branch `lantern-Native+HDR-beta`, Native+ 0.9.38.2 beta 2), whose patches target
Lantern 0.9.38. Here they are rebased onto Lantern 0.9.37 (`d901fbd`), the version Atlas pins:

- The engine patch is Native+'s, line for line. One hunk (`gpu/shim/window.cpp`) has new
  context, since 0.9.38 added a Wayland hint next to it.
- The launcher patch keeps only Native+'s HDR settings: `Core/Choices.cs`,
  `Core/DisplayPeak.cs` and `Views/DisplayPage.cs`. Native+'s own name, settings folder and
  updater are left out: this edition keeps Atlas's.

`source/launchers/prepare_lantern.py` applies the engine patch to the pristine Lantern tree
before Atlas's edits, and `prepare_launcher.py` the launcher patch before Atlas's launcher
edits. Both record the files they change in the preparation receipts.

## Licenses

Native+ is distributed under the same license as Lantern Engine (`LICENSE-LANTERN` in the
package). RenoDX's code is under the MIT license, in `licenses/RenoDX-MIT.txt`.
