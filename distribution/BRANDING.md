# Bristlune identity and native assets

The independent product is Bristlune 1.0.1, published by Trieflow LLC, with canonical product/privacy/support URLs on `https://bristlune.trieflow.com`. Renamed Windows qualification and website verification remain separate gates.

Native entry points are `bin/bristlune.exe` and `bin/bristlune.com`; the implementation DLL is `bristlune.dll`. CMake target and API symbol names retain their upstream names to preserve linkage. The application ID and Qt data location are `brushquay`; the singleton key is `BrushQuay1`; configuration, display settings and diagnostic log basenames use `brushquay`. Installed read-only resource namespaces and the KRA document format remain compatible with the original resource system. No existing Krita data is migrated or overwritten.

The assigned Store identity remains `1659hashfunction.BrushQuay`, publisher `CN=B6A2631A-FD32-45CC-AE12-82466975F528`, and ApplicationId `BrushQuay`. Existing BrushQuay profiles and export-preset stores retain their exact locations and format; no data migration accompanies the display rename.

The application icon, wordmark and splash use original source-authored assets under `krita/pics/branding/Bristlune`, with CC0 dedication, derivation notes and SHA-256 hashes. Upstream mascot and sponsor-logo resources are no longer compiled into the entry point. This does not clear the remaining brush, profile, interface-icon, plugin or third-party asset inventory.

Welcome-page news, donation and updater initialization is removed. The locked native build disables updaters and foundation-only components. The support action opens the canonical support page without sending diagnostic data. Diagnostic logs remain local and can contain machine details and file names; users review them before sharing. Copyright, GPL notices, developer and historical upstream sponsor credits remain. No Store identity is supplied by this change; packaging migration must require root-provided approved identity values.

Local tests compile the actual original-artwork resource collection, verify the application data path separates from Krita, and check canonical URL constants. Native executable startup, offline networking capture, tablet support and UI/scaling are pending Windows qualification.
