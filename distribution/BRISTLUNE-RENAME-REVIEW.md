# Bristlune 1.0.1 rename candidate

Source base: `5a7de71e347f65f9efca503d60724c8a8d68aeac`.
Approved name: Bristlune; canonical URL: `https://bristlune.trieflow.com`.

The customer display name, native executable/console stub/implementation DLL,
Windows version resources, package payload/output names, welcome/help/About UI,
original SVG wordmark, icon/resource names, new generated workspace names, current
notices and current documentation now use Bristlune. Product version is 1.0.1;
Windows binary/assembly version is 1.0.1.0. CMake's upstream ABI/version internals
remain intact.

The Qt application ID and data namespace remain `brushquay`, the singleton key
remains `BrushQuay1`, and configuration/log/resource/export-preset paths remain
unchanged. The assigned Store identity is `1659hashfunction.BrushQuay`, publisher
`CN=B6A2631A-FD32-45CC-AE12-82466975F528`, ApplicationId `BrushQuay`; package
presentation uses Bristlune and the assigned publisher display `hashfunction`.
The audited package builder still requires explicit approved identity, complete
runtime inventory, source/license attestations and exact SDK tools. Its manifest
validator additionally rejects stale product or publisher display strings.

The icon and splash raster bytes and the three MSIX PNG assets are unchanged.
Only current SVG titles and the runtime SVG wordmark change. Current artwork
hashes are refreshed and the retained raster derivation is documented without
claiming a new render. No old screenshot has been relabelled. The old upstream
README is retained byte-for-byte under `distribution/UPSTREAM-README.md`.
Immutable dependency locks, SPDX input evidence, historical Windows reports,
verification logs and original source attributions are unchanged.

## Evidence and limits

Historical run `34675482940`, public source
`e453edbb658166e064ab066452b7d97f71391399`, reports
`compiled_and_installed_not_packaged`, all six product Qt suites passed,
59,134 verified dependency-stage files, and unchanged input stage. Its native
receipt explicitly reports `licenseAuditComplete=false`. The three original
application binaries were `bin/brushquay.exe`, `.com` and `.dll`; their hashes
remain historical evidence. They do not qualify this renamed build.

Local checks passed:

```sh
python3 -m unittest discover -s build-tools/ci-scripts/tests -v
python3 -m unittest discover -s packaging/windows/msix/tests -v
cmake --build .brushquay/domain-tests --parallel 2
ctest --test-dir .brushquay/domain-tests --output-on-failure
git diff --check
```

There were 27 locked-build Python tests, 27 package Python tests, and five actual
local Qt suites. The rename regression was first red on the old display name
and domain, then green while proving the exact previous Qt profile path remains
selected. Three independent old/foreign manifest display mutations were red
before the corresponding strict validator checks, then passed by rejection.
Local package fixtures use synthetic bytes/SDK fixtures and do not claim a real
Windows MSIX or installed GUI success. No large download or full native rebuild
was performed on the low-space Mac.

The separately approved next candidate will stage only exact native build and
locked dependency inputs, build a disposable qualification package, retain
process/package/window/foreground ownership, create a document through the real
UI, paint a stroke, save/export/reopen and independently verify the files and
pixels, then normally close/uninstall/clean owned fixtures. It must retain source
and license completeness as false until their actual audit closes. The audited
public release gate is not bypassed by that disposable workflow. Native Windows
qualification, runtime/resource/source closure, genuine product screenshots and
public release remain pending.
