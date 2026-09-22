# Exact pinned Qt input recovery, September 22, 2026

Full release `35704628895`, public source
`05effdd486728d20b65559fb6632637293aa7fd5`, failed while fetching locked
dependencies. The original log reports HTTP 404 without a URL; native compilation,
installation and product qualification did not begin. The preceding small SDK
run `35704395403` passed through the exact PowerShell 7 / Python / Windows
PowerShell launch chain.

Current verified-TLS HEAD observations of all 176 pinned download URLs identify
exactly two 404 responses, both for `ext_qt`. The other 174 respond HTTP 200.
The ordered fetch reaches this archive before its associated metadata:

```text
https://invent.kde.org/api/v4/projects/16406/packages/generic/ext_qt/transition.now-update-qt-to-6.11.0-1788898275/archive.tar
https://invent.kde.org/api/v4/projects/16406/packages/generic/ext_qt/transition.now-update-qt-to-6.11.0-1788898275/metadata.json
```

The official current registry listing omits that version. Its September 17
replacement has recipe commit `e0ee7ab2e3b0d9fb8b4ab1c55426d398a13803ee`, whereas
the existing lock requires `993af62fdf291eaec05a1824d9b420782717fc44`. It is not an
acceptable substitute. The original producer job `4983784` artifact API and web
download both now return 404; the previously retained job artifact contained its
source/build log, not this SDK archive. No official byte-identical alternate was
found in these bounded checks.

Both cached originals were streamed through SHA256 again without extraction or
replacement:

| Original | Bytes | SHA256 |
| --- | ---: | --- |
| Qt archive | 787742720 | `766c8bef1577a76bba55f059bfb54afc352d1d38f47593365b1f544516974495` |
| Registry metadata | 878 | `26f5453f0c92cd8d0556f75aa77f1c24619bc2b62b8a8b2ac1ae790285cf9cbe` |

They remain at `.brushquay/cache/<SHA256>`. Lock URLs, hashes, sizes, source commits,
source publication receipts and runtime/license review remain unchanged.
Private retained evidence:

- `/private/tmp/bristlune-35704628895-failed.log`
- `/private/tmp/bristlune-35704628895-curl-probe.json`
- `/private/tmp/bristlune-extqt-current-registry.json`
- `/private/tmp/bristlune-extqt-new-official-metadata.json`
- `/private/tmp/bristlune-extqt-official-artifact-probe.json`
- `/private/tmp/bristlune-extqt-retained-byte-proof.json`

The narrow fetch diagnostic now wraps transport errors with the original locked
public URL and SHA256, preserving the original exception as its cause. It adds no
retry, mirror, changed hash acceptance or staging behavior. Four HTTP404/TLS error
cases across archive and metadata fixtures failed before the correction and pass
after it. They assert one request, exact original identity/reason, empty temporary
cache and no staging. All 20 `test_locked_windows_deps.py` tests pass.

## Approved private metadata access proof

The release owner authorized creating a draft only, not publishing the SDK:

- Repository: `hashfunction/brushquay`
- Draft tag: `bristlune-locked-build-inputs-20260922`
- Release ID: `393572515`
- Target public commit: `05effdd486728d20b65559fb6632637293aa7fd5`
- Sole asset: `ext_qt-1788898275-metadata.json`, ID `580969685`
- Asset bytes/hash: the exact 878-byte original metadata above

The local maintainer-authenticated asset readback matches the original bytes.
The anonymous asset API request returns 404. The release remains `draft:true`,
`published_at:null`; the 787742720-byte archive has **not** been uploaded. Private
creation/readback receipts are under
`/private/tmp/bristlune-private-metadata-proof-20260922`.

The manual-only `locked-input-proof.yml` workflow uses only the existing
same-repository `GITHUB_TOKEN` with `contents:read`. It addresses the exact release
and asset IDs, verifies the draft/tag and asset name/size/digest before and after
the download, and hashes the actual 878-byte body. It uploads only a bounded
access-result receipt. There is no dependency fetch, package build, installation,
public upload or product acceptance claim in this workflow.

GitHub documents read-only Contents permission for the
[release asset API](https://docs.github.com/en/rest/releases/assets#get-a-release-asset),
but draft visibility also depends on access. Actual job-token draft access is
therefore **pending this proof**, not inferred from the maintainer token. The
release-by-tag endpoint returned 404 even to the maintainer while the draft was
visible by ID; the proof deliberately binds API IDs rather than browser/tag URLs.

The release owner will review/push and dispatch the proof. Only if it succeeds
should the exact retained Qt archive be added to the same private draft, then a
small guarded preseed operation can restore these two cache hashes before the
unchanged lock verifier runs. That upload and preseed integration are not part of
this candidate. No full build rerun is justified until the missing original bytes
are accessible to its runner.
