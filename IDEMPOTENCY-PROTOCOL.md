# Idempotency Protocol

Status: Stage 1 normative protocol; no idempotency store/runtime exists.

## 1. Definition

Idempotency means a retry of the same scoped operation request can return the same verified outcome without creating an additional canonical effect. It does not mean every unkeyed request is safe to repeat.

Identity tuple:

```text
(scope_digest, idempotency_key, canonical_request_digest)
```

## 2. Key scope

The contract declares scope fields. Core canonical scope always additionally binds:

- contract ID/version/package digest;
- canonical result owner/root binding identity;
- operation intent;
- mechanism ID/version/package digest;
- contract-declared subject/result locator components;
- installation policy version where it changes result authority.

The scope is canonicalized with a versioned policy and hashed. Plain string concatenation is forbidden.

The key is caller-stable opaque data with bounded length. Core does not infer one from timestamps or content unless the contract explicitly defines deterministic derivation.

## 3. Canonical request digest

The digest covers the frozen representation actually executed:

- exact contract binding;
- candidate canonical bytes/digest;
- frozen input digests/manifests/tokens;
- canonical root/result locator bindings;
- static effect plan digest;
- operation/mechanism binding;
- domain extensions/config that affect effects/result;
- relevant verification/outcome policy.

It excludes generated run ID, receive/finish timestamps, transient logs, and receipt fields.

Hashing a mutable locator instead of consumed bytes/token is insufficient.

## 4. Durable intent

Before mutation, Core writes and syncs an immutable intent binding:

- run ID;
- scope digest;
- key;
- canonical request digest;
- contract/registry/mechanism digests;
- frozen inputs;
- effect-plan digest.

The durability level is recorded. If intent durability cannot be established, mutation must not begin for contracts requiring retry safety.

## 5. Decision table

| Prior state | New request | Required result |
|---|---|---|
| No matching key in scope | Any digest | Create durable intent, then proceed |
| Verified receipt, same key and digest | Same request | Return existing verified result/receipt; no mutation |
| Verified receipt, same key but different digest | Different request | `rejected` conflict; no mutation |
| Intent only/incomplete, same key and digest | Retry | Inspect canonical target/effects before any replay |
| Previous `failed_no_effect`, same key/digest | Retry | Allowed only after no-effect evidence remains valid |
| Previous `failed_partial` | Same request | Inspect all effects; complete only contractually safe missing idempotent effects |
| Previous `committed_unverified` | Same request | Verify/finalize existing result; do not blindly replay |
| Previous `indeterminate` | Same request | Retry forbidden until inspection resolves state |
| Same result bytes without matching intent | Same/different key | Contract may classify `adopted_existing`; never claim created by this operation |

## 6. Canonical result lookup

The contract specifies lookup authority:

- canonical result;
- Phase receipt;
- canonical result then receipt.

Core uses a registered read-only verifier to find operation identity/digest in the result or validate content/head state. A rebuildable receipt index may accelerate lookup but is not canonical.

Absence from an index does not prove absence of a result.

## 7. Receipt/evidence lookup

Receipt lookup binds:

- scope/key/request digest;
- run/intent digest;
- exact contract/mechanism;
- terminal status;
- canonical result reference/state;
- evidence finalization.

Only `succeeded_verified` is an immediately reusable success. A receipt file with invalid schema/digest/bindings is not trusted.

## 8. Mechanism-specific recovery

### Exclusive create

- destination absent and valid intent → retry create;
- destination exact planned digest and operation identity can be bound → recover/verify existing;
- same bytes without operation identity → contract may adopt, otherwise conflict;
- different/unknown state → conflict or indeterminate.

### Append/correction

- exact operation ID/request digest record at valid chain/head → deduplicate;
- same operation ID with different digest → conflict;
- invalid/torn tail → recovery required, no append;
- expected predecessor head still current → retry may append;
- later unrelated valid records exist → contract-specific conflict/inspection; no blind append.

### Copy/create

- every destination exact expected digest and policy permits existing → recover verified result;
- subset exact, remaining absent → complete only after static-plan/idempotency/recovery checks;
- any different digest → conflict;
- unreadable/racing destination → indeterminate.

## 9. Concurrency

Concurrent same-key requests require one intent-registration serialization boundary. Both must not independently conclude “absent.”

Future implementation may use:

- target-local lock and intent create-if-absent;
- atomic local index entry plus target verification;
- contract result stream identity.

A global database is not required by specification. Any index remains rebuildable and cannot override canonical result/evidence.

## 10. Retry rules

- No stable key: no general retry guarantee; caller must inspect.
- Same key/digest verified success: no-op return existing.
- Same key/different digest: permanent conflict until a new key.
- Partial/unverified/indeterminate: inspect first.
- Retry cannot weaken contract version, mechanism, write scope, or verification.
- Retry after contract upgrade is a new exact contract identity unless a migration policy explicitly maps it.
- Automatic retry loops/scheduling are outside Core.

## 11. Failure and exit behavior

Idempotency conflict before mutation → `rejected`, non-zero.

Verified existing same-key/same-digest result → `succeeded_verified`, exit 0, `execution_disposition: reused_existing`, `mutation_attempted: false`, and no new effect receipt.

Unresolved previous intent → `indeterminate` or existing partial/unverified status, non-zero.

## 12. Security/claim limits

- SHA-256 collision resistance is assumed, not mathematically guaranteed.
- Key secrecy is not required; keys must not contain secrets.
- Key ownership/authentication is external policy.
- Local privileged users can alter intent/receipt/result without signing/WORM.
- Receipt history alone does not prevent complete deletion/rollback/recomputation.

## 13. Mandatory future tests

- concurrent first use of one key;
- same key/same digest;
- same key/different digest;
- same key across different scope/contract versions;
- crash before and after durable intent;
- crash at each mechanism boundary;
- stale/corrupt receipt index;
- canonical result exists but receipt missing;
- receipt exists but result changed;
- partial multi-effect completion;
- committed result with evidence finalization failure;
- indeterminate unreadable target;
- append record identity collision;
- adopted-existing policy versus operation-created claim.
