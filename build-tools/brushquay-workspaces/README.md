# Generate original native BrushQuay workspaces

The source-authored layout recipes in `libs/ui/KisBrushQuayWorkspaceLayouts.h` arrange real application dockers; they are not imported upstream workspace files. Both keep the native file/edit/brush-control toolbars and toolbox. Illustration places color/overview, layers, and presets/history in a right-side stack. Inking shows layers/tool options and presets while hiding color/history/overview. No document, brush resource, artwork or user path is included.

The registered native `KisBrushQuayWorkspaceTest` creates a real `KisMainWindow`, arranges the dockers, saves through `KisWorkspaceResource`, reloads its XML, repeatedly restores state, checks native dock visibility/areas, and imports it into the real resource model without overwrite. The missing-docker case must leave the original window unchanged. This requires the full compiled application, plugins and test resources.

On the accepted Windows build, set these values for **that test only**:

```powershell
$env:BRUSHQUAY_WORKSPACE_OUTPUT = '<new absolute evidence directory>/workspaces'
$env:BRUSHQUAY_WORKSPACE_SOURCE_COMMIT = '<full 40-character source commit actually compiled>'
ctest --test-dir .brushquay/build -R KisBrushQuayWorkspaceTest --output-on-failure
```

The test writes `BrushQuay_Illustration.kws`, `BrushQuay_Inking.kws`, and one provenance JSON for each using exclusive creation. The JSON records platform/Qt version, exact generation source commit and SHA-256, with visual acceptance explicitly false. These are original source/evidence artifacts, not native dependency redistributions. Copy them back for source review and explicit CMake installation only after native generation succeeds. Then verify installed lookup using the real resource model and switch both workspaces at 100/150/200% scaling on Windows. Save/restore tests are not that visual acceptance.

The local `CMakeLists.txt` here only compiles the exact Qt Widgets layout implementation; it does not execute a QApplication or open a window. On the locked Mac it was used to catch compiler errors after the missing-header RED. No generated `.kws` file, full native application test result or accepted Windows layout is claimed yet.
