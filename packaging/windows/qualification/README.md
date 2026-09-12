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
review on another host. Native CI compiles the same four C# files using the
installed Windows Framework compiler and reference assemblies. No product code
or published runtime assembly is loaded into PowerShell or this observer.

## Observer launch compatibility

The native installer host remains x64 Windows PowerShell 5.1. Its .NET Framework
`ProcessStartInfo` lacks `ArgumentList`; the observer now receives the same six
values through `Arguments`, each quoted using the documented Windows
[backslash and quotation rules](https://learn.microsoft.com/en-us/cpp/c-language/parsing-c-command-line-arguments).
The executable, direct `Process.Start`, retained handle, activation-attempt flag,
timeout, ownership checks and cleanup order are unchanged. Embedded NUL is refused.

`test_observer_arguments.ps1` round-trips eight values through a real child
process, including empty, Unicode, quote, backslash, trailing slash and newline
values. On Windows it compiles a .NET Framework reader and tests its actual
`Main(string[] args)` under both CI PowerShell hosts before dependency fetching.
It also checks a real process-start failure through the original lifecycle core,
retaining the primary exception and separate cleanup error. Local PowerShell
7.6.6 replay passed; Windows PowerShell 5.1 execution is still required in CI.
Run 34706011185 failed earlier during dependency transport (WinError 10054) and
produced no artifacts; it provides no native result for this correction.

```text
pwsh -NoProfile -File packaging/windows/qualification/test_observer_arguments.ps1
```

## Read-only native dependency observations

After the existing exact native/install/stage checks and runtime materialization,
`prepare.py` writes `staged-pe-imports.json` before calling the package SDK. Each
selected EXE, DLL, PYD and COM records its original application/locked owners and
paths, bytes and SHA-256, plus separate normal and delay import descriptors. The
record binds the exact source commit/tree, run/attempt, dependency lock and native
build receipt. It never changes runtime selection or executes a payload file.

The reader is `tools/llvm/bin/llvm-readobj.exe` from the already locked
llvm-mingw 20251118 archive. Original archive SHA-256:
`d14a2022c095b83404b64a249406478d852821d31beaa32abe31c932832b3538`.
Its 1,545,216-byte reader has SHA-256
`2911b6a130c7d88e74a894368d493e5fa80a0baae3bc6ed35e06b543e360fd4e`,
measured directly from that rehashed archive. The production collector checks the
reader against the original verified stage owner/size/hash before and after use.
It uses the documented [LLVM COFF import reader](https://llvm.org/docs/CommandGuide/llvm-readobj.html),
with output grammar checked against retained LLVM source revision
`a832a5222e489298337fbb5876f8dcaf072c5cca` (`COFFDumper.cpp` and
`COFFObjectFile.cpp`). Named imports retain the hint; ordinal imports remain
explicit. A real PE fixture exercises both directories using the exact Windows
reader after dependency fetch and before the long native build.

Bounds are 1,024 PE files, 8 MiB of reader output per file, a 20-second reader
process timeout, a five-minute budget checked between files, eight file errors,
and 16 MiB of retained rows plus bounded context/errors. Unknown/truncated output,
changed inputs, missing tools and write failures yield typed `incomplete`
observations. Output is exclusive; existing evidence is preserved. The original
SDK/package error remains primary even when this observation is incomplete.

The installed observer separately records `module-observation-startup.json` and
either `module-observation-workflow-complete.json` or the best available failure
snapshot. It reads only the retained, package-verified process after owned job
assignment, validates that process before and after enumeration, and records
full paths and stable file bytes/SHA-256 for package and Windows modules. Package
modules must match the exact payload to receive an observed result. Source/tree,
run/attempt, process identity/start, unsigned-package/native-receipt records and
the exact `probe-input.json` digest accompany each snapshot. Module observations
are capped at 1,024 paths, 2 GiB of aggregate file bytes and a fifteen-second
budget checked between reads and before accepting a snapshot. Outside paths,
missing/mutated payloads, ownership changes or query errors remain incomplete
metadata; their errors cannot replace the primary GUI or cleanup error.

The original late `Modules()` check still requires actual Qt core and platform
modules and rejects modules outside the package/Windows boundary. Its acceptance
logic, normal close, file/pixel oracles and cleanup remain unchanged. These new
records explicitly set `observationOnly: true` and `releaseReady: false`; an
`observed` status means the bounded observation completed, not source or license
approval. They add no binary uploads. The remaining libvpx/gperf producer pins
and debug-runtime license/source review are separate; no debug or libvpx file
has been excluded.

Focused validation includes real native-file measurements and seven module
ownership/query/hash refusals; normal/delay/name/ordinal parsing, real child
reader timeout/output/exit failures, reader/input mutations, exclusive retention,
and the original package failure following incomplete metadata. Local Framework
compilation and PowerShell replays passed. The locked Windows reader and actual
installed module enumeration still require a fresh native run.

```text
python -m unittest discover -s packaging/windows/qualification -v
pwsh -NoProfile -File packaging/windows/qualification/test_module_evidence.ps1
```
