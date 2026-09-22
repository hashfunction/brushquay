# Exact-package real Windows marketing capture

This is a separate, manually dispatched capture workflow. The active
`binding.json` deliberately has `qualified: null`: it cannot download, install,
or capture a product until the reviewed original successful release is pinned.
It neither rebuilds the application nor supplies consumer qualification.

## Three intended raw scenes

The original **Moonlit Garden** illustration is a layered OpenRaster input,
authored for this demo. `fixtures/artwork-preview.png` previews only that artwork;
it is not an application screenshot and must not be published as one. The
generator and artwork are dedicated under CC0-1.0 by Trieflow LLC. Pillow is
needed only to regenerate the committed fixture; capture CI does not install it.

All document paths visible during the actual capture use the exclusively owned
`C:\Bristlune Demo` folder. Ordinary application actions open the ORA, save a KRA,
save and apply a named PNG export preset, export the image, open that actual PNG,
and save the reopened document. No settings, document or preset state is injected
into the application profile.

| Raw filename | Intended composition and accurate caption |
| --- | --- |
| `01-painting-workspace.png` | Moonlit Garden fitted in the real painting workspace, with the three original named editable layers. Caption: “Build an illustration with layers.” |
| `02-export-preset.png` | The actual Export with Preset dialog showing the saved **Moonlit Garden - PNG** preset and real PNG options over the illustration. Caption: “Save a named preset for repeatable exports.” |
| `03-exported-illustration.png` | The actual exported PNG reopened and saved as a document, fitted in the workspace. Caption: “Reopen and check the exported illustration.” |

The screenshots use raw `Graphics.CopyFromScreen` pixels of the complete visible
application window; the preset scene includes its actual owned modal dialog.
There is no screenshot cropping, recoloring, text replacement, reconstruction,
or generated application chrome. Input artwork generation is separate from
screenshot capture. Inspect the raw scenes after a successful capture before
using these captions or publishing the files.

## Binding and lifecycle

Before dispatch, a reviewer must fill the exact successful public source commit,
run ID and attempt, Store/metadata artifact IDs, and original unsigned MSIX and
`store-export.json` byte counts/SHA-256 values. The release must have completed
both original installed lifecycles and the independent exporter. The capture
checkout and the separately checked-out qualified source must both be clean.

`prepare_capture.py` verifies GitHub run/artifact provenance, full downloaded ZIP
size/SHA-256, safe member inventory, and the exact two Store output files. It
retains both original installation receipts and every original snapshot. The
qualified source's unchanged helpers verify payloads, original cleanup/normal
close and pixel oracles, source/notice owner selection, graph exclusions and
the exact unsigned MSIX container. The pinned original final export receipt
binds the original path-sensitive validator's result without rewriting Windows
paths in historical evidence.

`prepare_probe.py` substitutes only the reviewed `Workflow` method and the
capture-purpose literal in the qualified `GuiProbe.cs`. Its original native
input, exact PID/process-start/executable/package ownership, window/foreground,
picker, job, module and cleanup methods remain byte-identical. The original
workflow body itself is pinned; unexpected qualified-source changes refuse
generation. This separate observer is compiled against the unchanged qualified
support helpers, then receives the original payload/source/native-evidence
bindings. Ordinary UIA window move/resize operations and a supported original
display mode produce readable full-window frames; original display restoration
remains required.

`capture.ps1` uses the original qualification lifecycle dispatcher and original
Appx, install readback, trust, owned process-stop, uninstall, profile cleanup and
display helpers. Fixture customizations are the exact capture filename
allowlist and the documented empty transaction-directory removal below;
the original ownership implementation is unchanged. Existing demo
folders, profiles and registrations are refused. The unsigned original stays
unchanged; installation uses a separately verified signed copy with an owned
temporary certificate, removed after uninstall.

After proven normal exit zero and an empty owned job, `capture_files.py` verifies
the original ORA hashes, three layers, identical real saved/exported/reopened
512×384 pixels, actual persisted named PNG preset, and raw screenshot dimensions
and process/hash provenance. Only then does cleanup seal and remove the owned
fixture/profile. Changed or unexpected files refuse cleanup. Successful capture
also requires uninstall, certificate removal, signed-copy cleanup, display
restore and unchanged original package/input readback. Failure remains failure,
even if some earlier screenshots exist.

The manual `marketing.yml` uploads only raw PNGs and JSON receipts. It does not
upload the app, profiles, signed copies, private keys or demo documents. It does
not mutate the assigned Store identity or any release acceptance gate.

## Focused local review evidence

* `python3 -m unittest discover -s packaging/windows/marketing -p 'test_*.py' -v`:
  six tests passed, covering exact method/purpose substitution (LF and Windows
  CRLF), refusal of changed qualified workflows, null/stale bindings, archive
  alias/traversal/extra members, actual fixture lease protection, persisted
  preset/pixel/raw-capture readback and changed-input/normal-stop refusals.
  The empty transaction-directory test covers the actual source-defined name,
  exact fixture membership, normal stop, unexpected content, multiple/foreign
  directories, links, and changed marker/protected files.
* `pwsh -NoLogo -NoProfile -File packaging/windows/marketing/test_capture_lifecycle.ps1 -Python python3`:
  actual capture lease/cleanup callbacks passed, including missing-stop and
  foreign-file refusals, the actual empty-transaction cleanup invocation and
  retained metadata, followed by verified stopped cleanup.
* `pwsh -NoLogo -NoProfile -File packaging/windows/marketing/test_capture_labels.ps1`:
  the actual C# expected-label expression passed the exact Windows Qt path and
  refused five different native-spelling, filename, destination or error texts.
* The complete generated observer compiled with C# 5 against .NET Framework 4.8
  references and unchanged original support sources. The capture PowerShell
  script parsed through the actual callback fixture.

These are capture infrastructure checks. Actual Windows screenshots and the
exact final-package binding remain pending the successful native release and a
separate reviewed capture dispatch.

## Source-defined export label and temporary directory

`KisExportFileTransaction::canonicalDestination` returns the canonical parent
through `QDir(parent).filePath(filename)`, using Qt forward slashes. The job
passes that exact path through `result.outputPath`; `KisMainWindow` displays
`Export created: %1` without converting it to native separators. The capture
therefore uses the exact expected `C:/Bristlune Demo/Moonlit Garden.png` message.
It does not normalize or fuzzily match observed UI text. The original expression
failed the focused Windows-path test before this correction.

The product retains its transaction folder after successful publication:
`QTemporaryDir` has `setAutoRemove(false)`, and moving its staged image leaves
an empty `.brushquay-export-XXXXXX` directory. A local actual Qt 6.11.2 replay
compiled the unchanged `KisExportFileTransaction.cpp` and confirmed one empty
directory remains even after transaction destruction. The same fixture queried
the actual QMenu accessibility provider: `Export with Preset...` retains three
literal dots. The separate Choose Destination button uses a Unicode ellipsis;
the capture targets that button's exact `chooseExportDestination` object ID.
Original replay source and output are retained under
`/private/tmp/bristlune-capture-qt-contract`.

Capture cleanup removes only this one documented empty directory after proven
normal stop, exact marker/root identity, protected-byte and full fixture-file
checks. It records the original directory identity before removal and a separate
removal receipt. It refuses nonempty, linked, multiple or differently named
directories. The original strict fixture inspector resumes immediately after
`rmdir`; no product or original ownership helper is changed.

The remaining capture labels were traced to the current source: `Open Images`
and `Saving As` in `KisMainWindow`; full filenames in `KisDocument::caption()`;
`Export with Preset` and its Q_OBJECT class `KisExportPresetDialog`; actual
`QLineEdit exportPresetName`, `saveExportPreset`, `chooseExportDestination`,
the saved QListWidget item name, `KisWdgOptionsPNG`, and `QMessageBox` titled
`Export Result`. Custom action XML flows through `KisActionRegistry` unchanged
in the default English locale. Native Windows provider and capture success
remain unproved until the separate exact-package run.
