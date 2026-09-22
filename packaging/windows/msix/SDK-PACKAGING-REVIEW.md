# Original SDK packaging failure and bounded correction

Run `34727411552`, public source `7e49e7d5614d617e6491f625422415d5f70a0c42`,
completed the native build and all six Qt product suites. Its first release
lifecycle failed in MakePRI, before signing, installation, activation, or any
consumer workflow. Neither installed lifecycle nor final Store export passed.

Original artifact `10308404998` (`Bristlune-Windows-foundation-qualification`)
is 1,729,526 bytes, SHA256
`958e81dec7bb1502b5dc3e8f00d924352b4162250abf0aaf2061d39442d6f6c7`.
The unmodified ZIP, extracted evidence, and full failed log are retained privately
under `/private/tmp/bristlune-34727411552-review` and
`/private/tmp/bristlune-34727411552-failed.log`.
The original `installation-result.json` is 3,756 bytes, SHA256
`e864b76bccc3a20d8b45ba633c091ccd6d3d61bf9ace79660843e09e50c62449`.
It records `primaryError: "python exited 1"`, no unsigned/signed package, and no
cleanup errors. The more precise original UTF-16 SDK log reports
`PRI175` / `PRI235`, `0xdef00512`, on:

```text
D:\a\brushquay\brushquay\.brushquay\qualification\installed-34727411552-1-4127a01d978c480d81f0f9d7b229d5ea\.brushquay-msix-5vmfqmpi\payload\Bristlune\qml\QtQuick\Controls\FluentWinUI3\light\images\pageindicatordelegate-indicator-delegate-current-pressed@3x.png
```

That path has exactly 260 characters. The original config indexed the entire
payload, including Qt's own QML image resources. The manifest references only
the three locked `Assets` logos. The correction changes only the PRI seed to
`Assets`; every runtime file remains in the exact copied, packed, independently
read-back and SDK-unpacked payload. No file omission or shorter runtime name is
introduced. Microsoft's [PRI configuration contract](https://learn.microsoft.com/en-us/windows/uwp/app-resources/makepri-exe-configuration)
defines `startIndexAt` as the seed relative to the index root. The small native
fixture will verify the actual SDK result; the original log alone does not prove
which internal MakePRI path operation rejected the 260-character name.

The same original receipt exposes a second deterministic mismatch before another
long build: SignTool's `FileVersion` display string is
`4.00 (WinBuild.160101.0800)`, while MakePRI and MakeAppx display
`10.0.26100.7705 (WinBuild.160101.0800)`. The existing production preflight already
checked all three tools' numeric major/minor/build parts as `10/0/26100`, their
original executable names, valid Microsoft signatures, and exact file bytes.
The exporter incorrectly required the display string prefix for every tool.
The receipt now retains the four numeric parts in addition to the unchanged
display string. Export requires integer `10/0/26100` plus a bounded integer
revision, the original nonempty display, Microsoft subject and certificate
thumbprint. Tool path, current SHA256/size, fixed SDK version, and both original
installed lifecycle bindings remain enforced. Historical receipts are unchanged;
their previously unrecorded numeric revision is not invented.

The original remaining SDK record fields agree with the existing verifier:

| Tool | Bytes | SHA256 |
| --- | ---: | --- |
| makepri.exe | 919896 | `27d40a7aa43710fa3a15675ef18cb303f20815eb008379a08a81d49921844596` |
| makeappx.exe | 584024 | `00fff202b71c1266b8c3899701e42b5468ea153b2b33a0a47215fe27695f16d0` |
| signtool.exe | 543064 | `431ee314c83988cacda86606356fd321b75ae0093481b97e3b738e99c412f2a0` |

All three paths share the exact SDK `10.0.26100.0/x64` directory and Microsoft
certificate thumbprint `6ACE61BAE3F09F4DD2697806D73E022CBFE70EB4`. The fixed SDK
record has exactly `sdkVersion`, `makepri`, and `makeappx`; SignTool remains in its
separate path/hash/size record. No original tool hash pin is substituted here.

Validation on the local macOS host:

```text
python3 -m unittest discover -s packaging/windows/msix/tests -p test_pri_assets.py -v
  1 passed; 1 actual-Windows-SDK test explicitly skipped on macOS
python3 -m unittest discover -s packaging/windows/msix/tests -p test_store_lifecycle_replay.py -v
  5 passed, including both full original-file lifecycle fixture replays
python3 -m unittest discover -s packaging/windows/msix/tests -p test_store_export.py -v
  4 passed
TMPDIR=/private/tmp <pwsh> -NoLogo -NoProfile -File packaging/windows/qualification/test_operation_scope.ps1
  passed actual production callback scope and unchanged pre-existing profile refusal
git diff --check
  passed
```

The PRI scope test failed against the original config because runtime files and
the manifest were incorrectly included in the indexed set, then passed after the
single config change. The full lifecycle replay with the actual SignTool display
string failed at the original exporter version predicate, then passed after the
numeric correction. Missing/wrong/short/bool/negative/out-of-range numeric parts,
empty display, foreign publisher, and invalid thumbprint remain refused. The first
local PowerShell run used macOS's symlinked `/var` temporary location and correctly
refused that path; the unchanged test passes with the owned `/private/tmp` location.

Before a full native rerun, the manual-only `msix-fixture.yml` workflow can run on
the reviewed public snapshot. It performs no app build, install, signing, or UI
qualification. Its Windows-only test observes original signatures and both SDK
version representations, invokes the unchanged production MakePRI/MakeAppx
builder with a Qt-named PNG at a path longer than 260 characters, verifies exact
unsigned ZIP and SDK-unpacked bytes, and checks the actual
[detailed PRI dump](https://learn.microsoft.com/en-us/windows/uwp/app-resources/makepri-exe-command-options)
contains precisely the three manifest logo paths. Original JSON/XML/log metadata
is retained even on failure; the fixture package is not uploaded or represented
as a product package. The same Windows test is discovered by the existing native
pipeline before dependency acquisition or compilation.

Actual Windows SDK fixture, fresh dual installed lifecycles, Store export, and
marketing capture remain pending. Reviewed runtime/source/license binding and
the null final marketing package binding are unchanged.
