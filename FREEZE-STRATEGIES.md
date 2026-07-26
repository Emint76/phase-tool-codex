# Freeze Strategies

Status: Stage 1 normative specification; no freezer implementation exists.

## 1. Purpose

A freeze strategy binds operation inputs to evidence. Different strategies provide different guarantees. Only bytes actually copied into Core-controlled content-addressed storage are called a frozen byte copy.

Supported strategies:

- `copy_and_hash`;
- `manifest_and_hash`;
- `lock_snapshot_revalidate`;
- `value_snapshot`.

## 2. Shared requirements

Every input evidence record contains:

- binding ID;
- strategy;
- resolver/locator declaration;
- observed byte/value digest;
- size/count;
- observation time;
- provenance reference when required;
- manifest/blob digest where applicable;
- revalidation token where applicable;
- errors/unsupported properties;
- validator/mechanism version.

SHA-256 identity is scoped to exact canonical bytes. Metadata, file identity, permissions, link state, and durability require separate evidence.

## 3. `copy_and_hash`

### Procedure

1. Resolve input under read/path policy.
2. Reject unsupported link/reparse/path state.
3. Open a stable read handle where the platform permits.
4. Stream all bytes to a Core-controlled temporary blob while hashing and counting.
5. Flush/sync according to the declared evidence policy.
6. Verify stored blob digest/length by read-back.
7. Publish content-addressed blob `<digest>` without replacement.
8. Record blob digest, length, resolver observation, and publication result.
9. Operation reads only the frozen blob.

### Guarantees

When all steps and future tests pass:

- the operation consumes the same blob bytes whose digest is recorded;
- later upstream mutation cannot alter the consumed frozen blob;
- same digest refers to the same bytes under the selected hash assumption;
- mutable upstream is not read after freeze.

### Non-guarantees

- upstream semantic correctness;
- authenticity or approval;
- original metadata/ACL/timestamps unless separately captured;
- durability beyond the selected platform/filesystem profile;
- resistance to privileged modification of Core storage;
- remote/network filesystem semantics.

### Revalidation

Re-hash/length-check the frozen blob immediately before mechanism use or bind an open immutable blob handle. Re-reading upstream is forbidden.

### Mandatory evidence

- upstream observation reference;
- blob digest and length;
- content-addressed locator;
- copy/read-back validator results;
- selected durability policy;
- proof operation plan references the blob digest.

## 4. `manifest_and_hash`

### Procedure

1. Enumerate a bounded declared set deterministically.
2. Normalize each relative locator under path policy.
3. Record type, length, content digest, and selected metadata.
4. Sort entries by canonical byte ordering.
5. canonicalize and hash the manifest.
6. Store the manifest as evidence.

### Guarantees

- a point-in-time inventory of observations;
- deterministic manifest digest for the same recorded entries;
- later comparison can detect observed entry/content changes.

### Non-guarantees

- manifest entries are not frozen bytes;
- no guarantee the set remained stable during enumeration unless a snapshot/lock boundary exists;
- no guarantee later reads yield recorded bytes;
- no prevention of rename/symlink/path races;
- no atomic directory snapshot;
- no permission, ACL, owner, or semantic guarantee unless recorded/tested.

### Revalidation/use rule

For a mutation mechanism that needs input bytes, manifest-only evidence is insufficient unless:

- bytes are opened and held under a stable handle/lock;
- every consumed byte is rehashed and matched immediately before/during use; and
- destination is not committed on mismatch.

Preferred rule: convert required mutable bytes to `copy_and_hash` before mutation.

### Mandatory evidence

- enumeration root binding;
- canonical ordered manifest;
- manifest digest;
- per-entry digest/length/type;
- enumeration start/end;
- instability/errors;
- revalidation result if consumed later.

## 5. `lock_snapshot_revalidate`

### Purpose

Bind mutable target/current state that cannot or should not be copied wholesale, such as an append head.

### Procedure

1. Define lock scope and concurrency-token algorithm in the contract/mechanism.
2. Observe state and capture token (digest/head/version/length).
3. Record expected token in intent/effect plan.
4. Immediately before mutation, acquire the target-local lock.
5. Resolve target again using race-resistant path/handle policy.
6. recompute state token under lock;
7. require equality with expected token;
8. perform one bounded effect while lock remains held;
9. read back and verify resulting token before releasing lock.

### Guarantees

- cooperating writers using the same lock scope are serialized;
- stale expected token is rejected before mutation;
- result is verified relative to the state observed under lock.

### Non-guarantees

- non-cooperating or privileged writers are not excluded by an advisory lock;
- lock name equality alone does not prove target identity;
- distributed/network locking is unsupported;
- filesystem/path substitution must be handled separately;
- crash durability is separate from concurrency.

### Mutable upstream rule

Reads of target/current state are allowed only while holding the specified lock and using the revalidated identity/token. Other mutable upstream reads after freeze are forbidden.

### Mandatory evidence

- lock provider/version/scope;
- initial and under-lock tokens;
- target identity observations;
- acquisition/release times and result;
- stale-token validator result;
- post-effect token/read-back.

## 6. `value_snapshot`

### Procedure

1. Parse according to declared input mode/schema.
2. canonicalize with an exact versioned codec, or preserve raw bytes.
3. record canonical bytes/value, digest, length, and codec.
4. use only the captured value throughout the run.

### Guarantees

- Core validators/mechanisms consume the recorded canonical value/bytes;
- repeated digest computation over the same canonical bytes is deterministic.

### Non-guarantees

- caller-side bytes before the Core boundary unless raw binary ingestion captures them;
- semantic truth, authenticity, trusted time, or identity;
- external referenced object stability.

### Revalidation

Recompute digest of stored canonical bytes/value before planning/use. Do not re-read a mutable caller object.

### Mandatory evidence

- input mode/encoding;
- codec/version;
- captured length/digest;
- inline value or attachment digest;
- schema and validator results.

## 7. Strategy selection

| Need | Required/default strategy |
|---|---|
| Consume external bytes in mutation | `copy_and_hash` |
| Record point-in-time inventory only | `manifest_and_hash` |
| Mutate relative to current target head/state | `lock_snapshot_revalidate` |
| Small structured/scalar candidate/config | `value_snapshot` |
| Directory tree later copied | per-file `copy_and_hash` plus manifest, not manifest alone |
| Remote/network input | unsupported for strong v1 freeze claims; copy to tested local storage first |

## 8. Mandatory TOCTOU tests

Future executable tests must cover:

- input changes while being copied;
- input changes after manifest but before use;
- directory entry replaced between enumeration/open;
- symlink/reparse insertion during resolution;
- source handle points to replaced/unlinked object;
- stale target head before lock;
- target replacement before and after lock;
- non-cooperating writer during append;
- frozen blob tampering before use;
- hash/length mismatch during stream;
- crash before blob publication, after publication, and before intent finalization;
- WSL `/mnt` behavior separately from native Linux filesystem.

A test that detects drift only after canonical target mutation does not prove TOCTOU prevention; it proves post-mutation detection and must lead to partial/unverified classification.
