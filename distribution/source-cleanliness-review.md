# Original source-state evidence at native boundaries

Run `34695741111`, attempt 1, compiled and installed Bristlune and passed all six
required native Qt suites. Packaging then refused the checkout with
`Qualification requires the exact clean committed source`, before MSIX creation
or installation. The native and installed-qualification records both name
source `af5048657c34455c6c3997c1efc19696586db9e7`, tree
`998e647f3ac3baf0bb59be8b2e97f01da292a1fa`. Native inputs were unchanged and all
59,134 staged input files verified. These are native build results, not an
installed consumer, MSIX or source-distribution clearance.

The original native builder checked source status only before configuration.
The later packaging check discarded Git's status output. Neither retained the
dirty path list, so the exact writer cannot be recovered from this run. Original
native metadata SHA-256 is
`0d998e7bd863504e8d9e76025899015d8aa065945601ada75203126e316c684d`;
the private failed log SHA-256 is
`5c45318a9c4d790df782380dc95e196197bfc777b974ad27fbd8825b25d5de9c`.
The original files remain in the private run collection, without rewriting or
publishing the complete logs.

The reviewed paths for builds, tests, generated translations, installation,
qualification and probe compilation are already below ignored `.brushquay/`
directories. The native translation-generation log points to KI18N's
`build-tsfiles.cmake`, whose output uses `CMAKE_CURRENT_BINARY_DIR`. This does not
prove those generators wrote into the checkout. There is no evidenced specific
output to relocate yet. This candidate adds observation; it does not reset
source, discard edits, change ignores or relax the clean-source requirement.

`source_state.py` records the original HEAD/tree and NUL-delimited Git porcelain
bytes before configuration and after configuration, focused compilation, full
compilation, the six native tests, and installation. The packaging boundary
writes `source-before-package.json` before retaining the same refusal. A native
command failure gets a separate final observation while preserving its original
exception. The existing metadata artifact includes these JSON files; each native
observation is also bound by size and SHA-256 in `native-build.json`.

For Git-returned paths only, the observation records committed object identity,
mode, byte count, SHA-256 and line-ending counts alongside the original working
file observations. Raw diff, numstat and index line-ending metadata retain mode,
rename, deletion and CRLF distinctions without copying source contents into the
receipt. Files are read only after path and regular-file checks; symlink and
Windows reparse targets are never hashed. Git output is limited to 2 MiB, detailed
path observations to 256, and each hash read to 64 MiB, with explicit omissions.
Existing receipts are never overwritten. A final HEAD/status read detects a
changing checkout. Any dirty status still fails, including paths outside the
detailed observation limit.

Local verification:

```sh
python3 -m unittest discover -s build-tools/ci-scripts/tests -v
python3 -m unittest discover -s packaging/windows/qualification -v
git diff --check
```

The two suites pass 34 and 33 tests. The six new source-state cases use real Git
repositories and file bytes: clean source, CRLF-only changes, untracked output
and deletion, wrong commit and exclusive evidence, foreign symlink refusal,
and index mode plus rename identity. The actual packaging helper retains the
original dirty-file hashes and leaves those bytes unchanged. The new compile
boundary case proves that an observed source violation after the focused build
stops the full build; native command execution is mocked only for that sequence
test. The initial new observation tests failed before the helper existed.

The next Windows run must identify the first non-clean phase and exact paths.
Any subsequent repair should address only the proven producer, with a regression
for its output location or byte mutation. No new Windows result or successful
installed lifecycle is claimed by these local tests.

## First observed producer and repair

Run `34704767479`, public source `33d0e89a5545917ed0d3057408cbd2a0891435e1`,
stopped immediately after successful configuration. The original 552-byte
before-configure record was clean (SHA-256
`3da682005e2bedc745700c22ca719049179604ff62009de247296b0241460058`).
The 950-byte after-configure record (SHA-256
`ad431d0e7e64fae89926a49db92a2fa7a211b2252c59e19cf0c81f5cbd432154`)
identified exactly one untracked output: `test.tif`, 50 bytes, SHA-256
`c421e871ac8abe5483fd31b3da1d784d2e6d532e68c6216f6381c870e5ce2e18`.
The commit remained unchanged. No full compile was started in this run.

`cmake/modules/CheckLibTIFFPSDSupport.cmake` runs a native TIFF write probe
whose `TIFFOpen` uses relative `test.tif`. The builder launched configuration
with the source directory as its working directory. Configuration now runs
from its already-created build directory, with the same absolute source,
build, dependency and install arguments. The probe output stays with generated
build files. No source file is removed, overwritten, ignored or reset; the
per-phase source checks remain intact.

The original, unchanged TIFF module was separately executed through actual
CMake and host libtiff 4.7.2. The former source working directory produced the
same 50-byte TIFF and exact SHA-256 as Windows. The corrected production
configuration helper produced that same file under the build directory and
preserved the original source TIFF and CMake project bytes. This is a native
host reproduction of the output location, not a new Windows build claim.
The private original logs and verification are retained under
`/private/tmp/bristlune-real-tiff-probe-34704767479`.

The permanent regression runs a real CMake child through that production
helper, proves its output location, and protects an existing source file of
the same name. The build-tool suite now passes 35 tests; all 33 packaging
qualification tests still pass. Fresh Windows compilation, installed painting
and export, complete source delivery and final Store packaging remain pending.
