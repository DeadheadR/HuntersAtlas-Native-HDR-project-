# Atlas 3.1 verification

The tested illustrated native runtime SHA-256 is
`54e8644c4b69fc455a5ace3bb894cb0b1cc126196accf74c4369d78e53a2005b`.
The player ZIP retains that executable unchanged.

## Resolution and zoom

28 native Vulkan offscreen cases passed: four representative areas at each of
1280×720, 1920×1080, 2560×1440, 3840×2160, 1920×1200, 3440×1440 and 5120×1440.
Every case verified wheel, keyboard +/- and mapped controller RT/LT zoom,
resolution-scaled minimum/maximum clamps, a live 75% viewport resize and restore,
preserved normalized world coverage, canvas bounds, a uniformly scaled legend
outside the canvas, visible framebuffer pixels and the expected area identity.

resolution-zoom-qa.json binds the results to the runtime, renderer objects, test
executable, map index and asset pack. No spoiler screenshots are published.
Offscreen coverage does not prove every driver's live swapchain/display-mode change.

## Maps and package

All 16 compiled areas and their hash-pinned payloads were validated. Fog grouping
preserved supported source surface area, and illustrations were clipped outside paths.
2,329 local overlap regions were analyzed; sheet/fallback QA found no empty or
internally ambiguous final overlap records. All 16 areas were rendered and reviewed
privately in 96 images, including upper/lower passage views.

The clean distributable is extracted into a fresh directory for ZIP CRC, manifest,
native-runtime, area-index, asset-pack and owned-runtime contract verification.
Only the generic map-settings seed is shipped under state/; personal configuration,
saves, installation receipts and generated shader caches are excluded.

## Limits

Six unavailable collision trees across three areas remain documented source
qualifications. Two static pickup positions lie outside the supported footprint.
Game-authored AI navigation plus collision support does not certify every
player-only roof, ladder, drop, moving object or door state. Decorative surroundings
are artistic placements, not surveyed environmental objects.

The local build was installed with settings/save hashes preserved and a verified
rollback copy retained. Package/render checks do not replace in-game acceptance
or testing on other hardware.
