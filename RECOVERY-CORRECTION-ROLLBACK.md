# Recovery, Correction, and Rollback

Status: Stage 1 normative distinction; no recovery/rollback executor exists.

## 1. Terms are not interchangeable

- **Retry:** submit the same scoped request again.
- **Recovery inspection:** read intent, receipts, plan, target, and attachments to establish current state.
- **Append correction:** add a new immutable record that corrects/supersedes facts without rewriting prior bytes.
- **Compensating operation:** a new forward operation intended to counter a prior verified effect.
- **Snapshot restore:** replace state from an exact before-image under a compare-and-swap precondition.
- **Separate rollback contract:** an independently versioned/validated contract with its own candidate, effects, verification, and receipt.

A rollback plan or handoff is not executable rollback.

## 2. Default policy

Automatic rollback is prohibited by default and the contract schema fixes `automatic: false`.

Reasons:

- rollback may fail or compound partial state;
- pre-existing same-hash results must not be deleted;
- multi-effect ordering and external concurrent changes matter;
- append history should not be rewritten;
- restore durability/path semantics differ by platform;
- current Phase evidence shows planned-only rollback, not a general mechanism.

## 3. Retry

Retry is governed by `IDEMPOTENCY-PROTOCOL.md`.

It is allowed only when:

- scope/key/request digest match;
- exact contract/mechanism binding is still available;
- current result/effect state is established;
- mechanism-specific recovery says replay/completion is safe;
- no different-digest conflict exists.

Schedulers/retry queues are outside Core.

## 4. Recovery inspection

Triggered by:

- durable intent without receipt;
- `failed_partial`;
- `committed_unverified`;
- `indeterminate`;
- receipt/result disagreement;
- changed or missing required attachment.

Inspection is read-only and produces validator results plus one of:

- resolved `failed_no_effect`;
- resolved `failed_partial` with known effects;
- resolved `committed_unverified`;
- finalized `succeeded_verified` if all original predicates/evidence can now be established without new domain mutation;
- remains `indeterminate`;
- recommendation for retry/correction/compensating/separate rollback operation.

Inspection must not silently mutate or repair the target.

## 5. Append correction

Use for append-only records where history remains canonical.

Requirements:

- new correction has a distinct operation ID;
- references exact prior result/record ID/digest/head;
- records reason and corrected/additional facts according to contract;
- executes through the same controlled append mechanism;
- leaves prior bytes unchanged;
- projection exposes original and correction/supersession relation;
- does not convert a prior failed/partial outcome into unqualified historical success.

Core recognizes only `correction` intent and append relation evidence; domain semantics belong to contract validators.

## 6. Compensating operation

A compensation is a new forward effect, not time reversal.

Requirements:

- separate candidate and durable intent;
- exact reference to prior receipt/effects;
- contract-authorized compensation policy;
- current-state preconditions proving compensation will not overwrite later work;
- own effect plan, terminal status, result and receipt;
- prior receipt remains unchanged;
- compensation failure is independently visible.

Examples may include creating a tombstone or deleting an object proven to have been created by the prior operation, but delete is not a v1 mechanism. Therefore executable compensation that requires deletion is deferred.

## 7. Snapshot restore

Deferred design, not a v1 mechanism.

Future requirements:

- exact frozen before-image bytes/digest and provenance;
- exact prior operation final digest;
- current state must still equal that final digest/token;
- race-resistant CAS replacement;
- policy for intervening dependent operations;
- restore durability and post-verification;
- independent result/receipt;
- Windows/Linux implementation and crash tests.

If current state differs, restore is rejected, not forced.

## 8. Separate rollback contract

For high-risk operations, rollback may be a separate exact contract. It:

- is selected outside Core routing;
- has its own candidate/schema/trust binding;
- references prior receipt and before-state evidence;
- declares bounded effects and write scope;
- uses only supported bundled mechanisms;
- passes all normal validation/freeze/plan/execute/verify stages;
- cannot receive privileged bypass status.

V1 has no general rollback contract because update/delete/restore mechanisms are not implemented.

## 9. Mechanism recovery table

| Mechanism/result | Retry | Correction | Compensation | Restore/rollback |
|---|---|---|---|---|
| Exclusive create, verified no effect | Safe with same key/digest after recheck | Domain-dependent | Not needed | No |
| Exclusive create, exact result exists | Verify/finalize; no duplicate create | Domain-dependent | Only future policy if operation-created and unchanged | Deferred |
| Append, valid record exists | Deduplicate | New append correction allowed by contract | Never delete/rewrite history | Forbidden for canonical stream |
| Append, torn tail | No append; inspect/quarantine/repair policy outside normal operation | Correction only after trusted chain boundary restored | No automatic action | No rewrite claim |
| Copy, subset applied | Inspect; complete safe missing effects only | Domain metadata correction possible | Future operation only | Deferred |
| Copy, different destination hash | Conflict | Domain-dependent | Never overwrite/delete blindly | Separate future contract |
| Committed but evidence failed | Verify/finalize existing result | If domain facts need correction | Not before inspection | Not automatically |
| Indeterminate | Forbidden | Not until state known | Not until state known | Not until state known |

## 10. Evidence

Recovery-related receipt fields include:

- prior run/intent/receipt references;
- inspection validators and observation time;
- target before/current states;
- decision and blockers;
- retry disposition;
- recovery required;
- selected policy;
- new operation reference for correction/compensation/rollback;
- no claim that a plan was executed without an effect receipt.

## 11. Multi-effect recovery evidence

`intent.json` alone is sufficient to prove authorization and the frozen plan, but not to prove which effect was reached. For any plan with more than one target effect, the future runtime must use the durable per-effect journal defined by `EVIDENCE-MODEL.md` and `schemas/effect-journal-entry.schema.json`.

Recovery rules:

- missing `attempt_started` marker means that effect was not authorized for handoff;
- `attempt_started` without a durable observation marker requires target inspection and defaults to `indeterminate` when state cannot be established;
- every next effect is blocked until the prior observation marker is durable;
- recovery creates a new run/reference and never rewrites the original intent, marker chain, or valid receipt;
- without executable crash tests for marker durability/order, multi-effect runtime execution is prohibited.

## 12. Terminal status interaction

- `rejected`/`aborted`: no target recovery.
- `failed_no_effect`: retry may be allowed.
- `failed_partial`: recovery required; no success exit.
- `committed_unverified`: verify/finalize first; no replay.
- `indeterminate`: inspection mandatory; retry forbidden.
- `succeeded_verified`: no recovery; later correction/compensation is a new operation.

## 13. Mandatory future tests

- intent without receipt at each mechanism boundary;
- same-hash existing created by another operation;
- partial multi-effect copy;
- append torn tail;
- result committed but receipt/evidence write fails;
- target changed after prior result;
- correction points to wrong digest/head;
- compensation against intervening change;
- restore without before image;
- restore CAS conflict;
- rollback plan exists but no executor;
- automatic rollback request rejected;
- prior history/evidence remains immutable through correction/compensation.
