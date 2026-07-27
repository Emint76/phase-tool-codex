# Stage 3 implementation-driven deviations

Stage 3 adds one neutral executable mechanism, `exclusive_create`. These corrections are limited to contradictions encountered while executing that mechanism; they do not add a workflow language or a domain-specific Core lifecycle.

## D3-001 — frozen bytes for `exclusive_create`

- **Practical problem:** the Stage 1 effect-plan conditional forced `input_binding` to `null` for `exclusive_create`, while the existing `frozen_input` content-source model requires a binding ID. This made it impossible to bind arbitrary binary target bytes to an independently captured and frozen input.
- **Minimal change:** retain the existing `input_binding` union and remove only the `null` restriction from the `exclusive_create` conditional. `captured_candidate` sources still require a null binding; `frozen_input` sources still require a string binding.
- **Executable test:** `test_fixture_create_validate_plans_one_bound_effect_without_target_mutation` checks the exact frozen binding, source digest, content digest, and length; `test_execute_exclusive_create_writes_exact_bytes_and_verified_receipts` verifies the resulting bytes independently.
- **Why Core remains neutral:** binding preparation is confined to the existing planning boundary. `core.py` neither names `exclusive_create` nor reads fixture-specific candidate fields.

## D3-002 — truthful Stage 3 CLI result envelope

- **Practical problem:** the Stage 2 command-result schema fixed `mutation_attempted` to `false`, so it could not represent a real execution result truthfully.
- **Minimal change:** add the versioned `stage3-command-result.schema.json` with a boolean `mutation_attempted`; leave the Stage 2 schema unchanged.
- **Executable test:** `test_cli_validate_plan_execute_and_inspect_fixture_create` exercises all four standalone commands and checks `mutation_attempted=true` only for execute.
- **Why Core remains neutral:** this is a CLI serialization boundary. Core returns the same generic `PhaseOutcome` for every contract.

## D3-003 — executed receipts require durable intent linkage

- **Practical problem:** the Phase receipt schema required an intent digest for `validated_planned`, but did not require it whenever `execution_disposition` was `executed`. A schema-valid mutation receipt could therefore omit the authorization record that must precede mutation.
- **Minimal change:** add one conditional requiring `evidence.intent_digest` to match the existing digest definition whenever `execution_disposition == executed`. No status or field was added.
- **Executable test:** `test_executed_receipt_schema_requires_durable_intent_digest` mutates an otherwise valid executed receipt and proves schema rejection.
- **Why Core remains neutral:** the rule applies to every executed effect and contains no mechanism or contract identity.

## D3-004 — complete evidence writes before broker handoff

- **Practical problem:** the evidence writer performed one unchecked write call. An intent publication short write could be followed by broker invocation even though the complete canonical intent was not persisted.
- **Minimal change:** use an exclusive, unbuffered full-write loop, flush, and file `fsync` for canonical evidence publication. Stage 3 claims `file_data_synced`; it does not claim directory-entry or power-loss durability on every platform.
- **Executable test:** `test_durable_intent_exists_before_mechanism_invocation` observes complete intent and plan files, absence of target and final receipt, immediately before the broker calls the mechanism.
- **Why Core remains neutral:** the correction belongs to `EvidenceStore`; Core only sequences intent publication before broker handoff.

## D3-005 — inspect an intent-only incomplete run without inventing a status

- **Practical problem:** inspection required `receipt.json` first. A failure after target commit but before receipt publication left useful intent/plan/blob evidence unreadable and encouraged synthesis of a terminal status not durably recorded.
- **Minimal change:** when receipt is absent but canonical intent and plan are present, inspection validates their linkage and returns `receipt_present=false`, `inspection_required=true`, and `terminal_status=null`.
- **Executable test:** `test_receipt_finalization_failure_leaves_intent_without_durable_receipt` checks the committed target, durable intent, effect attachment, absent receipt, null receipt digest, and limited inspection result.
- **Why Core remains neutral:** the inspector reasons only about generic evidence relationships and never selects a contract or mechanism.

## Deferred boundary

Verified reuse for same-key/same-request is deferred to Stage 4 because a trustworthy implementation requires exact prior verified-receipt discovery and current-target revalidation. Stage 3 does not treat an existing destination as this run's result and does not synthesize `reused_existing`; it fails closed. Same-key/different-request conflict is implemented before repeated mutation.

## Bounded platform claim

Stage 3 uses an OS exclusive-create primitive, rejects visible links/reparse points, exposes a reparse test seam, and rechecks bytes through the opened operation's resulting path. Lexical/path preflight is not claimed as a complete physical containment guarantee. Windows junction/reparse and Linux descriptor-relative resistance are not production-qualified here; privileged concurrent writers and power-loss durability are also outside the Stage 3 claim.
