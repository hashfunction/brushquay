# Bristlune native source materials

This directory traces the Windows dependency lock to its source inputs and
prepares verifiable **source-only materials**. It does not clear a binary for
distribution. `correspondingSourceComplete` and `licenseReviewComplete` remain
false, including in every collection receipt. The audited MSIX builder's
separate release-owner attestations are unchanged.

## What is established

`inventory.json` binds all 90 locked archives to the exact recipe commit
`993af62fdf291eaec05a1824d9b420782717fc44`, tree
`c7c208f011a7123df1b99d6fe7f59276b5025e84`. The 86 `ext_*` packages have 94
reviewed Windows x86_64 MinGW/Clang input declarations. The other four records
are the pinned LLVM-MinGW, CMake, Ninja and Python SDK inputs. Package-registry
`sourceCommit` is a **recipe** revision; it is never substituted for a library
source revision.

`windows-selection.json` records the zero-based source-call selection and exact
recipe file digest. `inventory_native_sources.py` reads Git objects from that
immutable tree; it does not run CMake or interpret its conditionals. The complete
498-file recipe tree, including patches, overlays, configuration and scripts, is
collected. Preserve the original Windows conditionals and patch order when
rebuilding; the collection includes other-platform patches too.

The actual original [Windows dependency build](https://invent.kde.org/packaging/krita-deps-management/-/jobs/4983784)
and its source-event excerpts establish the Qt submodules and OpenColorIO nested
inputs in `resolved-inputs.json`. That document distinguishes an immutable recipe
pin, a build-observed short revision resolved to a full commit, an unproved build
default, and an unresolved moving branch. The follow-up materialization now
contains 117 verified archives: 83 source tarballs/overlays and 34 Git trees.
See [MATERIALIZATION.md](MATERIALIZATION.md) for receipts, exact provenance gaps,
notice findings and commands. The downloaded OpenColorIO 2.5.1 source was SHA-256 checked
against its recipe; the five retained `Install*.cmake` excerpts come from those
exact bytes and preserve their upstream headers.

All 59,134 staged dependency/tool files were re-read against their original
locked archives and registry metadata. Reusing the actual qualification runtime
selector produces **4,235 dependency files, 1,092,903,138 bytes**, owned by 68
packages. This is a dependency selection, not an observed final installed app.
The other 22 package records remain in scope: libaom, Highway, x265 variants and
header libraries can contribute compiled code without a separate runtime DLL.

The generated `dependency-runtime-files.json` records every selected path,
size, SHA-256 and archive owner. Its digest is bound in `inventory.json`.
`notice-candidates.json` records 180 possible notice files with original paths
and owners. The notice archive preserves their exact text. Filename discovery
is intentionally **not** a determination of applicable licenses or a complete
notice set; several dependencies and application resources need additional
notices from their source archives.

## Recreate and verify the available collection

Use a local trusted filesystem with Python 3.10 or later and Git. No network or
dependency execution occurs in these commands. Existing outputs are refused.
The recipe repository need only contain the exact pinned Git objects; edits in
its working checkout cannot change the collected source. On Windows use a
normal local directory without reparse points. On macOS use `/private/tmp`
rather than its `/tmp` symlink for output examples.

From the application source root:

```sh
python3 -m unittest discover -s distribution/native-source -p 'test_*.py' -v
python3 distribution/native-source/inventory_native_sources.py \
  --recipes /absolute/path/to/krita-deps-qt6 \
  --cache .brushquay/cache --stage .brushquay/locked \
  --output /absolute/new/source-materials --check
python3 distribution/native-source/native_source.py verify \
  --archive /absolute/new/source-materials/Bristlune-native-recipes.tar \
  --plan /absolute/new/source-materials/recipes-source-plan.json
python3 distribution/native-source/native_source.py verify \
  --archive /absolute/new/source-materials/Bristlune-native-notice-candidates.tar \
  --plan /absolute/new/source-materials/notices-source-plan.json
```

The first command reproduces `inventory.json` and refuses any difference with
`--check`. It reconstructs the binary input inventory from the original archive
bytes before reading selected files; an edited installed receipt is insufficient.
It creates deterministic, uncompressed PAX tar files, source plans, full file
inventories and collection receipts. Tar timestamps and ownership are zeroed;
Git executable modes are preserved. No `export-ignore` or `export-subst`
attribute can silently omit/change source, because Git blobs are read directly.

`native_source.py verify` needs the **separate reviewed plan**, not a plan trusted
only because it appears inside the archive. It verifies each member and rebuilds
the canonical tar stream into a hash sink without extracting it. It rejects
missing/extra/duplicate members, traversal and Windows path aliases, links,
special files, altered modes, timestamps, source bytes, embedded manifests and
trailing data. Output publication uses an exclusive hard link after independent
readback, so a concurrent output owner is preserved.

For additional ordinary Git source trees without gitlinks or symlinks:

```sh
python3 distribution/native-source/native_source.py git-collect \
  --repo /absolute/source-repository --commit <full-reviewed-commit> \
  --tree <full-reviewed-tree> --prefix <component-name> \
  --output /absolute/new/component.tar --plan /absolute/new/component-plan.json
```

Unmaterialized Git submodules are refused. In particular, a Qt superproject
archive by itself is insufficient. Collect the superproject and the eight exact
module source archives identified in `resolved-inputs.json`, and preserve the
path-to-commit mapping and offline assembly instructions. Review any further
gitlinks or nested downloads in each source archive. The original Qt recipe
sets `GIT_SUBMODULES_RECURSE false`; it does not build every Qt repository.

Other verified upstream source tarballs, source overlays and license texts can
be collected with `native_source.py collect --plan <reviewed-plan.json>
--materials <directory> --output <new.tar>`. The materials directory must contain
exactly the plan's member paths. Plans use the same schema as the generated
recipe/notice plans: each file has explicit bytes, SHA-256 and mode, and
`provenance` identifies its immutable source and original recipe hash. Do not
reclassify a prebuilt DLL archive as source. First verify each download against
the recipe or independently reviewed producer source pin, record its actual
SHA-256/size, and inspect nested source/patch requirements. Legacy MD5/SHA1 recipe
checks and branch names are identified in the inventory; neither constitutes a
newly invented strong source pin.

## Remaining source and notice work

1. Obtain the original resolved revisions/source cache for **libvpx `meson-2`**
   and **gperf `meson`**, or a producer receipt that proves the corresponding
   source. The original log prints branch names and versions, not these commits.
   Today's branch tip is not proof of the 2026-09-08 build's source.
2. Preserve and publish the materialized source archives and Git inputs, including
   all eight Qt module commits, Qt's bundled third-party source/notices, ANGLE's
   separate Google-zlib input, and the five libraries compiled into OpenColorIO. Review
   the retained source notice candidates for actual distribution applicability. Preserve
   OpenColorIO's pystring CMake patch and its nested build options. Its minizip-ng
   build disables additional fetching and uses the separately locked zlib.
3. Trace the **opaque prebuilt inputs** to their source/build and notice records:
   curl-for-win OpenSSL 1.1.1l_4; XZ 5.2.6 Windows; DrMinGW's libdwarf/zlib and
   separately copied Microsoft debug DLLs; CPython 3.13.5's embedded runtime,
   PCbuild external libraries and VC runtime; and the actually selected gettext
   translations/CLDR and gettext library. Microsoft DLLs need their applicable
   redistribution permission and notices; this is not a demand for unavailable
   Microsoft source. Determine which components require source versus notices
   under their actual licenses, and record the combined-license assessment.
4. Include the exact final Bristlune public source, application build scripts,
   relevant generated configuration and rebuild/install instructions. Reconcile
   the renamed run's complete installed-tree inventory with the dependency
   inventory, then review the actual application resources (including bundle
   internals, ICC profiles, patterns, fonts and translations). The old candidate
   `resources.csv` contains `NOASSERTION` fields and is not a completed review.
   Resolve the original dependency CI helper revision if those scripts are used
   to recreate that build. Identify normal system build tools accurately;
   blanket byte-identical reproduction of every tool is not this task's gate.
5. Root publishes the immutable source assets and notices, downloads them
   without authentication, verifies every hash and records durable URLs. Only
   after the final file-to-source/license review can the existing audited MSIX
   gate receive a truthful approved runtime inventory.

The corresponding-source definition and delivery conditions are in the
application's preserved [GPLv3 text](../../COPYING), sections 1 and 6. Source
means the preferred form for modification plus applicable build/install scripts,
not a recipe repository pointing at unknown inputs. Qt likewise documents
delivery of the actual library source and modifications, applicable notices and
users' ability to replace/relink the library in its [open-source obligations](https://www.qt.io/development/open-source-lgpl-obligations).
These materials do not introduce a requirement for a byte-identical binary
rebuild, grant third-party rights, or attest that all final distribution terms
have been reviewed.

## Evidence handling

`evidence/original-windows-source-events.json` contains only allowlisted source
events with original line numbers and a hash binding to the downloaded upstream
log. **Do not publish the complete upstream job log:** its runner environment
contains unrelated historical credential-shaped values. No such environment
records are needed in the source collection. The small Qt metadata and LLVM/
OpenColorIO source excerpts have their provenance in `resolved-inputs.json` and
the review report. Historical native receipts retain their original identity
and outcome; none is rewritten as a Bristlune installed-workflow success.
