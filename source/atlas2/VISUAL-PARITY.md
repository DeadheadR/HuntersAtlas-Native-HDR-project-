# Historical source-only visual parity audit

Current status is in [TEXTURE-LIFECYCLE.md](TEXTURE-LIFECYCLE.md). The 16-ppu
integration's descriptor-capacity defect has synthetic and native repair evidence.
Four sampled same-view raster comparisons pass operational checks; full visual
identity and navigation readability are unaccepted. The checklist below records
the earlier baseline; its statements about absent live measurements are historical.

Atlas2 is currently **not visually identical to V1**. There is no measured in-game
speedup, completed live comparison, or gameplay FPS result. This checklist is based
on source and validated local packs. CPU bake/lookup/cache tests cannot establish
gameplay performance or visual acceptance.

| Feature | V1 reference | Current Atlas2 | Status / next visual check |
|---|---|---|---|
| Floor coordinates | Live X/Z triangles, Y vertex heights, authored area/layer identity | Same current-pack coordinates, bounds and heights, projected into rasters | Coordinates retained; raster edge/detail parity unverified |
| Supported geometry | Version-1 rectangles and version-2 triangles supported by retained reader | Baker targets the current 16 version-2 triangle packs with vertex heights | Legacy rectangle packs are not supported by this baker |
| Floor material | World-anchored parchment texture multiplied by height tint | Flat shaded RGBA; no floor parchment texture | Omitted material/grain; screen background art remains |
| Height colors | Shared range for active floor and layers within 6 Y units; RGB `(q+4,q+2,q)`, `q=int(118+120*t)` before texture | Per-floor range including anchor; RGB `(242,240,238)*(118+120*t)/255` | Different range and color formula; cannot claim same colors |
| Elevation toggle | Toggles floor shading and corresponding UI | Static shading remains baked; reference responds to toggle | Not implemented for static tiles; UI state can change independently |
| Active outlines | Same authored rings; RGB 204/193/163, alpha 220; width `0.85*s` UI units | Same ring locations/color/alpha; fixed world width 0.12 | Width/AA/rasterization differ |
| Active walls | Same authored segments; RGB 15/18/19; width `clamp(0.13*z,2.5*s,5*s)` | Same segments/color; fixed world width 0.32, hence ideal screen width `0.32*z` | Important zoom-dependent thickness difference |
| Other-floor context | Excludes active layer; fill alpha 38 nearby / 27 far, outline alpha 62 nearby / 49 far | One precomposed all-floor context including active layer underneath active imagery; fill 27 and outlines 49 | Near/far emphasis omitted; edge/context composition differs |
| Enclosed void/interior fills | Separate dark opaque fills, current/context material, then floors over them | Not baked | Omitted; may affect interpretation of enclosed spaces, not merely decoration |
| Interior and wall-band hatch | Cached, zoom-dependent scratch/hatch strokes and deterministic wear | Not baked | Omitted |
| Hatch exclusion around symbols | Dynamic screen-space glyph footprints cut decoration strokes | No corresponding static hatch/mask | Omitted with decoration; live symbols still draw above map |
| Drawing order | Original floor/outline/wall order, context per layer | Primitives rasterized into reveal-signature groups; group compositing order differs | Overlap/alpha pixels can differ even with fog disabled |
| Reveal/fog decisions | Authored reveal regions; centroid/vertices and bbox probes; guarded flag reads | Same authored region order and floor/line probes become slice requirements; flag decisions evaluated before tile loops | Policy intended to match for retained primitives; exact raster fog-edge pixels unverified |
| Private fog preference | Working installation retains its own preference | Private fixture forces fog on; both in-process comparison modes share it | Must compare identical settings, not different installations' defaults |
| Player and facing | Existing live adapter, projection, icon/tint and yaw mapping | Reused unchanged after static base | Source retained; native alignment not yet observed |
| Lamps/NPC/ladder/gate icons | Existing live discovery/eligibility/rules, icon assets, sizes, colors and tooltips | Same draw path/assets; floor filtering can differ if selected layer differs | Source retained; live visibility still needs comparison |
| Pickups | Live flag/category logic and colored dots | Reused unchanged | Same category colors in code; native presentation unverified |
| Background/frame/font/compass/menu | Existing art, font and surrounding UI | Reused unchanged | Source/assets retained; not a screenshot parity pass |
| Labels | Original catalog and location/marker text | Private catalog is empty, areas/metadata markers anonymized; reference/feature labels may differ internally | Intentional test-fixture difference; no screenshots/log text to user |
| Automatic floor | Stateless nearest local interpolated surface, else authored anchor | Same raw lookup semantics, plus 0.35-unit continuity hysteresis when moving less than 20 X/Z units between samples | Raw offline probes match; history can intentionally change rendered layer |
| Manual floor / visual reference | Normal V1 automatic behavior | Developer manual override; prototype reference rendering shares selected floor with static mode | Fix floor for visual parity; test floor selection independently with V1/strict telemetry |
| Zoom/pan/follow | Same UI transform and input paths | Reused, with tiled base and discrete LOD | Shared control code; resolution/LOD/cache effects differ |
| Cold map / map switching | Geometry submitted by original path | Max 4 tile uploads/frame and bounded retirement; partial imagery can appear while cache warms | New transient behavior; first-open hitch and native upload lifetime unmeasured |
| Overlaid comparison | V1 alone | Reference plus 50% static base in developer overlay mode | Use for alignment only; use separate full-opacity modes for color/material comparison |

`s` is `MapUiScale()` and `z` is the actual stored zoom in UI screen units per native
world unit. They must be read from the same render-frame snapshot in comparisons.
The term "native world unit" does not assert a conversion to metres.

## Raster scale and zoom implications

LOD0 contains **8 texels per native world unit**, so one source texel spans **0.125
world units**. The 256-texel interior spans 32 world units; 2-texel gutters on each
side make the allocated texture 260×260. At LOD L, density is `8 / 2^L` and tile
interior spans `32 * 2^L` world units.

The nominal choice is `floor(log2(8 / z))`, clamped to available levels. If more
than 48 relevant visible tiles are requested, the renderer can coarsen further.
LOD images are independently rasterized with one pixel-centre coverage sample;
they are not area-filtered downsampled mips, and there is no crossfade between LODs.
The pinned backend defaults to bilinear sampling; bilinear filtering cannot restore
detail missing from the source raster. Seams, transition popping, thin-line loss
and native readability remain unverified.

At LOD0, the ideal footprint of one source texel is `z/8` UI units:

| ImGui display size, assuming scale 1 framebuffer | UI scale s | Recenter zoom `9*s` | Source texel at recenter | Keyboard/controller/footer max `25*s` | Source texel at that max |
|---|---:|---:|---:|---:|---:|
| 1280×720 | 1 | 9 | 1.125 | 25 | 3.125 |
| 1920×1080 | 1.5 | 13.5 | 1.6875 | 37.5 | 4.6875 |
| 2560×1440 | 2 | 18 | 2.25 | 50 | 6.25 |
| 3840×2160 | 3 | 27 | 3.375 | 75 | 9.375 |

These are **source-derived calculations**, not observed image-quality measurements.
Actual framebuffer/DPI scaling must also be recorded. The inherited mouse-wheel
and Fit paths clamp raw zoom to 0.15–25, while keyboard/controller/footer use
0.15*s–25*s. Therefore "maximum zoom is 25" is not generally correct.

Fixed world-width lines are a separate parity problem: at default `z=9*s`, the
ideal Atlas2 wall width is `2.88*s` versus V1's `2.5*s`; at scaled maximum it is
`8*s` versus `3.25*s` (about 2.46×). At zoom-out, V1 keeps its minimum screen width
while Atlas2 lines can become subpixel or disappear in independently rasterized
coarse levels. Current LOD0 outline widths are only 0.96 texel active / 0.8 texel
context; walls are 2.56 texels. This needs inspection at both zoom extremes.

## Next-window comparison protocol, prepared but not run

Use one guarded copied-save process, a fresh parent reservation and the shared
native lease. No native launch is permitted while the current parent hold applies.

1. Confirm native arrival status, region, XYZ and independently calculated V1/raw
   floor at an eligible discovered destination. Record selection discrepancies.
2. For visual pairs, fix that floor with the developer override. Keep pose/yaw,
   region, selected floor, zoom, view centre, canvas, viewport/UI scale and feature
   settings identical. Matching floor alone is insufficient.
3. Capture separate full-opacity static/reference frames after upload readiness;
   retain images locally only. Inspect default, Fit, scaled maximum and scaled
   minimum. Add pairs on either side of each observed LOD transition and across a
   tile boundary during pan. Test mouse-wheel and scaled control limits separately.
4. Compare floor edges, narrow paths, overlaps/stairs, wall/outline widths, void
   fills, material/contrast, icon contrast, fog boundaries, gutters and LOD changes.
   Known omitted styling must remain listed rather than reported as visual passes.
5. Compare layer history separately with manual override off. Do not infer V1 floor
   selection conformance from reference rendering forced to the same selected floor.
6. Preserve exact finite coverage by AreaNN/layer/destination. Hidden static tiles
   do not count as visual acceptance. No all-coordinate or all-location claim.

`visual_pair.py` prepares default/Fit/scaled-extreme same-view telemetry pairs and
rejects pose, zoom, centre, floor, size or feature-setting mismatches. Matching views
are labelled **pending visual review**, never pixel-identical or FPS-tested.
`visual-comparison-plan.json` specifies additional LOD/pan and appearance checks.
The new render-snapshot fields have CPU build/unit validation only until a native
window is granted; this does not add any live coverage.
