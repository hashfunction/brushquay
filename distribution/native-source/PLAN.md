# Bristlune native source collection

Scope: source inventory, source-only collection and verification. The product,
runtime selector, installed workflow, CI and audited public package gate remain
separate. Work starts from source `02947962463041a3d4432444e1958f8c106f68a7`.

1. Bind all 90 locked inputs to the exact dependency recipe tree and original
   Windows dependency build. Trace Windows source declarations, patches, nested
   inputs, runtime owners and available notice candidates. Preserve uncertainty
   where the original build does not identify the source.
2. Add a deterministic, offline collection format that verifies immutable Git
   trees and source/notice bytes, never executes dependency build instructions,
   never replaces an existing output and independently verifies every archive
   member. Keep missing material and unreviewed license conclusions explicit.
3. Test changed/extra/missing inputs, unsafe archive paths and modes, duplicate
   members, changed provenance and output preservation. Generate and verify the
   real small recipe/evidence collection without downloading large binaries.
4. Record exact remaining materials and publication instructions for root review.
   Archive integrity is not an attestation of license or corresponding-source
   completeness. Root owns public source delivery and the final runtime audit.
