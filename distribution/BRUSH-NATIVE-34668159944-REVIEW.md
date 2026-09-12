# BrushQuay native run 34668159944 review

Source baseline: `88c818b6f3513196d9b22a0e5630c8294bb0fbbf`, public snapshot
`f661a48a`. The full Windows Qt 6 build completed. Four required suites passed;
WorkspaceTest and ExportPresetIntegrationTest failed.

## Retained evidence and exact assertions

GitHub artifact `10291219389`, `BrushQuay-Windows-foundation-qualification`, was
131,369 bytes. Logs/metadata are under
`/private/tmp/brushquay-34668159944-review`; no application/native archive was
downloaded. The artifact's small generated workspace payload was removed from
the local audit copy; its provenance JSON remains. Exact Qt log hashes:

- `KisBrushQuayWorkspaceTest.log`:
  `e2f6ce8cbd7b637c7e787f2eb457708cd5d574808fbda5bc92c11f80c675b96f`.
- `KisExportPresetIntegrationTest.log`:
  `15c4014a81a8de7eaf955b6c4e936ac488b6e8d9a6ed4b92e158b60a9efca53e`.

Both `initTestCase` checks passed, including early plugin-path values, discovery,
all required docker factories, and actual PNG/JPEG export-filter construction.
The prior initialization correction worked. Fontconfig/OpenGL/font warnings are
not the failing assertions and are not used to infer these causes.

Workspace: `originalLayoutsSaveReloadAndRestore(Inking)` at baseline line 90
expected `color->isHidden() == true` but got false. Illustration passed, giving
five passing cases and one failure overall. The layout recipe removed inactive
dockers from QMainWindow before saving state. Removed dockers have no serialized
visibility entry; Qt reintroduces them during restore. A tiny actual Qt Widgets
probe reproduced the same transition: ColorSelectorNg was hidden with
NoDockWidgetArea immediately after arranging Inking, then visible in the right
area after each restore. A fresh destination window also exposed Illustration's
inactive tool-options docker and the unrelated hidden fixture docker.

Export: PNG and JPEG option round trips fail at baseline line 83 in
`KisExportPresetCodec::restore`, returning "This preset's export format or
extension is unavailable." The same rejection prevents generated PNG/JPEG
publication. Dialog selection, late-owner, and cancellation assertions also
fail before the intended successful export lifecycle has been established;
the run reports four passing cases and seven failures.

The locked Qt header has `QT_FEATURE_mimetype_database -1`. Its SHA256
`4308df9c735810ae76671c075249c1f37f3caa1bac7d00c7c22d6483739d7da6` matches the
verified local stage manifest's ext_qt file record. Production
`krita/CMakeLists.txt` explicitly embeds `mime-database.qrc` for Qt 6. The GUI
integration executables link kritaui/kritaplugin, not that application resource.
KisMimeDatabase relies on QMimeDatabase for PNG/JPEG suffixes, so filter discovery
alone cannot satisfy the codec's MIME/suffix guard in this process.

## Changes

The original workspace recipe now reattaches inactive dockers and keeps them
hidden before save. Qt can serialize their visibility. The real native workspace
test additionally checks all layout-specific inactive dockers after restore.
The new focused test restores into a different, initially visible topology three
times, checks active dock placement, and preserves the existing no-mutation
requirement when a required docker is absent. No QMainWindow restore behavior or
workspace acceptance assertion was bypassed.

Both GUI integration executables now embed the same existing application MIME
resource through a small shared CMake helper. Startup checks require that
resource before the first MIME query; the native export preflight separately
checks supported MIME types and suffixes, yielding a precise boundary error if
configuration differs again. The focused resource test compiles that exact qrc
and verifies real QMimeDatabase PNG/JPEG names, suffixes and file classification.
No dependency, MIME mapping, exporter, preset validation or destination rule was
changed.

## Verification and limits

RED on macOS Qt 6.11.2: both layout data rows failed with inactive dockers visible
after native restore, and the MIME test failed because the application resource
was absent at startup. GREEN after the changes: all five focused Qt executables
pass, including repeated actual offscreen QMainWindow save/restore. All 27 Python
CI-script tests pass. `git diff --check` passes.

Commands from the source root:

```sh
cmake -S build-tools/brushquay-tests -B .brushquay/domain-tests -DCMAKE_PREFIX_PATH=/opt/homebrew/opt/qtbase
cmake --build .brushquay/domain-tests --parallel 2
ctest --test-dir .brushquay/domain-tests --output-on-failure
python3 -m unittest discover -s build-tools/ci-scripts/tests -p 'test_*.py'
git diff --check
```

The required native six-suite set, 180-second timeout, resource-model import,
workspace provenance, pixel/file publication tests and failure assertions remain
in place. Windows workflow YAML, early plugin initialization, native build and
acceptance runner are unchanged. No full local product rebuild was attempted.
The full Windows integration suites must still run against this candidate;
follow-on export behavior and generated workspace visual acceptance are not
claimed from the focused macOS checks. Root owns independent review, public
snapshot/push and the next native run. No status/site/publication change is part
of this commit.
