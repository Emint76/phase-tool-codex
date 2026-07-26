# Revised Roadmap — Phase Tool

Status: proposed sequencing after Iteration 0.5. No later stage is authorized by this roadmap alone.

## Principles

1. Build one universal core, not three domain runtimes.
2. Use `task_journal.v1` as the first real vertical slice, not as core vocabulary.
3. Prove mechanisms first with synthetic conformance fixtures, then a real contract.
4. Validate generality against source and knowledge admission after task journaling works.
5. Keep legacy Phase2/3/4 until parity and explicit deprecation.
6. Every guarantee requires a component boundary, negative tests, and platform scope.
7. No live KB/OpenClaw mutation in development validation.

## Iteration 0.5 — Phase Core Generalization

Artifacts:

- strategic correction;
- core architecture;
- contract model;
- current Phase decomposition;
- `task_journal.v1` proposal;
- repository transition plan;
- revised roadmap;
- independent architecture review.

Stopping condition:

- universal boundary answers the four review questions;
- only new documents changed;
- no code, rename or commit.

## Stage 1 — Contract and guarantee specification

Purpose: define executable contracts before runtime implementation.

Artifacts:

- ADR: core/contract/adapter ownership;
- ADR: contract trust and extension registry;
- ADR: hard anti-control-plane architecture budget and rejection gate;
- Phase contract JSON Schema;
- core evidence/result schemas;
- generic terminal status model;
- freeze strategy specification;
- effect-plan and effect-receipt schemas;
- write-scope/path policy;
- idempotency protocol;
- correction/compensation/rollback semantics;
- Windows/Linux filesystem guarantee matrix;
- golden vectors and negative fixture catalog;
- non-executable `source_admission.v1` and `knowledge_admission.v1` contract exemplars covering profile/taxonomy bindings without core vocabulary.

Synthetic contracts:

- `fixture_append.v1` to test append/create without task semantics;
- `fixture_copy.v1` to test copy/create and partial failure without admission semantics.

Stopping condition:

- schemas validate positive fixtures and reject adversarial fixtures;
- neither synthetic contract requires task, KB, source, knowledge, Hermes, or Phase2/3/4 fields;
- source/knowledge exemplars validate against the same contract meta-schema without enabling execution or claiming parity;
- registry ownership, installation trust root, exact extension digest binding and v1 prohibition of third-party mutation executors are explicit;
- any request to add routing, approval, orchestration, taxonomy/profile interpretation or registry administration to core fails unless a separate approved ADR and two-contract proof justify it;
- conceptual overlap or two schemas do not stabilize a plugin/mechanism ABI; stable public core seams require two independent mutation-bearing implementations with matching semantics and conformance tests;
- the core evidence model uses one machine-readable receipt plus only the durable intent/frozen attachments needed for recovery, not a mandatory Phase3-style report tree;
- privacy/security ADR exists before any real original instruction is appended.

## Stage 2 — Minimal Phase Core, validation-only first

Purpose: implement core without target mutation.

Order:

1. contract resolver and digest/version binding;
2. run/evidence directory and safe IDs;
3. candidate capture;
4. input freeze/hash strategies;
5. validator runner;
6. plan generation/validation;
7. evidence/result schema validation;
8. `phase validate`, `phase plan`, `phase inspect`.

Tests:

- untrusted contract/mechanism rejection;
- mutated input and TOCTOU fixtures;
- traversal/symlink/reparse/reserved-name rejection;
- reached-step evidence on early failure;
- deterministic output/golden vectors;
- native Windows and Linux/WSL.

Stopping condition:

- no mutation mechanism is enabled;
- fixture contracts produce deterministic validated plans/evidence;
- no Phase2/3/4 wrapper needed.

## Stage 3 — Controlled effect mechanisms

Purpose: implement the smallest trusted mutation surface.

Initial mechanisms:

- exclusive create;
- expected-head append under lock;
- content-addressed copy/create;
- effect receipt and immediate post-verification.

Deferred:

- arbitrary update;
- automatic rollback;
- arbitrary external executors;
- multi-root transactions;
- remote/network filesystems.

Required tests:

- concurrent append/copy;
- stale head/pre-state;
- short/torn write and process crash;
- partial multi-effect copy;
- same-hash idempotency and conflicting hash;
- fsync/`FlushFileBuffers`/directory semantics for claimed platforms;
- result committed but evidence finalization failed;
- broker-only write-scope enforcement and explicit limits.

Stopping condition:

- synthetic append/copy contracts pass the platform matrix;
- `failed_partial`, `committed_unverified`, and `indeterminate` are observable and not masked.

## Stage 4 — First real vertical slice: `task_journal.v1`

Purpose: prove a useful end-to-end Phase contract. This is the first real domain vertical slice; the earlier source/knowledge exemplars are schema/design probes only.

Slice order:

1. `task_open` through one exclusive create-with-first-record effect;
2. `task_event` through expected-head append;
3. `task_close` with explicit partial/failure/unfinished data;
4. read-only verify;
5. recorded `task_verify`;
6. correction/amendment;
7. raw show and deterministic list;
8. search/export projections.

Contract-owned work:

- task schemas/state machine;
- exact-input policy;
- event canonicalization/hash chain;
- task ID profile;
- artifact observation scopes;
- correction projection;
- privacy/retention policy.

Core-owned work:

- resolver, freeze, lock/append/create, generic idempotency, result/evidence finalization.

Stopping condition:

- standalone CLI works on Windows and Linux/WSL;
- task vocabulary is absent from core modules/schemas;
- corruption/concurrency/privacy tests pass;
- no adapter required for correctness.

At this point task-journal-driven abstractions remain provisional. They may be internal implementation seams, but are not frozen as a general third-party plugin ABI before a second mutation-bearing contract confirms them.

## Stage 5 — Thin agent adapters

Order:

1. Hermes adapter/skill;
2. Codex adapter/instructions;
3. OpenClaw adapter/skill.

Adapter tests:

- exact contract version invocation;
- attribution mapping is declared, not authenticated;
- no direct task stream/evidence writes;
- non-zero Phase status not masked;
- no canonical output duplication;
- compatibility/version refusal.

Stopping condition:

- deleting an adapter leaves core/contract behavior unchanged;
- all adapters call the same standalone Phase interface.

## Stage 6 — `source_admission.v1` compatibility validation

Purpose: prove copy-based admission uses the same core without weakening it.

Inputs:

- Stage1/Stage2 source fixtures from `crab-control-plane` at `f6c19d…`;
- existing review, package, manifest, placement and destination-hash expectations.

Work:

- define source candidate/contract directly, avoiding a separate Stage2→Phase3 bridge;
- reuse generic copy/create effect mechanism;
- implement provenance/review/placement validators as contract extensions;
- run legacy-versus-new differential tests in disposable roots;
- compare rejection, idempotency, result and evidence surfaces.

Stopping condition:

- no source/KB terminology enters core;
- destination hash and refusal parity are demonstrated;
- known legacy TOCTOU/declared-scope overclaims are not reproduced;
- no live KB write.

## Stage 7 — `knowledge_admission.v1` compatibility validation

Purpose: test richer instance policy without expanding core.

Work:

- knowledge package/profile/taxonomy bindings;
- selected-profile and selected-type validators;
- instance config outside product repository;
- copy/create result and lineage verification;
- legacy fixture differential tests in disposable workspace roots.

Stopping condition:

- profile/taxonomy semantics remain contract/instance policy;
- Phase Core unchanged except proven generic mechanism defects;
- adding a knowledge profile requires config/contract data, not core branches;
- no live KB mutation.

## Stage 8 — Legacy wrapper migration/deprecation decision

Candidates:

- Phase2 audit/scaffold wrappers;
- Stage2 handoff bridge;
- Phase3 hard-coded target router;
- duplicate repo/KB copy libraries/schemas;
- Phase4 wrapper;
- orchestration smoke wrapper;
- manual live skill hash registry.

For each candidate:

1. map legacy inputs/outputs/guarantees;
2. prove replacement parity and intentional differences;
3. retain compatibility adapter if needed;
4. publish deprecation period;
5. remove only by explicit approved change.

Stopping condition:

- no live consumer depends on removed entrypoint;
- canonical result/evidence ownership remains unambiguous;
- history and migration documentation remain available.

## Stage 9 — Packaging and publication

Only after contract/core/admission proof:

- final repository/product name decision;
- optional in-place rename preserving Git history;
- Python 3.11+ package;
- `uv tool install` and `pip install` paths;
- signed/versioned releases if required;
- installation/update/rollback documentation for the tool itself;
- security review and supply-chain checks;
- public compatibility matrix.

## Cross-stage quality gates

At every stage report:

- exact source/contract/tool versions;
- changed files;
- tests and real outputs;
- independent review;
- implementation boundaries for each guarantee;
- open High risks;
- commit hash only if a commit was authorized and created.

Do not proceed automatically from one stage to the next. Each stage requires explicit user authorization.
