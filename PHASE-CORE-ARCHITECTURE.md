# Phase Core Architecture — Iteration 0.5

Status: proposed universal architecture; no implementation is authorized in Iteration 0.5.

## 1. Purpose

Phase Core executes a versioned operation contract through one controlled pipeline:

```text
candidate
→ contract validation
→ frozen input
→ controlled operation
→ post-operation verification
→ canonical result
→ canonical evidence
```

The pipeline is stable. The contract determines the domain, candidate shape, permitted operation, result authority, verification predicates, and evidence obligations.

## 2. Architectural invariants

1. **Contract, not wrapper name, defines the operation.**
2. **One Phase run has one core-owned evidence bundle.**
3. **The contract names one authoritative domain result surface.**
4. **Adapters never own domain result or Phase evidence.**
5. **Mutation is mediated by a registered effect mechanism, not arbitrary contract code.**
6. **Validation success does not imply semantic truth.**
7. **Freeze claims are limited to bytes actually copied/hashed and reverified.**
8. **Post-verification failure cannot be rewritten as success or assumed rollback.**
9. **Partial/indeterminate outcomes are first-class.**
10. **Every guarantee maps to a component boundary and future test.**

## 3. Layers and ownership

### 3.1 Phase Tool interface

A stable CLI/library boundary accepts:

- contract ID/version;
- candidate input;
- named input bindings;
- target bindings permitted by the contract;
- actor/invocation metadata;
- optional idempotency key;
- execution mode (`validate`, `plan`, `execute`, read-only `verify`, `inspect`).

`verify` at the Phase Tool interface is a read-only query over a named run/result and never creates or mutates a domain result. A domain-recorded verification, such as task `verify_record`, is a normal candidate executed through `execute`; it is not a privileged core mode.

It does not expose Phase2/3/4 selection.

### 3.2 Contract resolver

Responsibilities:

- resolve a bundled/installed contract by exact ID/version;
- verify contract digest and core compatibility range;
- reject ambiguous/untrusted contracts;
- load referenced schemas and trusted validator/mechanism IDs;
- freeze the resolved contract bundle into run evidence.

It must not load arbitrary Python/shell paths from contract data.

The extension registry is an installation trust boundary, not contract-owned data:

- Phase Core owns the registry interface and compatibility checks;
- an installation trust policy owns accepted publishers/digests;
- a contract binds validator/mechanism ID, exact version and package digest;
- v1 in-process mechanisms are release-bundled trusted-computing-base components;
- third-party validators, if permitted later, run read-only in a separately specified worker/sandbox and cannot mutate targets;
- third-party mutation executors are out of scope for v1; only the core effect broker performs mutation.

A mutable name-to-code registry or a signature without a configured trust root is insufficient.

### 3.3 Run coordinator

Responsibilities:

- allocate a safe run ID and contained run directory;
- maintain the generic run state machine;
- order validation, freeze, plan, operation, verification, and finalization;
- preserve reached-step evidence on failure;
- own final Phase status/exit code;
- never replace a domain result with a report.

### 3.4 Candidate capture

Candidate is the immutable core-boundary representation of the requested operation. Core records:

- exact received bytes/text according to declared input mode;
- contract identity/digest;
- invocation identity declarations;
- candidate digest;
- receive timestamp and tool version.

Candidate capture does not mean approval or semantic correctness.

### 3.5 Input freezer

Supports contract-declared strategies:

- `copy_and_hash`: content-addressed copy into run input;
- `manifest_and_hash`: hash all declared files with a stable manifest;
- `lock_snapshot_revalidate`: capture state token/head under lock and require equality immediately before operation;
- `value_snapshot`: canonicalize and hash a small structured value.

A manifest without copied bytes is not called a frozen copy. Mutable upstream may not be read after a `copy_and_hash` freeze. Other strategies must expose their weaker guarantee.

### 3.6 Validator runner

Validator phases:

1. contract/schema integrity;
2. candidate structural validation;
3. input binding and provenance validation;
4. domain policy validation;
5. precondition/write-plan validation;
6. post-operation verification;
7. evidence/result schema validation.

Validators are selected by stable registered IDs and versions. Pure validators receive read-only snapshots and return structured checks; they do not mutate targets.

### 3.7 Planner and capability/effect broker

The contract produces or selects a bounded effect plan. The broker validates each effect against:

- declared operation intent;
- allowed effect primitives;
- canonical target root(s);
- path/identifier rules;
- expected pre-state/hash/concurrency token;
- overwrite/update policy;
- privacy/secret restrictions.

Preferred invariant: domain extensions may propose effects, but only the broker performs filesystem mutation. If a future external executor can write directly, its stronger trust boundary must be explicit and cannot inherit broker confinement claims.

### 3.8 Registered effect mechanisms

Core-level reusable mechanisms are narrow and deterministic:

- append bytes/record under lock with expected-head check;
- copy content-addressed bytes to a contained destination;
- create a new file exclusively;
- compare-and-swap update with explicit before image/precondition;
- append correction/compensation record as an append primitive.

`append`, `copy`, `create`, `update`, and `correction` are operation intents. The actual low-level effects remain explicit. `update` is not enabled until before-image, concurrency, partial-failure, and recovery semantics pass tests.

### 3.9 Post-operation verifier

Verifies the contract-declared result without silently repairing it:

- expected effect set reached;
- destination hashes/bytes/state tokens;
- append head and chain/state transition;
- result schema/invariants;
- forbidden/missing effects to the extent observable;
- evidence completeness.

Declared-scope evidence is not an OS audit. Strong confinement requires broker-only mutation plus platform/path tests or a sandbox.

### 3.10 Result/evidence finalizer

Separates two authorities:

- **canonical result:** domain state named by the contract, e.g. a task stream or admitted asset destination;
- **canonical evidence:** the Phase run bundle owned by Phase Core.

The finalizer emits one canonical machine-readable receipt containing the result reference, check summaries/references, timestamps, hashes, status, blockers, and exit code. Receipt and referenced required attachments are schema-validated before success.

## 4. Minimal run evidence surface

Phase Core must not reproduce the Phase2/3 pattern of many mandatory check, report, Markdown, timestamp and wrapper artifacts for every small operation. The minimum conceptual surface is:

```text
.phase/runs/<run_id>/
  intent.json          # immutable request/contract/input bindings, synced before mutation
  receipt.json         # one canonical machine-readable outcome when finalization is reached
  blobs/<sha256>       # only bytes actually frozen by copy, when required
  attachments/         # optional large validator/effect details referenced by digest
```

`intent.json` is the durable recovery marker, not a success report. `receipt.json` contains structured validation summaries, effect receipts, result reference, terminal status and blockers. A human-readable report is a rebuildable projection, never another canonical artifact. Single-effect operations need no mandatory `checks/`, `logs/`, `plan/` or wrapper run tree. Multi-effect or diagnostic detail belongs in content-addressed attachments only when the contract requires it.

If a crash leaves intent without receipt, recovery classifies the operation by inspecting the declared target and mechanism-specific idempotency rules; absence of a receipt is never success. Exact file/container format remains a Stage 1 ADR decision. The invariant is one core evidence owner and the smallest evidence needed to recover and substantiate the claimed outcome.

## 5. Generic run state machine

```text
received
→ contract_validated
→ candidate_validated
→ input_frozen
→ plan_validated
→ operation_started
→ operation_completed
→ post_verified
→ finalized
```

Terminal classifications:

- `rejected`: no controlled target effect was attempted;
- `failed_no_effect`: operation attempted but verified no target effect;
- `failed_partial`: a known subset of effects occurred;
- `committed_unverified`: result appears committed but post-verification/evidence finalization failed;
- `indeterminate`: core cannot establish target state;
- `succeeded_verified`: all contract success predicates and evidence checks passed;
- `aborted`: explicit stop before mutation.

Core must not convert `failed_partial`, `committed_unverified`, or `indeterminate` into `rejected` or success.

## 6. Canonical ownership

| Surface | Owner | Contract role |
|---|---|---|
| Phase run metadata/evidence | Phase Core | Declares required domain evidence additions |
| Candidate snapshot | Phase Core | Defines shape/input mode/privacy policy |
| Frozen input | Phase Core freezer | Defines bindings and freeze strategy |
| Effect plan | Core broker | Defines permitted intent/primitives/scope |
| Domain canonical result | Contract-designated result owner, mutation mediated by core | Defines locator, authority, schema and verifier |
| Adapter output | Adapter only | References result/evidence; never competes with them |

## 7. Universality hypothesis and required proof

The table below is an architectural fit analysis, not evidence that universality has already been implemented or demonstrated. The hypothesis remains provisional until synthetic append/copy conformance and differential source/knowledge admission tests pass without adding domain branches to core.

| Capability | `task_journal.v1` | `source_admission.v1` | `knowledge_admission.v1` |
|---|---|---|---|
| Candidate | task command/event request | reviewed source package | reviewed knowledge package + profile refs |
| Freeze | request + task head token/snapshot | package/payload copy+hash | package/payload/profile/taxonomy bindings |
| Main intent | append/correction | copy/create | copy/create |
| Policy validators | task state/schema/privacy | provenance/review/placement | provenance/review/profile/taxonomy/placement |
| Result | task JSONL stream | source destination artifact(s) | knowledge destination artifact(s) |
| Verification | chain/head/state/result | destination hash/placement | destination hash/placement/profile binding |
| Evidence | Phase run + task result ref | Phase run + admission result ref | Phase run + admission result ref |

The proposed mapping requires no task or KB vocabulary in core. This must be verified against executable contract schemas, profile/taxonomy fixtures and legacy parity tests; Iteration 0.5 alone does not prove it.

## 8. Anti-control-plane boundary

Phase Core is not:

- an arbitrary DAG/workflow engine;
- an agent planner or semantic reviewer;
- a knowledge taxonomy/profile registry;
- an approval authority or identity provider;
- a deployment/orchestration platform;
- a scheduler, daemon, database, remote executor, or secrets manager;
- a replacement for OS permissions, WORM, signing, or trusted time;
- a wrapper hierarchy.

A feature enters provisional core only when needed for the first vertical slice or when at least two materially different contracts need the same deterministic mechanism and its guarantee can be tested independently. A provisional abstraction becomes a stable public core API only after two independent mutation-bearing implementations use it with the same semantics and conformance tests — two schemas or conceptual mappings are not enough. Otherwise it remains in a contract, adapter, or domain extension.

This is a hard architecture gate. Any proposal to add registry administration, approvals, routing, scheduling, orchestration, taxonomy/profile interpretation or arbitrary extension execution to core requires an explicit ADR showing why it cannot remain outside core, an independent complexity review, and conformance tests across at least two different contracts. Without that evidence the proposal is rejected.

## 9. Implementation-boundary proof obligations

Future tests must map directly to:

- resolver: wrong digest/version/untrusted mechanism rejection;
- freezer: mutable-upstream and TOCTOU fixtures;
- broker: path traversal, symlink/reparse, reserved names, out-of-scope plans;
- append: concurrent writers, short/torn writes, stale head, Windows/Linux sync behavior;
- copy/create/update: preflight-all-effects, partial failure, same-hash idempotency, conflicting destination;
- verifier: tampering, missing evidence, result/evidence mismatch;
- finalizer: aggregate schema validation and truthful partial/indeterminate state;
- adapters: no direct canonical writes.
