# BrushQuay original workspace provenance

Original layout recipes authored September 11, 2026 for Trieflow LLC, with the resulting layout-only resource files dedicated by Trieflow LLC to CC0-1.0. The generation code is GPL-3.0-or-later and retained in source. It copies no upstream workspace state or embedded art.

Required existing docker IDs, verified against this source: `ToolBox`, `KisLayerBox`, `PresetDocker`, `ColorSelectorNg`, `sharedtooldocker`, `History`, `OverviewDocker`. Native toolbar IDs: `mainToolBar`, `editToolBar`, `BrushesAndStuff`. These names identify existing native code; they do not import brush bundles, images, profiles or external assets.

Generation uses real `KisMainWindow` dockers and `KisWorkspaceResource::saveToDevice` format version 1. Each saved resource contains only its unique product name, base64 Qt window state and an empty settings element. It must contain no image, user or document path, machine identifier, executable command, credentials or external brush bundle.

**Generation/installation pending:** No placeholder `.kws` state is supplied. Run the native Windows generation/restore/resource-model test described in `build-tools/brushquay-workspaces/README.md`. Record its exact source commit, Qt/platform and hashes from the emitted JSON, review the two outputs, then add their explicit install entries. Full Windows switch/scaling acceptance remains separate from the automated save/restore checks.
