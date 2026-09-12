# Reviewed release input interface

`release-inputs.json` is deliberately `{ "schema": 1, "reviewed": null }` until
release review supplies original concrete data. A workflow switch cannot approve it.
The `reviewed` object has exactly these fields:

- `licenseReviewComplete`, `correspondingSourceComplete`: actual review attestations,
  both boolean true, supported by the records below.
- `catalog`: `{path, bytes, sha256}` of the source-relative original notice catalog.
- `publications`: one or more `{path, bytes, sha256}` references to original anonymous
  public-body readback receipts using the published Bristlune readback schema. These
  source-relative copies retain original bytes and their own historical scope/flags.
- `runtimeOwners`: exact retained runtime path → list of original input owner IDs.
  It must equal current selected runtime paths and their actual locked owners;
  current native application files use owner `application`.
- `owners`: owner ID → `{license, sources, notices}`. `license` is the reviewed
  expression for this owner's complete selected scope; `sources` lists exact archive
  SHA256 keys present in both catalog and verified public body records; `notices`
  lists applicable original paths within the catalog. Shared decisions appear once.
  Only owner `application` may use `current-application`, resolved to the exact
  current public source checkout archive URL. This does not cover dependency source.
  One additional source token, `upstream-reference:libvpx-1.13.1`, is accepted
  only for the exact selected `bin/libvpx-8.dll`, BSD-3-Clause and the exact
  original version-reference LICENSE/PATENTS pair pinned in `LIBVPX_REFERENCE`.
  This permissive reference creates no archive/body-verification or producer
  revision claim. The generated source index explicitly records its unknown
  `meson-2` producer revision and keeps it separate from `publicSources`.
- `excludedRuntime`: `{}` or exactly the three optional OpenSSL1 TLS files with
  original byte/hash records in `release_inputs.OPTIONAL_TLS`.
- `optionalTlsRemovalReviewed`: false for no exclusions; true only after a separate
  review has resolved runtime/dynamic-load applicability of that exact group.

The native release still reads every original selected PE before applying exclusions,
requires complete current graph records, and refuses any retained normal/delay import
into that group. It never treats this graph as proof about arbitrary dynamic loading.
All original catalog notices are copied unchanged, with catalog and generated current
source references. Nothing here decides license compatibility from notice presence.
New runtime owners or paths, different source/notice bytes, incomplete public readback,
and absent review fail closed. Original source publication need not claim final binary
acceptance; that belongs to the new independently gated export receipt.

## Concrete candidate for final review

`release-data/review-candidate.json` contains the complete proposed data in
`candidate`, with `reviewed:null` and both review attestations false. The active
`release-inputs.json` remains unchanged. `validate_candidate` checks the same
source/notice/publication/runtime material boundary while preserving false
attestations; its result is rejected by the actual MSIX audit builder.

The candidate joins the exact original run34708230966 runtime/PE observations
to the reviewed three-file TLS omission and the separately approved source
install omission of the optional SeExpr examples bundle. It projects 5,102
runtime inputs: 4,232 dependency files and 870 application files, across 68
used owner decisions. The old OpenSSL1 owner is unused and excluded from this
runtime-owner decision map; its original historical notices remain intact.

The combined `distribution/native-source/original-notices/release-catalog.json`
preserves the original dependency catalog entries and adds 173 byte-verified
application originals, four original W3C grant documents and the source-owned
Store terms. Its 1,470 notice
files retain subcomponent scope and custom LicenseRef definitions. The original
catalog remains unchanged. The copied public body receipt also retains its
original bytes and historical scope, covering 117 source archives and the two
published metadata documents; no large archive was downloaded again.

Run the independent candidate check with the original artifact metadata:

```sh
python3 packaging/windows/msix/check_release_candidate.py \
  --runtime-record /path/to/original/qualification-package.json \
  --pe-graph /path/to/original/staged-pe-imports.json
```

It binds the original evidence hashes/run, full 537-PE graph, exact omissions,
projected owner map, all original notice bytes and published source references.
It refuses rewritten original catalog entries and requires the active binding
to remain unapproved. `release-data/candidate-provenance.json` retains the exact
baseline evidence identities, owner qualifications and application scope.

`release-data/Bristlune-Store-license.txt` is the plain-text Partner Center
license candidate. Its identical packaged copy preserves the Microsoft-only
scope of SDK/Visual C++ protections while leaving independent open-source and
creative-resource grants intact. `store-license-basis.json` binds both copies
to the seven selected standalone Microsoft DLLs and ten unchanged original
Microsoft/Python notices. The checker rejects altered text, altered or missing
notices and a changed Microsoft runtime map. The original runtime end-user
license is not treated as a redistribution grant.

Final review must approve the proposed owner expressions and application
resource applicability. Only then may the reviewer copy the `candidate`
object into the active binding's `reviewed` field and explicitly set its two
review attestations true. There is no command or workflow switch that performs
that approval. A new exact public-source Windows run must still build/stage
the intended files, validate its current full PE graph, prove both original
installed workflows and pass independent unsigned export. The historical
5106-file observation does not claim those future outcomes.
