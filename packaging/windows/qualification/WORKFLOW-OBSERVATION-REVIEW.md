# Ordered original workflow observations

This correction was identified from the committed qualifier while native run
34724934063 was still compiling. It is not a claim about that run's eventual UI
result. That run was left unchanged.

`GuiProbe.Picker` used only the target basename for its observation filename.
The original workflow exports `artwork.png`, then opens that same file.
`Observe` records both calls and `Save` uses `FileMode.CreateNew`, so the second
call necessarily attempted to overwrite the first observation and threw before
the reopen filename input. The picker stage now includes its zero-based index
in the complete observation sequence. Exclusive writes remain unchanged.

The original exporter required only the five screenshot stages, even though
the workflow also records five picker stages. It now requires the exact ten
ordered observations below and the same five original screenshots. Every picker
still passes the original timestamp, PID/start, package, executable hash, handle,
node-bound, and original-body checks; picker stages must not claim captures.

| Index | Original observation | Capture |
| --- | --- | --- |
| 0 | 01-installed-ready | yes |
| 1 | new-document-settings | yes |
| 2 | picker-02-blank.kra | no |
| 3 | picker-03-artwork.kra | no |
| 4 | 02-painted-artwork | yes |
| 5 | picker-05-artwork.png | no |
| 6 | png-export-options | yes |
| 7 | picker-07-artwork.png | no |
| 8 | picker-08-reopened.kra | no |
| 9 | 03-reopened-export | yes |

## Focused evidence

`test_workflow_observations.ps1` extracts and executes the actual C# `Workflow`,
`Picker`, `SaveAs`, `Button`, `Observe`, `Save`, `Hash`, and dictionary helper.
UI/native/image-encoding leaves are controlled explicitly; this fixture is not
a Windows UI qualification or image claim. Actual exclusive evidence writes
initially reproduced `picker-artwork.png-observation.json already exists`.
After the one-line picker correction it verifies ten observations, five capture
pairs, five filename inputs, the original 30 pointer packets, one close input,
both original normal-close failure branches, and preservation of an existing
observation with zero filename input after refusal. The test runs in both
existing PowerShell test steps before native compilation.

The independent original-file lifecycle replay initially failed with
`Complete exact original evidence file set differs` when given the ten actual
stages. Both complete lifecycle fixtures now pass the unchanged package,
source, module, cleanup, artwork, and snapshot checks. Additional mutations
refuse omitted, duplicated, reordered or foreign-PID picker observations,
invented picker captures, and missing original captures, even when outer
snapshot hashes are refreshed.

Validation performed locally:

* `pwsh -NoLogo -NoProfile -File packaging/windows/qualification/test_workflow_observations.ps1` — passed.
* `python3 -m unittest discover -s packaging/windows/msix/tests -p 'test_store_*.py' -v` — 10 passed.
* Full unchanged observer/support sources plus the picker naming correction
  compiled with C# 5 against the .NET Framework 4.8 reference assemblies.

Private original red outputs are retained at
`/private/tmp/bristlune-workflow-observation-red.log` and
`/private/tmp/bristlune-export-sequence-red.log`.

## Remaining original contract audit

The source-defined ordinary file captions are `Saving As`, `Exporting`, and
`Open Images` (`KisMainWindow.cpp`). The export action is `E&xport...`
(`kritamenu.action`), matching the existing ampersand removal. The new-document
title is `Create new document`; its concrete derived class has no `Q_OBJECT`,
so its inherited metaobject remains `KisOpenPane`. The Create button is
`&Create`, and the width/height object names remain `doubleWidth`/`doubleHeight`.
The PNG options are a `KoDialog` containing `KisWdgOptionsPNG`. No title or
selector was broadened. Native Windows provider topology remains an actual-run
requirement.

The four artwork filenames match `workflow_files.py`, the ownership allowlist,
and exporter snapshots. Fresh-profile defaults are RGB8, opaque white; the
independent oracle still requires exact 512×384 pixels and the original bounded
stroke, export and reopened-image equality. Document captions retain the full
filename through `KisDocument::caption()`.

The remaining producer/consumer fields were checked across `GuiProbe.Main`,
`qualify.ps1`, `release_build.py`, and `store_export.py`: source/run/attempt and
native evidence; fixed identities and package directory names; original
prepared-package and full PE graph snapshots; SDK and observer hashes; exact
unsigned payload; both startup/workflow-complete module records; process start
and normal exit; all cleanup flags; installed-file oracles and display restore.
No further deterministic producer/verifier mismatch was found in that scope.
These source checks do not replace either full original installed lifecycle.

No product, runtime selection, source/license binding, input guard, retry,
timeout, file oracle, module policy, normal-close or cleanup behavior changed.
