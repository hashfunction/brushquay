# Bristlune export preset domain

The version 1 domain stores a UUID, Unicode display name, MIME type, extension and explicitly typed format options. The reviewed adapters are PNG and JPEG. Unknown formats, native document formats, arbitrary property names, paths, byte arrays, plug-in objects and unsupported value types are rejected. This boundary is deliberate: a format needs its own reviewed option adapter before appearing in the preset chooser. Ordinary advanced export retains the application's other available formats.

PNG/JPEG options use the existing export plug-ins' property names. Integers and Booleans survive JSON round-trips without the type erasure of legacy `KisPropertiesConfiguration::toXML()`. The background color has a bounded local KoColor XML representation, with no metadata, entities, external resources or profile paths. The native adapter must restore that property to KoColor and reject unavailable profiles/depths instead of silently substituting a different color space.

`KisExportPresetStore` defaults beneath the application's data directory in `brushquay/export-presets-v1.json`. It requires a successful load before Save or Delete. Malformed and future-version stores remain intact; an exclusive recovery copy preserves their exact bytes when writable. Every mutation stays blocked until the user explicitly repairs or moves the original and reloads. The UI must surface the original/recovery paths and provide Reload; it must not turn a load error into an empty writable store.

Writes use a sibling QSaveFile with direct-write fallback disabled. QLockFile serializes cooperating Bristlune writers; loaded bytes are checked before and after staging to reject stale UI state. Cancellation leaves disk and memory unchanged. This is atomic file publication with cooperating-writer locking, **not** a cross-process compare-and-swap against arbitrary external writers. Export destinations need their separate no-replace and recovery protocol; this preference-store API never authorizes an image overwrite.

The Qt-only test target can run without opening a window:

```sh
cmake -S build-tools/brushquay-tests -B .brushquay/domain-tests -G Ninja -DCMAKE_PREFIX_PATH=/path/to/qt
cmake --build .brushquay/domain-tests
ctest --test-dir .brushquay/domain-tests --output-on-failure
```

The same test is registered as `libs-ui-KisExportPresetStoreTest` in the native build. Local verification uses macOS arm64 / AppleClang 21.0.0 / Qt 6.11.2; it does not qualify the Windows Qt 6.11.0 ABI. The raw logs currently report 34 QtTest passes: 32 test cases/data rows plus initialization and cleanup. The sanitizer run repeats the same cases; it is not an additional 34 distinct tests.

This commit supplies persistence only. Native widget integration, asynchronous PNG/JPEG export, overwrite/source protection, cancellation/outcome reporting and real plug-in fixtures remain required before this feature is complete.

## Export destination transaction

`KisExportDestination::capture` resolves the chosen parent once, records directory identities, and captures an existing regular target's volume/device, full file ID/inode, size and SHA-256 **before** replacement confirmation. The renderer receives a private sibling path from `KisExportFileTransaction`; it never writes directly to the user's destination. The transaction protects original source basenames, canonical parent aliases, hardlink identities and captured source bytes.

After successful rendering, an approved old target moves with a native no-replace operation to `previous-output.<extension>` in the run directory. The moved file must still match the approved identity/content. New output is published with another no-replace move. Cancellation/failure restores the old file without replacing any late owner. If a collision prevents restoration, the previous file, late owner's file and staged render are retained. A successful replacement deliberately retains the old file for recovery. There is a short interval when the approved destination name is absent; a process crash can leave the previous file in the run directory.

This is a bounded preservation protocol, not cross-process atomic conditional replacement. Source/parent checks detect observed changes but cannot freeze unrelated filesystem processes. If another process renames an entire parent directory, retained run files move with it and the originally recorded path may no longer resolve. The transaction never searches for and deletes a replacement file. `published` records that the new file was moved into place; a subsequent verification error remains an error even when `published` is true.

The standalone suite adds 16 filesystem cases/data rows (18 QtTest passes including initialization/cleanup), repeated with ASan/UBSan. These tests cover real native macOS file operations, not real image rendering; the application controller must wait for actual plug-in completion and validate a decodable PNG/JPEG before calling `finish(true)`.

## Native integration (awaiting full Windows compilation)

The File menu action is registered in the actual `kritamenu.action` and `krita5.xmlgui` resources. `KisExportPresetDialog` uses each installed PNG/JPEG plug-in's real configuration widget, offers New/Save/Update/Delete/Reload, and returns a copied preset without exporting. Save and Delete remain disabled after a load failure. The new chooser explicitly disables its built-in overwrite question; an asynchronous identity/content capture precedes Bristlune's replacement question, and that exact consent snapshot reaches the worker. Existing KoFileDialog callers retain the default overwrite prompt.

`KisExportPresetJob` uses `KisDocument::exportDocument` and filters its actual `sigCompleteBackgroundSaving` by the private staged path. It keeps native export warning/options dialogs. Successful rendering is decoded and checked for expected format/dimensions off the GUI thread before publication; input hashing and final publication also run off the GUI thread. Document paths, file-layer paths and external reference-image paths are protected. Closing the source cancels publication. Outcomes distinguish cancelled/failed/unpublished from published output, retain recovery paths, and update last-export state only after verified publication. The underlying document's ordinary completion notification still concerns its private rendering stage; the final Export Result dialog reports destination publication separately.

The native codec preserves the background color's channel depth, installed profile and opacity; unknown/missing profiles and changed property types fail closed. Integer color channels are range-checked before native parsing. These checks have a local RED/GREEN test, but the native codec and plug-in integration are not yet claimed compiled on macOS or Windows.

`KisExportPresetIntegrationTest` contains nine actual native cases/data rows: PNG/JPEG codec/widget round-trips, unsafe format rejection, real dialog Save/Select/Apply without export, corrupt-store GUI mutation blocking, a late file created from the real completion signal, source closure, and generated PNG/JPEG export with source path/modified-state/bytes preservation. It uses generated 32×24 solid-color inputs. This full-application test is registered but **has not yet run**; the Qt-only harness correctly has no such target. Its RED target-absence log is not a native runtime result.

The standalone persistence suite now has 35 cases/data rows (37 passes including init/cleanup); the transaction suite has 16 (18 with init/cleanup), totaling 51 distinct cases/data rows. Sanitizers repeat those same cases. Windows compiler/API/linkage, actual plug-in runs, confirmation/cancellation UX, keyboard/accessibility and scaling remain gates.
