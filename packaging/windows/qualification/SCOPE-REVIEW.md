# Installed qualification callback scope

The native Windows run [34683047674](https://github.com/hashfunction/brushquay/actions/runs/34683047674)
compiled and tested Bristlune successfully, then failed before package preparation.
Its retained installation receipt names `Assert-NoExistingProfile` as missing;
cleanup also could not resolve `Invoke-OwnedUninstall` or `Restore-GuiDisplay`.
No package registration, signing certificate or application activation was reached.

Each operation used `GetNewClosure()`, which binds the callback to a dynamic
module. When GitHub invokes `qualify.ps1` as a child script, those modules cannot
resolve the qualifier's script-local helper functions. The earlier lifecycle
test exercised synthetic callbacks and did not cross this function boundary.

The operations now remain ordinary script blocks. The lifecycle core invokes
them synchronously, while `Invoke-InstalledQualification` and its state variables
are still in scope. No operation is returned for later execution. All phase
ordering, ownership checks, exception handling and cleanup remain unchanged.

`test_operation_scope.ps1` reads the actual production callback assignments and
executes the real preflight and cleanup in a private script scope. A retained
profile sentinel must produce the exact preservation refusal before any Windows
mutation; every cleanup callback must then resolve, return normally and leave
the sentinel unchanged. This reproduced the missing-function error before the
change and passes after it. It runs in CI before the expensive native build.

Local verification: the scope regression, existing lifecycle failure matrix,
native input ownership guard and display restoration suites pass under
PowerShell 7.6.6. This is harness verification on macOS; a fresh Windows run is
still required for installed painting, export, reopen and cleanup. The previous
run remains recorded as failed and does not establish Store readiness.
