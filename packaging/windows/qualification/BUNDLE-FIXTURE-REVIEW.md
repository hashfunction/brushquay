# Windows bundle fixture path correction

Run34724510673, public source00506caab7f4ef8161462752b30c1486e09b3d14,
failed in `test_actual_bundle_cmake_install_preserves_only_other_original_bundles`
at the CMake configure subprocess. All55 MSIX/source/license tests passed.
Dependencies were not fetched, the product was not built and no installation
or export acceptance was reached.

The fixture wrote native `str(source)` directly into CMake's quoted
`add_subdirectory` argument. The Windows source path is
`D:\a\brushquay\brushquay\krita\data\bundles`. Replaying the unchanged actual
fixture with that exact Windows path through real CMake produces exit1 and
`Invalid character escape '\a'`. The original Windows exception retained the
subprocess exit/command but discarded its captured stderr, so the original
runner's full CMake diagnostic is unavailable.

The correction is fixture-only: serialize that source path with `as_posix()`.
Both CMake subprocesses still must exit0; assertion failures now retain their
command, stdout and stderr. The unchanged actual source CMake install rule
must still install exactly README and the three remaining original bundles
with exact original bytes. The omitted original SeExpr bundle remains present
and hash-checked in source.

A second invocation supplies a `PureWindowsPath` spelling of the actual source
path, allowing the real CMake parser and actual bundle installation to exercise
Windows separators even on POSIX. It fails before the serialization repair;
afterward both actual source/path variants and the three TLS safety cases pass:

```
python3 -m unittest discover -s packaging/windows/qualification -p test_optional_resources.py -v
```

Five tests pass. Production build, resource install rules, release binding,
source/notices, ownership and both installed workflow/export gates are unchanged.
Fresh exact Windows execution is pending review and dispatch.

Retained private originals/proof:

- `/private/tmp/bristlune-34724510673-failed.log`, SHA256
  `19d9f66460bb2ca3378b4b3154a120f51160b32ec9f951c0a6f4611feabb4f1a`.
- `/private/tmp/bristlune-34724510673-cmake-path-red.json`: exact unchanged
  fixture's generated CMake text and real parser stderr.
- `/private/tmp/bristlune-34724510673-fixture-red.log`: new actual installation
  regression fails before path serialization is corrected.
