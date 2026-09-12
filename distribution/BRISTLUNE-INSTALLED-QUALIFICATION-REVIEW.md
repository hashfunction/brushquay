# Bristlune installed consumer qualification candidate

Prepared after the isolated Bristlune rename commit `ce98dba05b`. No public push,
Store submission, parent status or website change was made. **Actual Windows
packaging, installation and UI execution remain pending independent review and
CI.** Historical run 34675482940 remains evidence for its original source only.

The new candidate adds the approved disposable MSIX/runtime/installed workflow.
The existing public release builder and its source/license clearance gates are
unchanged. The full native build still requires all six product suites. Its new
receipt fields bind the GitHub run/attempt, complete install inventory, and exact
suite XML bytes. Packaging verifies these against the current clean source and
reconstructs the dependency stage from its pinned archives before selecting
runtime files. The selection includes native application QML, plugins, resources,
Qt/KDE runtime/plugins, embedded Python/PyQt, fontconfig/MLT data and target LLVM
runtime DLLs. Identical overlapping copies retain each owner; conflicts fail.

Read-only selection of the existing dependency receipt found 4,235 runtime
entries totaling 1,092,903,138 bytes. No full runtime copy, new dependency download
or full native build was performed on this Mac. Application install files will
be added and measured on Windows. These inventories support the release owner's
remaining source and notice audit; they do not assert that audit is complete.

`packaging/windows/qualification/qualify.ps1` owns installation, ephemeral trust,
profile/fixture and native display lifetime. The standalone `GuiProbe.cs` uses
normal broker activation and real UIA/Win32 input. Its source-traced selectors
cover the Create new document dialog (`KisOpenPane` is the inherited Qt meta-object
class of `KisDlgCreateNewDocument`), exact dimension widgets, Create, Saving As,
Exporting, PNG options, Open Images, and the real QPainter/OpenGL canvas classes.
Unproved native picker ownership or unavailable controls produce a bounded
failure; no synthetic receipt, app bypass, timeout relaxation or acceptance skip
was introduced.

The generated fixture contains protected original bytes. The app creates blank
and painted KRA documents, exports a PNG, reopens it and saves another KRA.
Independent ZIP/XML/PNG decoding proves dimensions, painted pixels and exact
export/reopen equality after normal exit. Loaded runtime modules are measured
against the installed package. Cleanup checks the exclusive markers, stopped
process/job proof, full file and directory snapshot, unchanged protected bytes,
exact registration and exact certificate before removing owned state. Missing
process-stop evidence retains state and fails, including after an observer
crash/timeout. Original desktop restoration and normal exit zero are mandatory.

Local verification completed for the candidate:

- 27 locked dependency/native configuration cases passed.
- 27 audited MSIX/source identity cases passed.
- 32 new qualification cases passed (native/run/tree/suite XML binding, runtime
  selection and conflicts, installed readback, pixel/export/reopen proofs,
  protected originals, foreign links/files/directories and cleanup ownership).
- All three focused PowerShell scripts passed: actual scalar input guard with
  18 unsafe mutations, display selection/apply/restore failure cases, and the
  real orchestration core across its normal path and 14 phase/cleanup failures.
- The standalone observer compiled as net48/C#5 using cached, locked 1.0.3
  reference assemblies, with zero warnings/errors. No Windows execution is
  claimed by this cross-host compile.
- Python compilation and `git diff --check` passed.

The rename commit's five existing local Qt suites already passed before this
harness change; no product behavior changed in this candidate. The next required
check is the actual Windows workflow, including MakePRI/MakeAppx, SDK unpack,
installed byte readback, source-traced control availability, native picker/canvas
ownership, real saved pixels, normal shutdown, uninstall and complete cleanup.
The first real run may identify a deployment or Windows accessibility detail;
all current gates remain strict while gathering that evidence.

See `packaging/windows/qualification/README.md` and `PLAN.md` for the exact
workflow contract and local commands. The workflow adds only guarded PNG
screenshot artifacts to its existing metadata globs; no binary/profile payload
is publicly uploaded.
