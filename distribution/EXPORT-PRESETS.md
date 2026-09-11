# BrushQuay export preset domain

The version 1 domain stores a UUID, Unicode display name, MIME type, extension and explicitly typed format options. The reviewed adapters are PNG and JPEG. Unknown formats, native document formats, arbitrary property names, paths, byte arrays, plug-in objects and unsupported value types are rejected. This boundary is deliberate: a format needs its own reviewed option adapter before appearing in the preset chooser. Ordinary advanced export retains the application's other available formats.

PNG/JPEG options use the existing export plug-ins' property names. Integers and Booleans survive JSON round-trips without the type erasure of legacy `KisPropertiesConfiguration::toXML()`. The background color has a bounded local KoColor XML representation, with no metadata, entities, external resources or profile paths. The native adapter must restore that property to KoColor and reject unavailable profiles/depths instead of silently substituting a different color space.

`KisExportPresetStore` defaults beneath the application's data directory in `brushquay/export-presets-v1.json`. It requires a successful load before Save or Delete. Malformed and future-version stores remain intact; an exclusive recovery copy preserves their exact bytes when writable. Every mutation stays blocked until the user explicitly repairs or moves the original and reloads. The UI must surface the original/recovery paths and provide Reload; it must not turn a load error into an empty writable store.

Writes use a sibling QSaveFile with direct-write fallback disabled. QLockFile serializes cooperating BrushQuay writers; loaded bytes are checked before and after staging to reject stale UI state. Cancellation leaves disk and memory unchanged. This is atomic file publication with cooperating-writer locking, **not** a cross-process compare-and-swap against arbitrary external writers. Export destinations need their separate no-replace and recovery protocol; this preference-store API never authorizes an image overwrite.

The Qt-only test target can run without opening a window:

```sh
cmake -S build-tools/brushquay-tests -B .brushquay/domain-tests -G Ninja -DCMAKE_PREFIX_PATH=/path/to/qt
cmake --build .brushquay/domain-tests
ctest --test-dir .brushquay/domain-tests --output-on-failure
```

The same test is registered as `libs-ui-KisExportPresetStoreTest` in the native build. Local verification uses macOS arm64 / AppleClang 21.0.0 / Qt 6.11.2; it does not qualify the Windows Qt 6.11.0 ABI. The raw logs currently report 34 QtTest passes: 32 test cases/data rows plus initialization and cleanup. The sanitizer run repeats the same cases; it is not an additional 34 distinct tests.

This commit supplies persistence only. Native widget integration, asynchronous PNG/JPEG export, overwrite/source protection, cancellation/outcome reporting and real plug-in fixtures remain required before this feature is complete.
