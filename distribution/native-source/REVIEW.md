# Bristlune native source trace and collection review

Source base: `02947962463041a3d4432444e1958f8c106f68a7`. Scope is confined to
`distribution/native-source/`. No product, installed qualifier, CI, package
gate, parent release status, website, Store operation or live Windows run changed.

The source/inventory tooling is ready for independent review. **Complete native
corresponding-source delivery and license clearance remain open.** No assets
were published. Current renamed Windows run `34683047674` was not inspected or
altered by this work. The retained historical application build
`34675482940`/public `e453edbb658166e064ab066452b7d97f71391399` establishes only
the previous native build with the same immutable dependency lock.

## Findings and available material

- Reverified all **90 locked archives and 59,134 installed input files**, including
  registry metadata, archive hashes, file ownership and exact staged bytes.
- Traced **86 dependency recipes / 94 selected Windows source calls**. Four
  additional tool packages remain represented. Source URLs, recipe hash fields,
  full Git pins, legacy weak hashes and opaque prebuilt inputs are distinguished.
- The existing selector yields **4,235 dependency runtime files / 1,092,903,138
  bytes / 68 owning packages**. Its exact code hash and full generated file-map
  hash are retained. Zero selected DLLs do not exclude compiled/static inputs.
- Retrieved the original upstream Windows dependency job `4983784`, pipeline
  `1342225`, recipe commit `993af62fdf291eaec05a1824d9b420782717fc44`. Kept only
  140 allowlisted source events from its 18,045,589-byte log in source. The full
  upstream log includes unrelated runner environment values and must not be
  republished; its original archive/member hashes are retained for provenance.
- Confirmed **Qt's eight exact submodule commits** against both the immutable
  superproject Git tree and original Windows checkout log. Confirmed five
  additional libraries built inside **OpenColorIO 2.5.1**: Expat 2.7.2, yaml-cpp
  0.8.0, pystring 1.1.4, Imath 3.2.1 and minizip-ng 4.0.10. Full commits and build
  instructions are recorded. Downloaded the actual 14,131,392-byte OpenColorIO
  source and verified SHA-256 against the original recipe before reading its
  nested build files. JPEG XL's original configure log resolves to the locked
  system Highway/Brotli/LCMS2 inputs.
- **libvpx `meson-2` and gperf `meson` remain unresolved original commits**. The
  original log reports only a branch and version. No present-day branch head is
  substituted. Exact gitlink records for the fetched immer/lager/zug helper
  submodules are retained for later build-source inclusion review.
- Original runtime inputs include opaque **curl-for-win OpenSSL 1.1.1l_4**, XZ
  5.2.6 Windows, CPython embedded runtime and DrMinGW's separately copied
  Microsoft debug DLLs. These need their actual source/build or applicable
  redistribution/notice records, not a false generic GPL label. More source and
  notice work is detailed in `resolved-inputs.json` and `README.md`.

The deterministic available collections are in
`/private/tmp/bristlune-source-collection-final/`:

| Collection | Members | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| `Bristlune-native-recipes.tar` | 498 | 1,474,560 | `0bb43c0db73c428fa0ec1ee3664612bf042c654af5acd01ac7feb5c6b00c7cd8` |
| `Bristlune-native-notice-candidates.tar` | 180 | 2,181,120 | `2b5fcccbcea4a25393e9e351a2301d14436cffe66a8fa5b0571d36d4363fbd18` |

That directory also contains separate source plans, collection receipts, the full
dependency runtime file map and full notice candidate map. Their hashes are
bound by committed `inventory.json` and `collection-receipts.json`. The recipe
archive from a prior independent generation has identical bytes.

An additional one-input source collection at
`/private/tmp/Bristlune-known-source-materials.tar` exercises the public CLI with
the actually verified OpenColorIO source archive. It is 14,141,440 bytes,
SHA-256 `1a417255ff164c3b4b4ef47f0e16e4bd9a52d5739f9afdf910c590a580b091e0`,
with separate `/private/tmp/bristlune-known-sources-plan.json`. This is expressly
one materialized input, **not** the full native source distribution. No large
binary archive was downloaded or recopied.

## Verification performed

`python3 -m unittest discover -s distribution/native-source -p 'test_*.py' -v`
passed **14 tests**. The first run was red because the collector module was
absent. Cases exercise real Git objects/commits, ignored export attributes,
preserved executable source modes, wrong commit/tree and unresolved gitlink
rejection, deterministic byte equality, changed/missing/extra materials,
symlink/ancestor and case/Unicode alias rejection, output-owner preservation,
duplicate/non-finite JSON, corrupted/duplicated/traversal/link/mode/time/payload/
manifest/trailing tar variants, reviewed Windows selector mutations and exact
retained evidence binding. The real immutable Qt tree and original build events
are cross-checked by the tests.

The full CLI with `--check` rederived the committed inventory from the original
90 archives and recipe Git tree, generated both real collections and verified
them before exclusive publication. Then three separate `native_source.py
verify` commands re-read the recipe, notice and actual OpenColorIO collections
against their separate plans. Each passed with the exact hashes above.

Owned code/data/docs pass the whitespace check. The full staged whitespace
check reports five pre-existing trailing-space lines in the byte-preserved
OpenColorIO `Install*.cmake` evidence; those source bytes were deliberately not
edited. Local verification used macOS Python/Git, not a Windows app execution.

No full application rebuild or installed workflow was rerun for these source
publication-only additions. The existing public MSIX gate still demands explicit
truthful per-file license/source review and both clearance attestations; these
tools always leave those attestations false. Hash verification authenticates the
recorded bytes against a reviewed plan; it cannot establish that arbitrary
user-supplied material is complete corresponding source or authenticate a
reviewer's legal conclusion.

## Next bounded work

Materialize the selected source tarballs/overlays and resolved Git/module sources
into reviewed SHA-256/size plans, resolve the two original moving Git inputs and
the opaque producer source/notice records, and assemble actual source/resource
notices against the renamed Windows installed tree. Include the exact final
application source and build/install instructions. Root then publishes source
assets, verifies anonymous downloads and supplies any later truthful audited
runtime record. The main unresolved facts are specific original inputs and
notice decisions; a blanket byte-identical reproduction requirement is not
being imposed.
