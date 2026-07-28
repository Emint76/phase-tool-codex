# Admission Ordered Multi-Effect Specification Candidate

Status: **non-executable, neutral candidate**. No active schema, Core, broker, mechanism, CLI, or registry change is made by this document.

## 1. Scope

This candidate defines only the neutral lifecycle needed for an operation with exactly two statically known effects. It contains no source, knowledge, KB, provenance, taxonomy, review, or placement-domain vocabulary.

The Core lifecycle remains one lifecycle. Contracts own domain planning; Core sequences an immutable plan; the broker dispatches each effect to its exact bundled mechanism.

## 2. Plan shape

Normative draft shape: `contracts/spec-candidates/admission-v1/schemas/ordered-effect-plan.schema.json`.

A future versioned effect-plan extension MUST provide:

- `effect_order: static_predeclared`;
- `effects`: schema-valid array with exactly 2 entries for admission v1;
- fixed ordinal effect labels `effect.0.blob` and `effect.1.descriptor`, unique only within one plan; the globally meaningful identity is `(plan_digest, effect_id)`;
- explicit ordinal `0`, then `1` with no gaps or duplicates;
- exact mechanism ID/version/package digest on each effect;
- frozen content source, exact content digest/length, target root binding/relative locator, preconditions, durability policy, and `on_failure: stop_and_classify` on each effect;
- one aggregate plan digest covering order, IDs, mechanisms, targets, bytes, policies, and contract binding.

For the admission contract candidates the fixed ordinal labels are `effect.0.blob` and `effect.1.descriptor`. They are not derived from plan contents and are not globally unique by themselves. Exact contract binding, order, mechanisms, targets, and content belong to the immutable plan whose digest scopes both labels. These labels are contract-owned values; neutral runtime branches only on ordinal and generic effect shape.

All inputs, serialized effect bytes, targets, and parent/root observations MUST be frozen and the complete plan MUST pass preflight before durable intent.

## 3. Durable ordering

Required order:

1. validate/freeze/serialize/preflight the full plan;
2. durably publish immutable `intent.json` binding the full plan digest;
3. durably publish `attempt_started` for effect 0;
4. invoke effect 0 mechanism exactly once for that attempt;
5. observe target and durably publish `observation_recorded` for effect 0;
6. only if effect 0 is verified (`applied_new_verified` or `verified_existing`), publish `attempt_started` for effect 1;
7. invoke effect 1 mechanism exactly once for that attempt;
8. observe target and durably publish `observation_recorded` for effect 1;
9. run aggregate post-verification;
10. finalize required attachments and the one canonical Phase receipt.

An unverified, applied-unverified, failed, inaccessible, or indeterminate prior effect blocks every later effect. Missing durable `observation_recorded` also blocks advancement even if process memory says the effect succeeded.

## 4. Per-effect receipts and progress

Every mechanism actually invoked MUST produce one effect receipt, including an invocation that verifies an existing exact object without writing. A not-started effect has no effect receipt.

The required `ordered-effect-progress` attachment validates against the candidate schema and accounts for the complete plan with:

- `completed_effect_ids`;
- `verified_effect_ids`;
- `failed_effect_id` or null;
- `not_started_effect_ids`;
- one ordered item per planned effect;
- state: `not_started`, `failed_no_effect`, `applied_new_verified`, `verified_existing`, `applied_unverified`, or `indeterminate`;
- target and observation digest.

These are structured details, not new terminal statuses.

### Set invariants

- progress effect IDs, order, kinds, mechanisms, and targets equal the plan exactly;
- effect-receipt IDs equal exactly the subset whose mechanisms were invoked;
- journal `attempt_started` IDs equal the invoked subset;
- journal `observation_recorded` IDs equal the subset with durable observations;
- `verified_effect_ids` is a subset of `completed_effect_ids`;
- `not_started_effect_ids` has no journal entry or effect receipt;
- success requires every planned ID verified and no failed/not-started ID;
- a started effect has a non-null observation digest; a not-started effect has a null observation digest;
- completed effects form a plan prefix, and a later effect may start only after every earlier effect is verified.

These cross-field rules are intentionally semantic rather than JSON-Schema-only guarantees. Activation requires the exact-bound neutral validator `phase.ordered_effect_plan_progress_v1`, owned by the common Phase lifecycle layer and listed by both admission contracts. It interprets only immutable plan binding, order, generic effect states, set equality, and observation markers; it contains no source/knowledge vocabulary or policy.

## 5. No atomicity and no rollback

The two effects are not a transaction. Each effect is individually no-replace and post-verified. Earlier verified objects remain if a later effect fails. Runtime MUST NOT delete, overwrite, compensate, or roll back automatically. Cleanup of mechanism-owned temporary files is operational cleanup, not rollback of canonical targets.

Any UI or receipt claim of all-or-nothing behavior is invalid.

## 6. Aggregate classification

Existing terminal statuses are sufficient:

| Observed state | Aggregate status |
|---|---|
| rejected before first mechanism | `rejected` |
| mechanism attempted; positive proof no canonical effect | `failed_no_effect` |
| at least one newly created/partial canonical effect and operation incomplete | `failed_partial` |
| both intended canonical objects positively present but required post/evidence predicate incomplete | `committed_unverified` |
| any attempted effect cannot be distinguished | `indeterminate` |
| all effects/result/evidence verified or exact prior result reused | `succeeded_verified` |

A verified-existing effect is not attributed as created by this run. If effect 0 was verified-existing and effect 1 conflicts without mutation, positive proof of no mutation permits `failed_no_effect`; if effect 0 was newly created, the same effect-1 conflict is `failed_partial`.

## 7. Retry and idempotency

- Same scoped key + same canonical request digest + prior exact `succeeded_verified`: revalidate canonical descriptor, blob, descriptor-to-blob binding, and Phase receipt; then return `reused_existing` without invoking either mechanism.
- Same key + different request digest: `rejected` conflict before mutation.
- Intent-only, partial, committed-unverified, or indeterminate prior run: inspection before any retry.
- Retry never restarts at ordinal 0 blindly. It revalidates every prior planned target and journal binding.
- A verified existing object may satisfy an effect only after exact digest, length, locator, root authority, and plan binding verification.
- Missing safe completion precondition or any different digest is conflict/inspection-required, not overwrite.
- Concurrent same-key first use requires the existing intent-registration serialization boundary.

## 8. Recovery preconditions

Recovery is read-only until all of these are established:

- exact original contract, request, intent, plan, mechanism and root bindings are available;
- plan and progress/effect/journal sets are coherent;
- every prior target is inspected against exact digest/length/locator;
- no conflicting descriptor/result exists;
- every missing effect is idempotent and its destination is absent;
- source frozen bytes and descriptor bytes still match the original plan;
- previous status permits completion.

A recovery completion is a new run/reference linked to the original run. It never rewrites original intent, journal, effect receipts, or valid terminal receipt.

## 9. Required edge behavior

### Existing verified blob + absent descriptor

If the blob exactly matches plan and authority, effect 0 is recorded `verified_existing`; effect 1 may run after the durable observation marker. If descriptor is then verified, aggregate success is allowed. The receipt must not claim the blob was created by this run.

### Existing descriptor conflict

Full preflight should detect a different descriptor before effect 0 and reject without mutation. If a race creates the conflicting descriptor after a newly verified effect 0, stop and classify `failed_partial`. Never replace the descriptor.

### Descriptor exists + blob absent

The canonical pair is inconsistent. Normal admission is rejected/inspection-required; it must not create a blob under an existing descriptor and silently adopt the descriptor.

### Evidence failure after effect 0

No effect 1 handoff. Newly created effect 0 yields `failed_partial` when positively known, otherwise `indeterminate`. Verified-existing effect 0 with positively unchanged targets can yield `failed_no_effect`. Recovery is required.

### Evidence failure after both effects

If both canonical objects are positively observed but aggregate verification or required attachment/receipt finalization fails, classify `committed_unverified` when a receipt can be finalized. If canonical receipt publication itself fails, the absence of a receipt is not a status; inspection uses intent/journal/targets and may later finalize truthfully.

## 10. Inspection

Inspection reports plan order, per-effect marker/receipt/target state, completed/verified/failed/not-started sets, canonical pair consistency, result-reference resolvability, retry disposition, and recovery requirement. Inspection MUST NOT mutate targets, synthesize success from blob presence, or trust an invalid receipt/index.

## 11. Result reference

The aggregate Phase canonical result reference points to the immutable descriptor locator/digest. Contract-owned post-verification resolves the descriptor and verifies its bound blob. The receipt binds both effect receipts. The descriptor remains the metadata authority; the receipt remains execution evidence.

## 12. Activation blockers

Runtime activation is prohibited until a future coding stage provides and crash-tests:

1. versioned per-effect mechanism binding in plan/intent/receipt semantics;
2. durable journal ordering on Windows and POSIX;
3. plan/progress/journal/receipt set conformance;
4. recovery inspection for every boundary;
5. two-effect failure/crash injection;
6. existing/missing/conflicting target matrix;
7. evidence-finalization failures after each ordinal;
8. Core-neutral architecture scans.
