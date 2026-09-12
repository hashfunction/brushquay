# Explicit audited Bristlune packaging

Run this builder from the exact reviewed **source checkout**, after the native Windows build/runtime and all redistributed inputs have passed their separate review. It never installs packaging tools into the app, extracts NSIS, copies a shell extension, registers file associations or COM, signs, sends to a notary service, downloads, or publishes.

Identity is a required `.props` file matching `distribution/PackageIdentity.props.example`. All five values must be supplied; placeholders, paired `@…@` template markers in any field, and inherited Store identity values are rejected. XML field ordering does not affect rendering. Ordinary XML punctuation, Unicode and a single `@` in an email address are preserved as literal values. Root obtains the actual Name/Publisher from the product's Partner Center registration and the signing certificate workflow. The application ID `Bristlune` inside the manifest is only a local application identifier. Version and actual supported/tested Windows range are explicit release inputs. Product strings are Bristlune / hashfunction, and the sole capability is `runFullTrust`.

The audited runtime directory is read only. Its JSON inventory must have exactly:

```json
{
  "schema": 1,
  "sourceCommit": "<full source commit used to produce this runtime>",
  "licenseReviewComplete": true,
  "correspondingSourceComplete": true,
  "files": [
    {"path":"bin/bristlune.exe", "bytes":123, "sha256":"<actual 64 hex characters>",
     "license":"<reviewed SPDX expression>", "source":"<corresponding source bundle/location>"}
  ]
}
```

Every actual file must appear with its exact size/hash and reviewed license/source reference; missing, changed or extra files fail. The two booleans are an explicit review attestation by the release owner. The builder does not establish legal clearance, prove that an arbitrary supplied source reference corresponds to a binary, or authenticate the reviewer. Do not set them merely to get a build. Current dependency/resource inventory is incomplete, so no real approved runtime inventory is provided yet. This gate also requires closure of dynamic runtime dependencies beyond the application's own CMake install tree.

The SDK tool lock is a separate required JSON file:

```json
{
  "sdkVersion":"10.0.<reviewed SDK build>.0",
  "makepri":{"path":"C:\\<exact SDK path>\\makepri.exe", "bytes":123, "sha256":"<actual hash>"},
  "makeappx":{"path":"C:\\<exact SDK path>\\makeappx.exe", "bytes":123, "sha256":"<actual hash>"}
}
```

These example strings are intentionally unusable. Root must record exact Microsoft SDK provenance, license/version and actual executable hashes. The builder never chooses the newest installed SDK or searches PATH. It freezes the supplied records and re-verifies them before each invocation. Command execution still assumes a trusted packaging host: hash checking and process creation are not a cross-process executable compare-and-swap.

On Windows, with all those reviewed inputs available:

```powershell
python -m unittest discover -s packaging/windows/msix/tests -v
python build-tools/ci-scripts/build-windows-package.py `
  --install <audited-runtime-directory> --audit <runtime-audit.json> `
  --identity <approved-identity.props> --sdk-tools <sdk-tools.json> `
  --output <new-output-directory>
python packaging/windows/msix/verify_brushquay_msix.py `
  --package <new-output-directory>/Bristlune.msix `
  --record <new-output-directory>/package-record.json
```

The builder creates a private sibling stage, copies only verified bytes, generates original Store assets and manifest, runs makepri, then makeappx pack/unpack with no overwrite and normal semantic validation. It parses the generated, SDK-unpacked and independently read container manifests and compares the exact package name, publisher, version, architecture, application ID/executable/entry point, capability list and target-device-family values with the approved identity. Duplicate sections, surplus applications/dependencies/capabilities and application extensions fail. The parsed SDK/container identity fields are recorded in the evidence. Both SDK-unpacked files and the independent ZIP payload must also match the exact expected hashes before native no-replace directory publication. Hash agreement cannot authorize a different identity. It retains the payload, unpacked tree, unsigned package, SDK logs and JSON record. Failures retain the private recovery/evidence directory; a concurrent final output owner is preserved. The original runtime directory is never modified. Temporary stages must be on a trusted local filesystem; hostile ancestor renames and power loss can require manual recovery.

Assets are three original Qt-rendered PNG derivatives of `krita/pics/branding/Bristlune/sc-apps-bristlune.svg`, CC0-1.0 / Trieflow LLC, with exact hashes in `assets.lock.json`. They replace inherited Store artwork. Derivation used Qt 6.11.2 QSvgRenderer, AppleClang 21.0.0.21000101 and the committed headless art generator; no upstream mascot, embedded font or external artwork was used.

The 26 local tests use synthetic byte/ZIP/SDK fixtures and real filesystem publication. They do not run Microsoft's SDK or prove a valid installable package. Actual SDK pack/unpack, signed test install/upgrade/uninstall, DLL/resource closure, full Windows runtime tests and WACK remain mandatory. See Microsoft documentation for [MakeAppx commands and validation limits](https://learn.microsoft.com/en-us/windows/msix/package/create-app-package-with-makeappx-tool) and [MakePRI command options](https://learn.microsoft.com/en-us/windows/uwp/app-resources/makepri-exe-command-options).
