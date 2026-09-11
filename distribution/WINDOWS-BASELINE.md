# BrushQuay candidate Windows build

This is the native build foundation for approved Krita v6.0.4 source `e7e52a72ed37ecaf9ffaa2fab836b7c2f5539d1f`. Product workspaces, export presets, complete branding, MSIX, tablet behavior and redistribution clearance are **not complete**. The application baseline has not yet been compiled on Windows by this implementation task.

## Exact inputs

`build-tools/ci-scripts/brushquay-dependency-lock.json` contains 86 frozen KDE binary packages and four portable build tools, with exact archive URLs, sizes, SHA-256, metadata SHA-256, recipe revisions and dependency edges. No branch lookup, package alias, registry search, package override, pip install or signing service is used by the build. The earlier four CI/dependency repository commits and current recipe tree are retained as provenance references; their provisioning scripts are not executed.

The accepted **candidate ABI** is LLVM-MinGW UCRT x86_64, Clang 21.1.6 from the exact 20251118 archive. The lock also pins CMake 3.31.8, Ninja 1.13.2 and the official CPython 3.13.5 NuGet SDK. The NuGet SDK supplies headers/import libraries absent from the embeddable runtime archive. Its patch version matches the candidate CPython runtime; it requires security/update assessment before release. The Qt archive is KDE-patched Qt 6.11.0, whose later 6.11 fixes/source closure remain an explicit release gate.

The generic registry URLs contain historical branch labels plus fixed package version timestamps; only the exact recorded SHA-256 bytes are accepted. For `ext_*`, `sourceCommit` is the dependency **recipe repository's** `gitRevision`, not a claim that all upstream library sources have been archived. SPDX/resource entries remain `NOASSERTION` / not release-cleared. Local verification of downloaded bytes is not license clearance.

Primary references: [LLVM-MinGW 20251118](https://github.com/mstorsjo/llvm-mingw/releases/tag/20251118), [CMake 3.31.8](https://github.com/Kitware/CMake/releases/tag/v3.31.8), [Ninja 1.13.2](https://github.com/ninja-build/ninja/releases/tag/v1.13.2), [official Python NuGet usage](https://docs.python.org/3.13/using/windows.html#the-nuget-org-packages). Repository/tree pins and full URLs/hashes are in the lock.

## Windows prerequisites and commands

Use Windows x64 with a committed, clean source checkout, Git, a host CMake for the small configuration-parser regression, and a working Python 3.9+ bootstrap with standard-library HTTPS trust. Root's initial runner uses Windows 2022 and Python 3.12.10. No VM provisioning, machine PATH changes, Windows Update changes, SDK installer or privileged setup script is required by these commands. The bootstrap downloads/verifies data; the native build uses the locked portable tools. Native build metadata records OS, bootstrap version/path and Git source HEAD/tree; the runner image itself is not an immutable image lock.

From the source root:

```powershell
python -m unittest discover -s build-tools/ci-scripts/tests -v
powershell -File build-tools/ci-scripts/fetch-locked-windows-deps.ps1 -Python python
powershell -File build-tools/ci-scripts/build-locked-windows.ps1 -Python python -Jobs 2
# For the first configure diagnostic only:
# powershell -File build-tools/ci-scripts/build-locked-windows.ps1 -Python python -ConfigureOnly
```

The stage is `.brushquay/locked/{deps,tools}`; build/install outputs are `.brushquay/build` and `.brushquay/install`. The build explicitly selects the x86_64 MinGW Clang/Clang++/windres executables, pinned CMake/Ninja/Python SDK and verified `pkgconf.exe`. It sets `BUILD_WITH_QT6=ON`, `ALLOW_UNSTABLE=QT6`, `BUILD_TESTING=ON`, `ENABLE_UPDATERS=OFF`, `FOUNDATION_BUILD=OFF`, `USE_EXTERNAL_RAQM=OFF` and disconnected FetchContent. Compiler flags, foreign PATH/PYTHONPATH and registry Python selection cannot silently select another toolchain. Source-vendored libraqm is used.

The script configures, builds default targets and installs; it does **not** run CTest, package, launch, sign or publish. Root owns the `.github` workflow and actual Windows tests. Two workers and 180 minutes are a starting CI limit, not a measured completion promise.

Each run logs under `.brushquay/evidence/<timestamp-uuid>/`: `configure.log`, `build.log`, `install.log`, `native-build.json`. Upload only these metadata/log files. Never upload cache archives, the verified stage, native binaries or installers before source/license audit.

## Preservation and verification

Downloads are written to unique temporary files, checked against hash/size, then added to the cache without replacement. A bad existing cache entry is retained and rejected. Unknown cache entries, branch source revisions, incomplete dependency edges and contradictory frozen metadata fail closed.

Staging never uses `extractall`. It validates Windows paths, rejects traversal/device/ADS/case aliases and symbolic/special entries, and materializes only regular files or same-archive hardlinks. Identical files shared by packages record all owners; different contents at one path are a fatal conflict with no override. A new stage is published with native no-replace directory rename. Existing or late-created stages remain untouched; incomplete private stages are retained with their recovery path in the error.

`verify` rebuilds the expected file inventory from the pinned archives and compares actual stage contents, including rejecting extra files. Editing the installed receipt cannot authorize changed files. Input files are checked before and after native compilation. These are bounded no-replace/validation operations, not a guarantee against hostile processes concurrently altering all filesystem names and metadata.

## Local evidence and remaining work

See `verification/summary.json` and raw logs. On macOS, all 90 archives were downloaded and hash-verified, all 86 registry metadata documents checked, and 59,134 files staged and reverified. No native Windows executable was run locally. Twenty-one Python tests pass, including native no-replace directory tests on macOS and real archive fixtures. Windows branch execution remains for root's CI.

Remaining: actual native configure/compile and Qt tests; package/resource/source/license closure; compiler and dependency security updates; complete BrushQuay branding and removal of upstream services/Store identity; reusable presets and original native workspaces; their real export/source-preservation tests; Windows pen/scaling/runtime/install/upgrade/uninstall; MSIX/signing/WACK/Store/canonical-site release gates. The complete approved implementation continues after the baseline build is established.
