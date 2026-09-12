# Bristlune native installer host correction

Run 34689838285 completed the native build and product tests, then failed before packaging or installation. The actual installed receipt reports Appx module load error 0x80131539 when Get-AppxPackage is imported by PowerShell 7; cleanupErrors is empty. The workflow used shell pwsh on windows-2022.

Use native x64 Windows PowerShell 5.1 for this original Appx installation lifecycle. An explicit host guard replaces the PowerShell-Core-only IsWindows variable and verifies original Appx cmdlets without remoting proxies. The same native host now runs actual read-only package queries and existing input/display/lifecycle/scope tests before the long product build. Other build steps keep their original host. Package identities, runtime, artwork, ownership, signing, GUI interactions, file oracles and cleanup are unchanged.

The new actual-host fixture first failed because the explicit host boundary did not exist, then passed the unsupported-host refusal on macOS. Existing actual callback/sentinel and lifecycle tests pass. All 32 Python installed-qualification tests pass. Native PowerShell 5.1 module execution and installed painting remain pending the fresh Windows run; this change is not an installation success claim.

Microsoft documents Appx as Windows PowerShell cmdlets: https://learn.microsoft.com/en-us/powershell/module/appx/ . PowerShell 7 compatibility can involve Windows PowerShell remoting for incompatible modules; this lifecycle selects the native host to retain original package objects: https://devblogs.microsoft.com/powershell/announcing-PowerShell-7-0/ .
