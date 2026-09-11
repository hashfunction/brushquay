# BrushQuay identity and native assets

The independent product is BrushQuay 1.0.0, published by Trieflow LLC, with canonical product/privacy/support URLs on `https://brushquay.trieflow.com`. This is source metadata, not a Store registration or verified website deployment.

Native entry points are `bin/brushquay.exe` and `bin/brushquay.com`; the implementation DLL is `brushquay.dll`. CMake target and API symbol names retain their upstream names to preserve linkage. The application ID and Qt data location are `brushquay`; the singleton key is `BrushQuay1`; configuration, display settings and diagnostic log basenames use `brushquay`. Installed read-only resource namespaces and the KRA document format remain compatible with the original resource system. No existing Krita data is migrated or overwritten.

The application icon, wordmark and splash use original source-authored assets under `krita/pics/branding/BrushQuay`, with CC0 dedication, derivation notes and SHA-256 hashes. Upstream mascot and sponsor-logo resources are no longer compiled into the entry point. This does not clear the remaining brush, profile, interface-icon, plugin or third-party asset inventory.

Welcome-page news, donation and updater initialization is removed. The locked native build disables updaters and foundation-only components. The support action opens the canonical support page without sending diagnostic data. Diagnostic logs remain local and can contain machine details and file names; users review them before sharing. Copyright, GPL notices, developer and historical upstream sponsor credits remain. No Store identity is supplied by this change; packaging migration must require root-provided approved identity values.

Local tests compile the actual original-artwork resource collection, verify the application data path separates from Krita, and check canonical URL constants. Native executable startup, offline networking capture, tablet support and UI/scaling are pending Windows qualification.
