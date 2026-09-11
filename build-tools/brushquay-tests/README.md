# BrushQuay focused native tests

This harness compiles the actual preset store, file transaction and identity
sources without the rest of Krita. It uses the same `QT_USE_QSTRINGBUILDER`,
`QT_USE_FAST_CONCATENATION` and `QT_USE_FAST_OPERATOR_PLUS` definitions as the
product. Keep those definitions enabled: otherwise `auto` concatenation can
hide a deferred `QStringBuilder` behind an apparent string variable, and a
focused build can miss errors in the full native build.

Example local commands (Qt development libraries, CMake and Ninja required):

```sh
cmake -S build-tools/brushquay-tests -B .brushquay/domain-tests -G Ninja \
  -DCMAKE_PREFIX_PATH=/opt/homebrew/opt/qtbase
cmake --build .brushquay/domain-tests --target KisBrushQuayIdentityTest \
  KisExportFileTransactionTest KisExportPresetStoreTest --parallel 2
ctest --test-dir .brushquay/domain-tests --output-on-failure \
  --output-junit builder-tests.xml
python3 -m unittest discover -s build-tools/ci-scripts/tests
```

The Windows driver now compiles these three lightweight targets first, writing
`focused-build.log`, before the complete all-target build writes `build.log`.
A focused failure stops that invocation before the large build. The full build
is still mandatory. Exact discovery and execution of all five planned native
suites—identity, workspace, export preset integration, file transaction and
preset store—remain mandatory before installation. The identity/store/file
transaction targets need only the small preset library and Qt Core/Test/Xml;
the workspace and actual image-export tests require the full native product.
Metadata artifact globs already include both build logs. The workflow, locked
compiler/dependencies, package gates and all five native test gates are unchanged.

## Windows 34597712434 repair evidence

[Run 34597712434](https://github.com/hashfunction/brushquay/actions/runs/34597712434)
used public snapshot `12a49fee11df156e47707144b8398744e8ed1c52` (tree
`bf090d1cb9605f2291ef61bb3e29c8b865a25f8f`), corresponding to local source
`32f706f02aae627d02f3b2d92844a7296941d44c`. After about 85 minutes, the full build
failed at four `toStdString()` calls in `KisExportFileTransactionTest.cpp`:
the receivers were QStringBuilder expressions, not QString values. Native
product tests and installation did not complete. The identity-first build had
passed and 59,134 dependency files had been verified.

Adding the production concatenation definitions to this local harness reproduced
all four exact compile errors before any path repair. Materializing stored test
paths as `const QString` and materializing the real/alias paths before filesystem
conversion fixed the errors. The same audit materialized the added integration
tests' concatenated source/output paths, including the path captured by the
asynchronous export-completion callback. No production source or behavior changed.
Locked Qt 6.11.0 and local Qt 6.11.2 builders store forwarded rvalues by value;
this work does not claim a reproduced dangling-temporary failure on those Qt
versions. Concrete strings avoid deferred/reference-dependent values and remain
appropriate for the focused harness's Qt 6.5 minimum.

RED/GREEN records are under `.brushquay/domain-tests/`: `builder-configure.log`,
`builder-red.log`, `builder-green.log`, `builder-tests.xml` and CTest's
`Testing/Temporary/LastTest.log`. Local GREEN used Qt/QtTest 6.11.2, AppleClang
21.0.0.21000101, arm64 macOS 26.6.2, CMake 3.26.4 and C++17. All three actual
executables compiled and passed: 37 store, 18 file-transaction and five identity
Qt checks (these totals include each suite's init/cleanup checks). The two new
build-order/failure-propagation tests were RED before the compile seam existed;
all 25 dependency/configuration/driver tests are now GREEN. Python compilation,
MSIX fixture tests and `git diff --check` also pass.

The integration test translation unit and full native application have not been
rebuilt locally; they require the configured full Windows dependency graph.
This is not Windows build, runtime, GUI, workspace-resource, MSIX or release
acceptance. The next exact Windows run must still compile the complete tree and
execute all five suites. Native source/license closure and release gates remain
separate. Root owns public snapshots, native dispatch and release status.
