# Stage 4 Spec Deviations

This document records implementation corrections made during Stage 4 acceptance hardening. It is not a backlog and does not list planned features.

## Corrections

- Append plans now use one `append_record` mechanism boundary for both absent-stream initial records and expected-head appends. The broker no longer routes initial append plans through `exclusive_create`; absent creation is owned by the append mechanism under an explicitly supplied evidence-root operational lock.
- This intentionally chooses initial-open creation through the unified append mechanism, even where earlier proposal language implied a separate create path for first task records.
- Stage 4 keeps a single intent/effect/mechanism meta-schema. It does not introduce proposal-era multiple task-specific intent schemas.
- JSONL stream heads now use a neutral canonical JSONL v1 policy rather than contract IDs. The codec requires UTF-8 canonical JSON objects with exactly one LF per record and rejects blank records, CRLF, noncanonical records, invalid JSON, and truncated tails.
- Append receipts include neutral append observations: `operation_identity`, `request_digest`, `record_identity`, `append_offset`, `record_digest`, `record_length`, `bytes_written`, before/after state, and `resulting_head`.
- Existing invalid stream tails are classified distinctly as target invalidity and are never truncated, repaired, rewritten, or deleted.
- Task journal record construction remains in the task journal contract adapter; shared core, broker, and mutation mechanisms do not interpret task lifecycle fields.
- Task journal candidates must carry caller-supplied `operation_id` and `idempotency_key`; minimal v1 requires them to be equal. Serialized task records use wire `record_type` values `task_open`, `task_event`, `task_close`, and `task_correction`; candidate actions remain `open`, `event`, `close`, and `correction`.
- Task journal event hashes are canonical JSONL append-head hashes over the record line with `event_hash` set to the empty string, the previous head, previous byte length, and codec domain `task_journal.v1`.
- Correction records append only `task_correction` and identify the corrected record by exact `(task_id, target_sequence, target_event_hash)`. Projection exposes the correction relation and does not rewrite the raw terminal outcome.
- Canonical result references expose only generic `appended_record` metadata for append effects. Task projection remains contract adapter output, not core result shape.
- Idempotent reuse is restricted to prior `succeeded_verified` evidence whose receipt, intent, effect receipt, generic append metadata, and exact prior appended byte range can be inspected against the current target. Later valid records may exist after that prior byte range.
- Same key/different digest conflicts before mutation. Same key/same digest with missing receipts, non-verified receipts, committed-unverified, partial, indeterminate, or failed finalization is rejected as inspection-required and is not executed.
- Same key/same scope registration is serialized with a shared evidence-root operational lock from lookup through durable intent and terminal completion.
- Phase intents carry `execution_requested`; dry-run intents are ignored for execute idempotency if no receipt exists, while receipt-less execute intents block as inspection-required. The broker refuses execute attempts whose durable intent does not request execution.
- Similar journal bytes without exact prior Phase append evidence are not accepted as idempotent reuse.
- `task_verify` is deferred; Stage 4 validates stream structure, append identity, and correction identity only.

## Schemas

- `effect-plan.schema.json` permits `append_record` with absent preconditions for initial append creation and present preconditions for expected-head append.
- `effect-receipt.schema.json` admits append-specific observation fields while preserving closed-schema validation.

## Tests

- Added regressions for the append boundary, broker non-use of `exclusive_create` for initial append, strict JSONL head vectors, two-process absent-stream races, Core idempotency races, lock acquisition failure, evidence-root lock files, and Stage 4 architecture scans.

## Core Neutrality

- Core remains lifecycle-only and does not branch on fixture, task, or effect identifiers.
- Task journal domain logic stays in `phase_tool.contracts.task_journal_v1`.

## Bounded Risks

- Windows durability is bounded to file-data `fsync` behavior available through the local Python runtime and platform filesystem. Directory-entry durability is not claimed for append creation beyond the declared local policy.
- The append lock is cooperative. Non-cooperating writers that bypass the evidence-root operational lock protocol can still race target bytes; such interference is detected where reread/readback/head verification observes it, but the mechanism cannot prevent it at the OS boundary.
