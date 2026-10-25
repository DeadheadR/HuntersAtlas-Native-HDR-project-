# Two independent Atlas 3.1 builds

The existing edition uses **Bloodborne for Windows v1.9** (Supermedo).
The additional edition is based on **Awakenchan's Lantern Engine v0.9.37**,
commit `d901fbd2ea4bea114b37c26a2a9278d1e97f7b46`.
Both support the guarded **CUSA00207 1.09** game layout and share the published
Atlas 3.1 illustrated map data. Each has its own runtime and launcher integration.

Run these from the repository root:

```bat
Build-Windows.cmd
Build-Lantern.cmd
```

Each command compiles and packages only its selected target. Outputs go into
fresh timestamped directories under `.local/artifacts/windows19/` or
`.local/artifacts/lantern/`; each target's `latest.json` points to its receipt.
The player archives are `Hunters-Atlas-3.1-Windows.zip` and
`Hunters-Atlas-3.1-Lantern.zip`. No command publishes a GitHub release, changes an
installed launcher, accesses saves, or overwrites a previous output.
`-PackageOnly` packages already built binaries and is for local QA.

## Build inputs

Copy `build-inputs.example.json` to `.local/build-inputs.json`, then set your
Python, MSYS2 CLANG64, .NET 8-or-newer SDK, and retained Windows native-build
paths. The Windows build preserves the published 3.1 launcher and runtime link
inputs, recompiling its three illustrated-renderer objects. The Lantern build
uses the official v0.9.37 source tree with bundled third parties; its preparation
script verifies the pristine source-tree digest, applies exact guarded patches
and records source hashes. Keep that upstream input tree clean. Changes to Atlas
integration inputs automatically refresh the prepared files while preserving
unaffected native build objects.

The scripts verify the exact published Atlas 3.1 Windows archive and official
Lantern v0.9.37 Windows archive hashes before using them. The Windows retained
native objects and captured link arguments remain required build inputs; this
does not claim to be a fresh machine build without those inputs.

## Distribution

Keep one repository and one release with two clearly labelled player ZIPs.
Publish corresponding source, retained build instructions, checksums and test
results alongside them. Keep the current Windows download available while
validating Lantern. Do not replace an old release asset silently.

Extract either edition into its own folder. Do not overlay their runtimes.
The Lantern edition stores launcher settings under its own `state/profile` and
retains the selected save path. It can import ordinary path/preferences fields
from a prior launcher, but does not modify that launcher's profile. Its Settings
page contains Atlas controls. Stock Lantern auto-updates are disabled because
they would replace the modified engine; update using a complete Atlas ZIP.

Lantern Engine by Awaken (https://github.com/Awakenchan/LanternEngine).
This is a modified Hunter's Atlas build, not an official Lantern Engine release.
Preserve upstream GPL notices and corresponding source when distributing it.
