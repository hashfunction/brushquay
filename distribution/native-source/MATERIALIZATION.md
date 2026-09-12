# Materialized native source follow-up

This follow-up starts from source commit `72bcdff8502558052a65c2ab1c0c0eacb73f74d5`.
It changes source acquisition, verification, inventories and documentation only.
No product, installed qualifier, CI, binary package or release attestation changes.

## Available materials and independent checks

`materialized-inputs.json` describes **117 source archives, 1,026,207,310 bytes**:

- All **69 unique** source URL inputs/overlays selected by the original Windows
  recipe passed their original checksums. Deduplicated records retain every
  owner, including FreeType stages and the three x265 builds. Three original
  inputs use MD5 (gettext, giflib and win-iconv); their measured SHA-256 values do
  not turn those original pins into SHA-256 attestations. Eight prebuilt-only
  URL inputs were excluded from these source requests.
- **34 immutable Git source trees** passed comparison of every tracked blob,
  executable mode and symbolic-link target with the Git object database. These
  include 12 resolved library repositories, Qt's eight selected modules, five
  nested OpenColorIO libraries, LLVM/compiler/build-tool sources, CPython, and
  the three recursively fetched Immer/Lager/Zug documentation/example helpers.
- **14 further archives** supply XZ 5.2.6, OpenSSL 1.1.1l, and 12 external sources
  pinned by the official Python embedded-runtime SPDX document. This collection
  preserves source/build components without claiming that every component in an
  upstream package-level SBOM is included in the final executable.

The private material root is
`/private/tmp/bristlune-source-collection-final`. Source downloads are under
`upstream-archives`; Git downloads are under `git-archives`; restored raw Git
archives are under `git-raw-archives`. The separately retained original binary
archives used for provenance inspection live under
`/private/tmp/bristlune-source-audit/producer-inputs` and **are not source
collection members**. Original downloads and build-log receipts remain retained.

Fifteen Git host archives applied export attributes or line-ending conversion.
For example, Qt substitutes `.tag` and omits `.gitattributes`/other tracked files;
CMake and CPython convert Windows text files to CRLF. The raw archives restore
missing/changed files from immutable source URLs, compare each returned blob
with its independent Git object ID, preserve the original download hash and
record every restoration. Output is deterministic gzip/PAX tar with normalized
metadata. A complete independent readback compares all tracked Git blobs again.
Original downloads are not overwritten. Symbolic links are never followed or
extracted by these tools. Gitlinks remain explicit in every proof.

The Git source proof does not expand unused Qt submodules. The original recipe
selects eight modules with `GIT_SUBMODULES_RECURSE false`, disables Assistant and
Designer, and excludes examples/benchmarks/manual/minimal-static tests. Thus QtTools' `src/assistant/qlitehtml` and
QtDeclarative's `tests/.../test262` gitlinks are recorded but were not fetched for
this build. The eight actual modules, OCIO's five nested sources and the fetched
Immer/Lager/Zug helpers have separate archives and path/commit mappings. Source
assembly must preserve those mappings and original recipe patch order. Keep
OCIO's pystring CMake patch with its source. Raw Qt `.tag` remains the tracked
preferred-source text; any archive-style generated commit substitution during
offline build preparation must be explicit and must not alter the audit archive.

`source-archive-content-inventory.json` records **408,512 archive members** and
**585 notice candidates**, with member paths, source owners, sizes and hashes,
plus nested-source descriptor paths. This is discovery evidence, not a completed
license applicability review. The earlier 180 installed notice candidates and
498-file complete recipe/patch archive remain available. Fifteen exact original
producer notice/readme texts are separately retained in `producer-notices` and
bound by `producer-provenance.json`; no DLL is included there.

## Provenance findings and open items

**libvpx and gperf remain unresolved.** The original dependency build prints
`meson-2` / version 1.13.1 and `meson` / version 3.1 but no resolved commits.
The currently visible branches are old, but their dates do not prove what the
original builder checked out. `producer-research.json` preserves this distinction.
Obtain the original Git resolution/source cache or an immutable producer receipt;
do not replace these with today's tips or a chronology-based guess.

**OpenSSL:** the exact original curl-for-win ZIP supplies the staged
`libssl-1_1-x64.dll` and `libcrypto-1_1-x64.dll` bytes and identifies OpenSSL 1.1.1l.
The matching unmodified source tarball passed SHA-256. Historical curl-for-win
commit `2fb8b5ba0980996bb04d5a779457e45390abe6bc` declares version 1.1.1l, revision 4
and that source checksum; its retained scripts describe a Configure prefix patch
and build options. It is a compatible historical builder candidate, **not a
proved producer commit**. The original ZIP readme has no revision binding; the
queried original release endpoints are unavailable. Retain the exact producer
build/patch evidence if this binary remains in the package and finish the actual
OpenSSL/SSLeay notice and combined-license review.

**XZ:** the original XZ 5.2.6 Windows ZIP's x86-64 `liblzma.dll` matches the stage.
The matching XZ source tarball, including Windows build instructions, passed the
SHA-256 in the original recipe's alternative source declaration. The producer's
README identifies the relevant XZ code as public domain, states that MinGW-w64
runtime code is statically linked, and requires `COPYING-Windows.txt` alongside
redistributed binaries. That exact notice is retained. This finding is a concrete
notice requirement; it is not a blanket copyleft demand for unknown compiler source.

**Python:** the official [embedded-runtime SPDX](https://www.python.org/ftp/python/3.13.5/python-3.13.5-embed-amd64.zip.spdx.json)
matches the complete original ZIP's SHA-256
`7d2650fd9d1b9d002d4a315d5f354247fd6a44f30517c7ef577b08f57a0fb6d9`.
The retained CPython source is commit
`6cb20a219a860eaf687b2d968b41c480c7461909`. Its actual PCbuild defaults and producer
SPDX identify bzip2 1.0.8, libffi 3.4.4, mpdecimal 4.0.0, OpenSSL 3.0.16, SQLite
3.49.1.0, XZ 5.2.5 and zlib 1.3.1, in addition to vendored-source components.
All 12 collected external archives passed the **producer's** source SHA-256
values. Tcl/Tk entries remain in the original SPDX but are not falsely described
as shipped by the embedded ZIP; no `_tkinter` module/Tcl/Tk payload is included.
The exact embedded LICENSE is retained. Applicable VC runtime distribution terms
and final file-to-license mapping remain a separate review, not a request for
Microsoft's proprietary source.

**DrMinGW:** the SHA-pinned patched 0.9.7.1 source tarball contains the actual
libdwarf 0.3.4 and zlib 1.2.11 source bodies, their build rules and licenses, plus
libiberty's demangler with its linking exception. These are not empty gitlinks.
The separately copied `dbghelp.dll`, `dbgcore.dll`, `symsrv.dll` and `symsrv.yes`
match the original 0.9.7 Windows archive byte for byte. Their Microsoft
redistribution terms must be established if they ship: Microsoft's
[DbgHelp documentation](https://learn.microsoft.com/en-us/windows/win32/debug/dbghelp-versions)
distinguishes the Debugging Tools package from the non-redistributable OS copy.
DrMinGW's LGPL notice does not supply Microsoft rights.

An alternative package scope is supported by concrete evidence. In
`krita/main.cc:107`, the application dynamically loads adjacent `exchndl.dll` and
returns normally when absent. All 341 selected dependency PE files were
independently hash-checked and their import tables read: only `exchndl.dll`
imports `mgwhelp.dll`, and only `mgwhelp.dll` imports `dbghelp.dll`. The current
runtime selector includes all dependency DLLs and explicit `symsrv.yes`.
Therefore a separately reviewed package-only exclusion of **all six** crash
handler files is a plausible way to omit optional crash reporting without a
product rebuild. Before changing that package, scan the actual application PE
imports/delayed loads and rerun the unchanged installed qualification with the
exact narrowed runtime. This task makes no exclusion or Windows success claim.
`evidence/drmingw-import-summary.json` binds the full private 341-file receipt.

**gettext:** 37 staged gettext-tools message catalogs and `locale.alias` match
the original prebuilt package. Each catalog's `.po` preferred source is present
in the SHA-recorded gettext 0.21 source archive. The remaining `intl.dll` is the
separate source build with the five retained Windows patches, not the prebuilt
iconv tool package. These origins and source hashes are retained in
`evidence/gettext-runtime-origin.json`. Preserve the original notices and assess
the actually selected content; CLDR/iconv programs are not inferred shipped just
because the upstream archive contains them.

The actual LLVM commit is proved by the original build log. The collected
mingw-w64 commit remains the locked llvm-mingw build script's default; original
release override evidence still needs review. Final renamed application source,
build/install scripts, generated configuration, application resources and the
actual installed-tree license mapping remain outside this available-dependency
source receipt. No historical native pass is relabeled as a new installed pass.

## Commands and validation

From the application source root, Python 3.10+, Git and curl are sufficient.
Downloads are HTTPS data only; no fetched build script is executed. Existing
cache/output owners are preserved. These receipts must first be independently
reviewed; byte verification is not provenance authentication by itself.

```sh
python3 distribution/native-source/source_materialize.py \
  --cache /absolute/source-cache --receipt /absolute/new-download-receipt.json
python3 distribution/native-source/source_materialize.py git-verify \
  --repo /absolute/source-git-metadata --commit <full-commit> \
  --archive /absolute/source.tar.gz
python3 distribution/native-source/source_materialize.py git-restore \
  --repo /absolute/source-git-metadata --commit <full-commit> \
  --archive /absolute/original.tar.gz --output /absolute/new-raw.tar.gz \
  --raw-repository <reviewed-https-repository>
python3 distribution/native-source/source_materialize.py collection-check \
  --receipt distribution/native-source/materialized-inputs.json \
  --cache /private/tmp/bristlune-source-collection-final
python3 -m unittest discover -s distribution/native-source -p 'test_*.py' -v
```

The read-only collection check reverified all 117 archive hashes, sizes, safe
paths, owners and the original inventory binding. To create a deterministic
outer source tar when disk permits, use `collection-create` with the same
receipt/cache plus new `--plan` and `--output` paths. This calls the existing
independent canonical-tar verifier. The plan is separate from the archive;
verify it again with `native_source.py verify --archive ... --plan ...`.
Only the receipt's source archives are selected; original binary inputs and
unlisted cache files cannot be silently included. Notice texts, source mappings,
recipe/patch archive and rebuild documentation must also accompany the eventual
reviewed publication. Root owns publication and anonymous download verification.

No extra 1 GB aggregate archive was made while free disk space was limited.
Focused tests cover wrong/changed download bytes, conflicting owners/pins,
legacy MD5 labeling, hostile/missing/altered Git archive members, export-attribute
restoration, wrong immutable blobs, deterministic output, existing-owner
preservation, receipt/inventory mismatch, owner/path mutation, and the actual
Python producer SPDX/source bindings. Both clearance fields remain **false**.

Validation on this candidate: **23 focused tests passed**, Python compilation
passed, all 117 material hashes/owners passed a fresh CLI check, and the restored
Qt superproject passed the independent Git CLI verifier. The original producer
SPDX bytes use CRLF; Git's whitespace check passes with `cr-at-eol` enabled so
that this evidence is preserved byte for byte. No new native build was run for
these source-only tools, and no Windows/product gate is claimed by these checks.
