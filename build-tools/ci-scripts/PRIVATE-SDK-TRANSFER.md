# Private restoration of the two original Qt inputs

The original KDE archive and metadata URLs remain pinned and currently return
404. No dependency lock byte, SDK revision, source pin, runtime selection or
license/source publication binding is changed by this restoration. See
`PINNED-QT-RECOVERY.md` for the original failure and retained-cache provenance.

Actual access proofs established the required job permission:

- `35707107569`: `contents:read` refused draft release metadata (HTTP403).
- `35707610475`: direct exact asset API also refused `contents:read` (HTTP403).
- `35708067868`: metadata-only job with `contents:write` passed the exact
  878-byte body/hash and draft-state checks before and after the request.

The release owner then authorized the archive upload to the same unpublished
draft, `393572515`, tag `bristlune-locked-build-inputs-20260922`. It contains only:

| API asset ID | Original bytes | SHA256 |
| --- | ---: | --- |
| `581002655` | 787742720 | `766c8bef1577a76bba55f059bfb54afc352d1d38f47593365b1f544516974495` |
| `580969685` | 878 | `26f5453f0c92cd8d0556f75aa77f1c24619bc2b62b8a8b2ac1ae790285cf9cbe` |

GitHub's asset digest and a full authenticated streaming readback independently
match the original archive's 787742720 bytes and SHA256. No duplicate archive was
saved locally. The anonymous archive asset request returns HTTP404, and the final
release readback remains `draft:true`, `published_at:null`. Original upload,
readback and anonymous-response evidence is retained privately under
`/private/tmp/bristlune-private-metadata-proof-20260922`. This draft is not a public
SDK or product release and must remain unpublished.

## Permission and confidentiality boundaries

GitHub [workflow artifacts are downloadable by signed-in readers](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts),
so a raw artifact in this public repository would not preserve SDK privacy.
The release owner instead authorized a dedicated random 32-byte
`BRISTLUNE_SDK_TRANSFER_KEY` repository Actions secret. It was generated in memory
and sent to `gh secret set` through stdin; no plaintext key file or log was created.
This is only an encryption key, not a PAT or account credential.

`private-sdk-fetch.yml` is a reusable fetch-only job. Its `contents:write` token
is supplied only to the fixed GitHub API fetch step. Checkout credentials are not
persisted. It checks exact unpublished release/tag, asset IDs, names, sizes and
digests before and after download. Original archive bytes are streamed to a
bounded temporary file, checked against the unchanged lock's hash and size, then
encrypted. No downloaded input is executed, extracted or compiled in that job.

Only two `.aesgcm` files and `transfer.json` are uploaded as the same-run artifact.
The artifact has one-day retention. AES-256-GCM uses a fresh random 12-byte nonce
for each file. Its authenticated data binds the repository, current source commit,
run, attempt, asset ID, expected original hash and byte count. The format is eight
magic bytes `BRSTSDK1`, twelve nonce bytes, sixteen authentication-tag bytes, then
ciphertext. The non-secret manifest must equal the current source/run/attempt and
the exact source-owned two-input binding; unexpected fields/files are refused.

The downstream Windows build explicitly has only `contents:read`. The encryption
key is scoped to its preseed step, not native build or application steps. Decryption
streams into an exclusive temporary file; GCM authentication and the original
plaintext hash/size must all pass before atomic, non-overwriting cache admission.
Changed, truncated, wrong-key or replayed inputs leave no admitted plaintext.
Links and existing destinations are preserved by refusal. The original dependency
fetcher then verifies the complete unchanged lock and original registry metadata
as before. It finds these two originals already cached and does not request their
missing upstream URLs. No new PAT, raw SDK Actions artifact, public draft release,
product bypass or cache hash exception is introduced.

## Focused validation and next actual proof

`node --test build-tools/ci-scripts/tests/test_private_sdk_transfer.cjs` passes all
nine focused tests, using real streamed encryption/decryption and actual temporary
file admission. Coverage includes random nonce/opaque ciphertext, tag/nonce/body/
key corruption, truncation, source/run/attempt/hash/asset replay, changed originals,
foreign existing files, links, unpublished draft and locked input predicates,
actual fetch-to-seed callers, oversized/corrupt/HTTP403 child responses, cleanup
of partial files and one exact ciphertext-only transfer file set. The fixtures
replace only the remote API/child payload source; they do not claim an actual SDK
or installed product success. YAML validation confirms write permission only in
the fetch job and no raw work/cache upload path. `git diff --check` passes.

The next manual workflow is `private-sdk-transfer-proof.yml`. It invokes the same
reusable fetch job, downloads only its own run/attempt's encrypted artifact in a
read-only Windows job, authenticates and seeds the cache, then invokes the unchanged
Python `verify_artifact` and `check_metadata` on the two original Qt inputs. It
performs no native build, package installation or product workflow. Both jobs
retain bounded metadata receipts separately from the ciphertext artifact.

Actual encrypted Windows fetch/preseed proof and the subsequent full dual installed
release qualification remain pending root review and dispatch. The older successful
SDK packaging and product suite evidence is preserved without being relabeled as
success for this candidate.
