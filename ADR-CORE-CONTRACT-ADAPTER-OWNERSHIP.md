# ADR: Core, Contract, and Adapter Ownership

- **Status:** Accepted for Stage 1 specification
- **Decision ID:** ADR-CORE-CONTRACT-ADAPTER-OWNERSHIP
- **Scope:** Phase Tool v1 architecture
- **Implementation status:** Specification only; no runtime exists

## Context

Phase Tool executes an exact versioned operation contract through one controlled pipeline:

```text
adapter
→ Phase Tool interface
→ Phase Core + exact contract
→ canonical domain result
→ canonical Phase receipt
```

Existing Phase2/3/4 and admission wrappers mix invocation, domain policy, mutation, and evidence. The new architecture needs one owner for each responsibility and must prevent task, admission, agent, and orchestration concepts from entering Core.

## Decision

### 1. Phase Tool interface

Owns only the stable invocation/query boundary:

- select an exact contract ID and version;
- accept candidate bytes/value and named bindings;
- accept installation-approved target-root bindings;
- accept an optional idempotency key;
- expose `validate`, `plan`, `execute`, read-only `verify`, and `inspect` modes;
- return a canonical receipt reference and exit code;
- reject unsupported modes/contracts before mutation.

The read-only `verify` mode MUST NOT create a domain result. A domain-recorded verification is an ordinary candidate sent through `execute`.

The interface does not perform domain routing, approval, planning by an agent, or direct target writes.

### 2. Phase Core

Owns universal deterministic mechanisms:

- exact contract resolution and compatibility checks;
- candidate capture at the Core boundary;
- input binding and declared freeze strategy execution;
- ordered validator invocation and result aggregation;
- contained run identity and minimal evidence lifecycle;
- effect-plan validation;
- effect broker and bundled mutation mechanisms;
- post-operation verification orchestration;
- generic terminal-status classification;
- idempotency protocol coordination;
- canonical Phase intent/receipt production;
- stable non-zero failure exit behavior.

Core MUST NOT interpret domain payload fields. It MUST NOT contain the forbidden vocabulary enumerated in ADR-ANTI-CONTROL-PLANE-BOUNDARY.

### 3. Operation contract

Owns operation-specific declarative policy:

- candidate schema and input mode;
- named input bindings and freeze strategy selection;
- registered validator references and configuration;
- write-root bindings and path policy;
- operation intent and allowed effect types;
- exact bundled mechanism binding;
- canonical domain result owner, locator rule, and schema;
- post-operation predicates;
- domain evidence requirements;
- success/no-effect/partial/indeterminate interpretation;
- idempotency scope and canonical request-digest profile;
- correction, compensation, or rollback policy;
- privacy, retention, and redaction policy references.

A contract is data. It MUST NOT contain executable commands, import paths, executable filesystem paths, or arbitrary prompts treated as trusted validation.

### 4. Registered validators

A validator owns one named check. It:

- consumes immutable candidate/frozen input or post-operation observations;
- has exact ID, version, package digest, phase, and capability declaration;
- returns one `validator-result` conforming to the Core schema;
- performs no target mutation;
- MUST NOT invoke the effect broker;
- MUST NOT select another contract or validator dynamically;
- MUST declare when a claim is `unknown` rather than infer success.

Bundled Core invariant validators are part of the Core trusted computing base. Optional third-party validators require the trust and isolation boundary defined by ADR-CONTRACT-TRUST-REGISTRY.

### 5. Effect broker

The effect broker is the sole v1 mutation boundary. It:

- accepts a schema-valid complete effect plan;
- resolves installation-approved root bindings;
- checks every target against write-scope/path policy;
- checks mechanism ID/version/digest and v1 support;
- invokes only bundled mutation mechanisms;
- emits effect receipts and observable before/after state;
- never interprets domain semantics;
- never expands the plan after mutation begins.

Validators, contracts, adapters, and skills MUST NOT write canonical targets directly.

### 6. Adapters and skills

Adapters/skills may:

- collect declared agent/session/operator context;
- choose a contract through domain-facing UX/routing outside Core;
- build a candidate and bindings;
- call the Phase Tool interface;
- display receipt/result references;
- propagate non-zero status.

They MUST NOT:

- duplicate contract validators;
- write canonical results or Phase evidence;
- convert Phase failure to success;
- create competing canonical reports;
- claim authenticated identity from declared attribution;
- bypass exact version resolution.

### 7. Canonical domain result

The contract designates the canonical result owner and locator. The result can pre-exist and be appended to, or be created by the operation. Core owns neither domain meaning nor semantic correctness.

A canonical result reference MUST state:

- owner ID;
- locator under an approved root binding;
- contract ID/version;
- result state token or digest;
- observed time;
- authority rule.

A wrapper report never supersedes the canonical domain result.

### 8. Canonical Phase evidence

Phase Core is the only canonical execution-evidence owner. The minimal surface is:

```text
.phase/runs/<run_id>/
  intent.json
  receipt.json
  blobs/
  attachments/
```

- `intent.json` is an immutable durable recovery marker written before mutation.
- `receipt.json` is the one canonical machine-readable terminal outcome when finalization is reached.
- `blobs/` contains only bytes actually frozen by copy.
- `attachments/` contains optional content-addressed details referenced from intent/receipt.
- human-readable reports are rebuildable projections and non-canonical.

Intent without receipt is not success; it triggers recovery inspection.

## Allowed dependency direction

```text
adapter/skill → Phase Tool interface → Phase Core
operation contract → schema/registry identifiers only
Phase Core → trusted registry snapshot
Phase Core → registered read-only validator boundary
Phase Core → effect broker → bundled mechanism
receipt → canonical result reference
```

## Forbidden dependencies

| From | Forbidden dependency |
|---|---|
| Phase Core | adapter, skill, agent runtime, domain payload vocabulary |
| Phase Core | routing, approval, scheduling, orchestration, taxonomy/profile interpretation |
| Contract | shell command, executable/import path, mutable registry alias, unbounded target path |
| Validator | effect broker, target mutation, contract selection, registry administration |
| Effect mechanism | domain schema, adapter context, policy decision, dynamic plan expansion |
| Adapter/skill | canonical target write, Phase evidence write, validator implementation |
| Domain result | dependence on wrapper report for authority |
| Receipt | claim of semantic correctness not established by declared validators |

## Failure ownership

- Contract/schema/registry rejection before mutation → Core terminal status `rejected`.
- Explicit pre-mutation cancellation → `aborted`.
- Attempt with verified no effect → `failed_no_effect`.
- Known subset of effects → `failed_partial`.
- Observed commit but incomplete verification/evidence → `committed_unverified`.
- Target state cannot be established → `indeterminate`.
- All success predicates and evidence validation pass → `succeeded_verified`.

Adapters cannot override this classification.

## Future enforcement and tests

| Boundary | Required future enforcement | Required tests |
|---|---|---|
| Core/domain separation | dependency/locabulary scan of Core | forbidden vocabulary and import tests |
| Validator read-only | worker capability boundary or bundled pure API | mutation attempt denied; unknown reported |
| Broker-only mutation | no writable target handles outside broker | adapter/validator direct-write negative tests |
| Exact contract | ID/version/package digest registry lookup | wrong version/digest/ambiguous entry |
| One evidence owner | schema and output-surface checks | no competing report authority |
| Result authority | contract-bound result reference | wrapper/result disagreement |
| Failure propagation | Core-owned terminal classifier | partial, committed-unverified, indeterminate fixtures |

## Consequences

- Domain contracts can evolve without Core branches.
- Core remains small but carries the mutation/evidence security boundary.
- Adapters remain replaceable.
- Extension flexibility is deliberately restricted in v1.
- Universality is provisional until two independent mutation-bearing contracts use the same Core pipeline and mechanisms with matching conformance tests.
