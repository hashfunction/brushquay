# Bristlune disposable installed qualification

This candidate extends the locked native Windows build with a real installed
consumer workflow. It has **not yet passed on Windows**. The prior native success,
run 34675482940, proves the earlier BrushQuay source and its six Qt suites; it
cannot qualify these new Bristlune deployment or GUI changes.

The workflow runs automatically after the unchanged full native compile and all
six required product suites. `prepare.py` requires the exact clean commit/tree,
GitHub run and attempt, the native-hashed suite XML, full CMake install inventory,
and reconstructed locked dependency stage. It selects explicit application,
Qt/KDE/plugin/resource/Python/LLVM runtime paths and records every source owner,
path, size and SHA-256. It does not run a dependency deployment script or modify
those inputs. The SDK executables use the explicit 10.0.26100.0 x64 paths,
Microsoft signatures/version metadata and hashes checked before each call.

The disposable identity is `Trieflow.Bristlune.Qualification`, publisher
`CN=Bristlune-CI-Qualification`, version `1.0.1.0`, application ID `BrushQuay`.
The actual installed family must be
`Trieflow.Bristlune.Qualification_kheb0ettnemtj`.
It never substitutes for the assigned Store identity. The existing audited
release builder still requires complete license and corresponding-source review.
Qualification records explicitly leave both clearance flags false.

`qualify.ps1` compiles a separate .NET Framework UI observer before installing or
adding trust. It signs a private copy with a non-exportable ephemeral certificate,
checks installed payload bytes, and activates through the normal package broker.
The observer retains the broker process handle, validates its executable and
package identity before assigning its job, and uses the normal product UI:

1. Create an explicit 512×384 document and save `blank.kra`.
2. Select the normal brush, reset foreground/background colors, show the canvas,
   zoom to 100%, and draw a real native mouse stroke on the observed canvas.
3. Save `artwork.kra`, invoke File → Export, and save `artwork.png` through the
   owned native/Qt picker and normal PNG options dialog.
4. Open that PNG and save `reopened.kra`, then quit normally with exit code zero.

The filename, dimensions, brush pixels, export and reopen are independent gates.
The standard-library decoder reads the actual KRA merged images and PNG and
requires white initial pixels, a bounded nonzero painted region, matching export
and reopened pixels, and unchanged protected bytes. Loaded native modules must
match recorded package bytes or lie within Windows; the actual Qt core and
platform plugin must be observed.

Each input verifies the retained process, native window, owner chain, foreground,
visible window/target bounds and stable UIA observation. A pointer action also
hit-tests the exact native root. A picker is never typed into until its exact
caption, class, retained PID and owner chain are proved. Unavailable or ambiguous
selectors stop the workflow and retain bounded UI observations. Screenshots are
unedited owned-window captures with pre/post guards and SHA-256 provenance.
An enumerated native desktop mode may be selected for readable captures; the
original mode is restored on success or failure, without registry or system DPI
changes.

The fixture and private package profile have exclusive markers. Existing
BrushQuay profiles/config/logs or product registrations cause refusal before
launch. File verification and profile sealing happen after proven normal stop;
failure cleanup needs an explicit stopped-process/job receipt. Changed or foreign
files/directories are preserved. Exact uninstall, certificate removal and display
restoration remain required. An abnormal observer exit without a stop receipt
leaves registration/profile state for recovery and fails qualification.

Only JSON/XML/log metadata, existing workspace exports, and guarded PNG captures
are uploaded. No MSIX, runtime, profile payload or generated KRA/PNG artwork is
uploaded. Verified unsigned package staging stays under the runner's ignored
`.brushquay/qualification/` directory for source/runtime review; it is not a
public release or distribution authorization.

Focused checks:

```text
python -m unittest discover -s build-tools/ci-scripts/tests -v
python -m unittest discover -s packaging/windows/msix/tests -v
python -m unittest discover -s packaging/windows/qualification -v
pwsh -NoLogo -NoProfile -File packaging/windows/qualification/test_input_guard.ps1
pwsh -NoLogo -NoProfile -File packaging/windows/qualification/test_display_modes.ps1
pwsh -NoLogo -NoProfile -File packaging/windows/qualification/test_qualify.ps1
```

`GuiProbe.csproj` and its locked reference-assembly package support compilation
review on another host. Native CI compiles the same three C# files using the
installed Windows Framework compiler and reference assemblies. No product code
or published runtime assembly is loaded into PowerShell or this observer.
