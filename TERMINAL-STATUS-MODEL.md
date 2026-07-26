# Terminal Status Model

Status: Stage 1 normative specification; no runtime implementation exists.

## 1. Purpose

Phase Core reports one terminal status in the canonical receipt. The status describes what Core can substantiate about the controlled operation, not what an adapter hoped to do.

Terminal statuses are mutually exclusive:

```text
rejected
aborted
failed_no_effect
failed_partial
committed_unverified
indeterminate
succeeded_verified
```

All statuses except `succeeded_verified` require a non-zero process exit code.

## 2. Required receipt dimensions

Status classification uses independent receipt fields:

- `execution_disposition` — `not_executed`, `executed`, or `reused_existing`;
- `mutation_attempted` — whether a trusted mechanism began a target-effect attempt;
- `result_state` — `none`, `verified_no_effect`, `known_partial`, `committed_unverified`, `indeterminate`, or `verified_result`;
- effect receipts and before/after observations;
- evidence finalization status;
- `retry_disposition`;
- `recovery_required`;
- blockers and exit code.

A missing receipt after a durable intent is not a status. Recovery inspection must derive and write a truthful receipt if possible.

## 3. Status matrix

| Status | Disposition | Mutation attempted | What is known | Retry | Recovery | Success exit |
|---|---|---:|---|---|---|---:|
| `rejected` | `not_executed` | No | Contract/candidate/input/policy/plan was unacceptable before mutation | Only after changing rejected input/config; same request is not retried automatically | No target recovery; diagnostic correction only | No |
| `aborted` | `not_executed` | No | Explicit cancellation occurred before mutation | New explicit invocation allowed | No target recovery | No |
| `failed_no_effect` | `executed` | Yes | Post-inspection positively establishes no target effect after a mechanism attempt | Idempotent retry may be allowed by contract | Usually no; inspect evidence first | No |
| `failed_partial` | `executed` | Yes | A known subset/partial byte range/effect occurred | No blind retry; only mechanism-specific recovery/idempotent completion | Required | No |
| `committed_unverified` | `executed` | Yes | Commit/result state is positively observed, but a required post/evidence predicate is not verified | No automatic replay | Required; verify target/evidence and finalize or correct | No |
| `indeterminate` | `executed` | Yes | Core cannot establish whether or how mutation occurred after an attempt began | Forbidden until inspection resolves state | Required | No |
| `succeeded_verified` | `executed` or `reused_existing` | Yes, or no for verified reuse | All contract success predicates, canonical result reference, and required evidence passed | Same-key same-digest may return existing verified outcome | No | **Yes, exactly 0** |

## 3.1 Deterministic classification precedence

After `intent.json` exists, the future classifier applies this precedence to the frozen plan, durable effect markers, effect observations, validator results, and evidence state:

1. no target-effect attempt and invalid/untrusted/unacceptable request → `rejected`;
2. no target-effect attempt and explicit cancellation → `aborted`;
3. any attempted effect with target state that cannot be distinguished → `indeterminate`;
4. at least one known applied/partial effect and at least one required effect not successfully verified → `failed_partial`;
5. complete intended commit/result is positively observed but a required domain/evidence predicate is not verified → `committed_unverified`;
6. a mechanism attempt occurred and positive observation establishes no target effect → `failed_no_effect`;
7. every required predicate/effect/evidence item is verified, or exact prior verified outcome is reused → `succeeded_verified`.

A missing marker, missing observation, timeout, or inaccessible target never counts as proof of no effect. A recovery finalizer may derive the previously implied terminal outcome, but may not rewrite an already valid terminal receipt to a more favorable status.

## 4. `rejected`

Classification conditions:

- no trusted mutation mechanism was invoked;
- a blocking validator failed or was unknown;
- exact contract/registry/mechanism resolution failed;
- contract version/digest/Core compatibility failed;
- plan/write scope/path policy failed;
- idempotency key conflict was detected before mutation.

Required receipt:

- `mutation_attempted: false`;
- `result_state: none`;
- null canonical result;
- no applied effect receipt;
- one or more blockers;
- non-zero exit.

A domain result that pre-existed is not claimed as produced by this rejected operation.

## 5. `aborted`

`aborted` is reserved for explicit cancellation after acceptance but before mutation. It is not a synonym for validator failure or process crash.

Required proof:

- cancellation source/reason is recorded;
- broker confirms no effect attempt began;
- target observation is optional unless needed to distinguish from a race;
- non-zero exit.

Cancellation after mutation begins cannot be `aborted`; classify by observed effect state.

## 6. `failed_no_effect`

Use only when Core can establish no target effect despite an attempted/failed operation. Examples:

- exclusive create failed before creating a destination;
- stale expected-head rejected under lock;
- content-addressed destination conflict detected before publication;
- temporary bytes were written only inside Core-owned disposable staging and removed, while canonical target remained unchanged.

It is not valid when target inspection is unavailable or a partial canonical file may remain.

## 7. `failed_partial`

Use when at least one intended target effect or a partial canonical effect is known and aggregate success predicates did not pass.

Examples:

- first copy effect succeeded, second failed;
- append wrote a truncated tail;
- destination object was created but contains fewer bytes than planned;
- correction relation was appended but another required effect failed.

Receipt must identify known applied, failed, and not-reached effects. `rollback planned` does not remove partial status.

## 8. `committed_unverified`

Use only when the complete intended commit/result state is positively observed, but Core cannot claim verified success because:

- post-operation verifier failed or was unavailable;
- required receipt/attachment finalization failed after result commit;
- final read-back/hash/head check did not complete;
- result schema/evidence validation failed despite observed commit.

This status must preserve the best available result reference marked unverified. It is not `failed_no_effect` and must not trigger blind replay.

## 9. `indeterminate`

Use when available observations cannot distinguish states such as:

- no effect versus partial effect after crash;
- old result versus newly committed result;
- expected bytes versus concurrent replacement;
- effect completed but target is currently unreadable;
- registry/evidence changed after mutation began and binding cannot be reconstructed.

`indeterminate` is fail-closed but does not assert no mutation. Recovery inspection is mandatory.

## 10. `succeeded_verified`

All must hold:

1. exact contract/registry/mechanism bindings passed;
2. all blocking validators passed;
3. effect plan and write scope passed;
4. every required newly executed effect is `applied_verified`, or `execution_disposition: reused_existing` is bound to an exact prior verified outcome;
5. post-operation predicates passed;
6. canonical result reference is schema-valid and resolves under the declared authority rule;
7. required attachments exist and match digests;
8. receipt validates against the receipt schema;
9. no blocker remains;
10. exit code is 0.

Schema validity alone never establishes these conditions.

## 11. Suggested exit-code classes

The public mapping is provisional until CLI specification, but v1 must preserve this distinction:

| Exit | Class |
|---:|---|
| 0 | `succeeded_verified` only |
| 10 | `rejected` |
| 11 | `aborted` |
| 20 | `failed_no_effect` |
| 21 | `failed_partial` |
| 22 | `committed_unverified` |
| 23 | `indeterminate` |
| 24 | receipt could not be finalized; intent requires inspection |

Adapters must propagate, not normalize, non-zero outcomes.

## 12. Semantic conformance rules

JSON Schema checks shape and some status-field conditionals. A future terminal-classifier conformance suite must additionally check:

- receipt effect set equals the frozen plan;
- status agrees with every effect receipt;
- no `rejected`/`aborted` receipt contains an attempted effect;
- `failed_no_effect` has verified unchanged canonical target;
- partial/unverified/indeterminate cannot use exit 0;
- succeeded receipt has all required validator/evidence results;
- timestamps/order and result bindings are coherent;
- unknown validator outcomes block success when declared blocking.
