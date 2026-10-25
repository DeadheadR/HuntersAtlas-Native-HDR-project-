# Atlas 3.1 verification

The dual-launcher update ships two separately built runtimes. Their exact archive
hashes and checks are recorded in [the release receipt](verification/v3.1-launchers/qa.json).

- Both ZIPs passed CRC, path, manifest and immutable runtime/dependency checks.
  All 321 compiled map files match between editions and retain Atlas 3.1 data.
- Nine Lantern integration contracts passed: game/settings, private profiles,
  fixed runtime/protected updates, matching engine identity, disabled travel,
  and rejection of mixed, changed, escaping or unknown inputs.
- Windows gameplay loaded a copied save in Hunter's Dream. The map displayed
  background art, symbols and aligned controls. Live resizing at 1080p, 1440p,
  4K and 3440x1440 preserved world coverage and centered confirmation.
- Lantern loaded the copied save and completed discovered-lamp travel from
  Hunter's Dream to Cathedral Ward. Its map passed the same four live viewport
  checks. The final build passed mouse-wheel zoom without player movement and
  mouse selection of a lamp's travel confirmation.
- Published Cathedral Ward and Forbidden Woods images are actual native map
  framebuffer captures. Woods uses area preview; it does not prove walking there.
- Original saves, prior release files and existing launcher profiles were
  fingerprinted before and after testing. No protected file changed.

The thin warm outlines are shared by both final builds. Windows gameplay/resize
checks preceded the final color/width adjustment; final appearance and mouse
checks ran on Lantern. Serial draw preparation is retained. Local NVIDIA tests
do not certify every GPU or driver.

The original Atlas 3.1 renderer had 28 offscreen resolution/zoom cases and all
16 areas were reviewed. Historical receipts remain in docs/verification/v3.1;
they do not describe the new runtime hashes or replace current live checks.

Six unavailable collision trees across three areas remain source qualifications.
Two pickup positions lie outside the supported footprint. Navigation/collision
data does not certify every roof, ladder, drop, moving object or door state.
Decorative surroundings are artistic placements.
