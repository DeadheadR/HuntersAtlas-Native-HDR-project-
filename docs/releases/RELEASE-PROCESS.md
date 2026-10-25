# Atlas 3.1 release procedure

The public product remains Atlas 3.1. This update uses immutable tag
v3.1-launchers, preserving the original v3.1 tag and assets.

1. Build with Build-Windows.cmd and Build-Lantern.cmd using the pinned inputs
   documented in source/launchers/README.md.
2. Verify both archives, shared map hashes, native/launcher contracts and affected
   live game behavior. Recheck protected saves and prior installations.
3. Update installation, compatibility, QA and release notes. Capture actual map
   screenshots and bind receipts to exact archives.
4. Stage only reviewed files. Exclude build outputs, saves, profiles, caches,
   secrets and unrelated local changes.
5. After owner authorization, verify remote main's expected parent, commit and
   push reviewed changes. Create a draft release titled Hunter's Atlas 3.1 under
   v3.1-launchers, using v3.1-launchers.md as its body.
6. Attach both player ZIPs, corresponding source, installation guide, QA receipt
   and SHA-256 checksums. Verify uploaded digests, publish and mark Latest.
   Check public links, screenshots and preservation of previous releases.

Never replace an existing release asset or move an existing tag. Player build
commands do not publish a release or modify an installed launcher.
