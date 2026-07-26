# Stage 2 Specification Deviations

Stage 2 changes remain uncommitted. This ledger records only implementation-driven corrections to the provisional Stage 1 baseline.

## D2-001 — Validation-only receipt outcome

- **Implementation blocker:** `phase-receipt.schema.json` could represent successful execution only as `succeeded_verified`, which requires `mutation_attempted: true`, effect receipts, and a canonical domain result. Stage 2 must report a successful validated static plan while truthfully asserting that no target mutation or canonical result occurred.
- **Minimal correction:** add terminal status `validated_planned` and result state `planned_no_effect`. Constrain them to `execution_disposition: not_executed`, `mutation_attempted: false`, no canonical result, no effect receipts, finalized evidence, at least one validator result, no blockers, no recovery, and exit code 0.
- **Executable tests:** `tests/test_stage2_receipt_schema.py::test_validation_only_receipt_is_schema_valid`.

## D2-002 — Early failure before intent creation

- **Implementation blocker:** exact contract/registry rejection can occur before a static plan and therefore before a truthful `intent.json`, while the Stage 1 receipt schema required a non-null intent digest for every outcome.
- **Minimal correction:** allow `evidence.intent_digest` to be null. Successful `validated_planned` still requires an exact digest. Early `rejected`/`aborted` receipts may use null.
- **Executable tests:** `tests/test_stage2_receipt_schema.py::test_early_rejection_can_truthfully_have_no_intent`.

## D2-003 — Exact schema binding consistency

- **Implementation blocker:** the two fixture contracts contained candidate- and receipt-schema digests that did not match the committed schema bytes, and referenced fixture result schemas that did not exist locally. An exact local resolver must reject those packages and cannot silently fetch or ignore the missing bindings.
- **Minimal correction:** add `fixture-append-result.schema.json` and `fixture-copy-result.schema.json`; update only the candidate, result, and receipt schema digests in `fixture_append.v1.json` and `fixture_copy.v1.json` to the exact current bytes.
- **Executable tests:** `tests/test_canonical_registry.py::test_exact_bundled_contract_resolution_succeeds`; the resolver recomputes every declared schema digest from bundled local bytes.

## D2-004 — Effect content source binding

- **Implementation blocker:** `effect-plan.schema.json` recorded only the derived content digest and an operation-specific nullable `input_binding`; append effects therefore could not prove which captured candidate they were derived from, contrary to the Stage 2 requirement that every effect bind to captured/frozen input.
- **Minimal correction:** require inert `content_source` with kind `captured_candidate` or `frozen_input`, a nullable/required binding ID selected by kind, and the exact source digest. No locator, code, command, or execution hook is added.
- **Executable tests:** `tests/test_validation_planning.py::test_append_and_copy_use_same_static_plan_api`; semantic plan validation rejects source digest/binding mismatches.

## D2-005 — Additive Stage 2 CLI result schema

- **Implementation need:** the standalone `validate`, `plan`, `inspect`, and unconditional `execute` refusal commands emit a common machine-readable result envelope. Acceptance requires each CLI output to be validated locally rather than treated as untyped console text.
- **Additive artifact:** add `schemas/stage2-command-result.schema.json` and its bundled immutable registry copy. This schema describes only the Stage 2 CLI envelope and does not change any Stage 1 contract, intent, receipt, validator-result, effect-plan, or domain-result semantics.
- **Executable verification:** real CLI smoke outputs are validated against this exact schema during the Stage 2 final verification gate; `_write` also validates every emitted command result against the bundled local schema before writing stdout.
