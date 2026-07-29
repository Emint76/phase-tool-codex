# Stage 6 Spec Deviations

This ledger records implementation-driven deviations from the Stage 6 source admission candidate.

## D6-001 - Active plan schema keeps Stage 5 compatibility

- **Implementation blocker:** the active plan/intent schema had one top-level mechanism, while source admission needs per-effect mechanisms.
- **Minimal correction:** add optional `effect.mechanism`, `effect.ordinal`, and `effect.locator_policy_id` while preserving the existing top-level `mechanism` for Stage 2-5 plans.
- **Regression references:** `tests/test_stage6_source_admission.py::test_source_execute_writes_blob_descriptor_progress_and_inspects`; Stage 2-5 regression subset remains green.

## D6-002 - Versioned content-addressed locator policy

- **Implementation blocker:** Stage 5 `content_addressed_copy` enforced `objects/<digest>`, while source admission requires `blobs/sha256/<prefix>/<digest>`.
- **Minimal correction:** add neutral `locator_policy_id` values for flat and sharded SHA-256 layouts. Stage 5 plans omit it and keep flat behavior.
- **Regression references:** `tests/test_stage6_source_admission.py::test_source_execute_writes_blob_descriptor_progress_and_inspects`; `tests/test_stage5_content_addressed_copy.py`.

## D6-003 - Mechanisms create safe missing target parents

- **Implementation blocker:** source descriptor and sharded blob locators require computed parent directories that did not exist in an empty target root.
- **Minimal correction:** add one shared mutation-boundary `TargetAuthority`. It creates and pins the bounded parent chain, rejects links/reparse points, uses held `dir_fd` authority on POSIX, and holds Windows directory handles without delete sharing so parent replacement cannot redirect create/readback. Both `content_addressed_copy` and `exclusive_create` use it.
- **Regression references:** `tests/test_stage6_source_admission.py::test_source_execute_writes_blob_descriptor_progress_and_inspects`; `tests/test_stage6_source_admission.py::test_source_mechanisms_keep_pinned_parent_authority_during_replacement`; Stage 3-5 path/race suites.

## D6-004 - Ordered progress is multi-effect only

- **Implementation blocker:** emitting the ordered-effect progress attachment for single-effect Stage 5 runs changed deterministic Stage 5 evidence inventory.
- **Minimal correction:** write `ordered-effect-progress.json` only when a plan has more than one effect.
- **Regression references:** `tests/test_stage5_content_addressed_copy.py::test_stage5_hardened_cli_summary_and_walkthrough_values`.

## D6-005 - Neutral executable contract-hook binding

- **Implementation blocker:** the Stage 5 phase-contract schema had no exact binding for a contract-owned executable adapter and described only one operation mechanism.
- **Minimal correction:** add neutral `contract_hook` and per-effect `effect_mechanisms` registered bindings, the `contract_hook` capability, and `admission_canonical_json_v1` to the canonicalization enum. The operation contract contains only exact ID/version/package/capability data. The trusted descriptor contains a code-owned `implementation_id`; no caller-controlled module or factory path is imported.
- **Regression references:** `tests/test_stage6_source_admission.py::test_source_contract_schema_and_hook_are_exact_registry_bound_and_code_owned`; full registry/package integrity verification.

## D6-006 - Preserve a verified ordered prefix on later pre-invocation failure

- **Implementation blocker:** a digest or contract-precondition failure while preparing effect 1 escaped the broker and discarded the in-memory receipt for already verified effect 0, allowing a real blob effect to be reported as a rejection with no effect.
- **Minimal correction:** first-effect preparation failures retain the accepted pre-mutation rejection behavior; later-effect preparation failures produce a validated failed-effect receipt so the broker returns the complete observed prefix and Core classifies it as `failed_partial`/`known_partial`.
- **Regression references:** `tests/test_stage6_source_admission.py::test_source_broker_preinvocation_failure_preserves_verified_prefix`; Stage 5 tamper regressions preserve first-effect rejection semantics.

## D6-007 - Descriptor placement test follows canonical source-result identity

- **Implementation blocker:** the initial concurrency test searched an obsolete `namespaces/.../source-results/...` path and did not independently prove which competing source identity won.
- **Minimal correction:** keep production placement `r/{namespace}/{logical_source_id}/{source_result_id}.json`; independently derive both result IDs and exact locators in the test, require one create-only descriptor, retain both immutable content blobs, reject the legacy locator, and verify truthful loser classification.
- **Regression references:** `tests/test_stage6_source_admission.py::test_source_concurrent_same_identity_different_content_has_one_canonical_descriptor`.
