# Bristlune

Bristlune 1.0.1 is a painting and illustration application based on Krita, with
local PNG/JPEG export presets and original workspace layouts.

- [Product](https://bristlune.trieflow.com)
- [Privacy](https://bristlune.trieflow.com/privacy)
- [Support](https://bristlune.trieflow.com/support)
- [Source and licenses](https://bristlune.trieflow.com/source)

The Windows entry points are `bin/bristlune.exe` and `bin/bristlune.com`.
Existing BrushQuay settings, resource profiles and export-preset data keep their
original paths. The assigned Store identity and application ID are unchanged.

The original BrushQuay Windows run 34675482940 compiled the full application,
passed all six required Qt product suites and installed the CMake tree. It did
not qualify a deployed runtime, installed MSIX or public binary distribution.
The renamed Bristlune build and real artwork/export workflow require new native
evidence. The source/license and complete runtime audits remain open.

See [product identity](distribution/BRANDING.md),
[locked native pipeline](distribution/WINDOWS-BASELINE.md),
[audited MSIX release gate](packaging/windows/msix/README.brushquay.md), and
[export presets](distribution/EXPORT-PRESETS.md).

Bristlune modifications are Copyright 2026 Trieflow LLC. The application is based
on Krita, Copyright the Krita Developers, and distributed under GPL-3.0-or-later.
Original author and license notices remain in each source and resource file.
The [upstream README](distribution/UPSTREAM-README.md) is retained unchanged.
Historical native dependency locks, source records and verification logs retain
their original names and evidence; they do not claim a renamed Windows success.
