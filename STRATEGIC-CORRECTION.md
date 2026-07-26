# Strategic Correction — Iteration 0.5

Status: architectural correction; no product code, repository rename, or migration is authorized by this document.

## 1. Baseline and reason for correction

This correction is based on Iteration 0 commit:

```text
9cb1bec117ef4ff6164f84b20a1998398093faca
```

Iteration 0 correctly identified task-journal requirements: original instruction preservation, explicit lifecycle, append-only correction, deterministic verification, hash chaining, visible partial/failure states, local portability, thin agent adapters, and honest ALCOA+-inspired boundaries.

The incorrect product boundary was treating those requirements as the basis for a standalone **agent-task-journal core**. That would create another validation, freeze, controlled-write, verification, and evidence runtime beside Phase.

The strategic correction is:

> Phase is a universal contract-driven tool for controlled information/record operations. A contract determines the operation result and domain semantics. `task_journal.v1` is the first new real contract executed by Phase Core, not a second core.

## 2. What was wrong in the former boundary

### 2.1 Duplicate execution mechanics

The Iteration 0 proposal assigned a task-journal-specific core responsibility for:

- candidate construction;
- schema and state validation;
- input hashing/freeze;
- write-surface containment;
- locking and controlled append;
- post-operation verification;
- canonical evidence;
- idempotency and failure classification.

These are mostly universal controlled-operation mechanics. Reimplementing them under a task-journal product would duplicate Phase and let guarantees drift.

### 2.2 Task semantics were mixed with runtime mechanics

Task lifecycle rules (`task_open`, `task_event`, `task_close`, `task_verify`), corrections, original instruction semantics, and task projections are domain policy. Locking, frozen input, effect mediation, evidence emission, and run status are execution mechanics. The former architecture placed both in one product core.

### 2.3 Existing Phase topology was treated as the reusable shape

Iteration 0 correctly rejected mechanical copying, but still described Phase mainly through Phase2/3/4. Those labels are historical harness topology, not necessary universal stages:

- Phase2 combines audit checks and repo-native scaffold rendering;
- Phase3 combines reusable run ownership with hard-coded target routing and admission implementations;
- Phase4 is a thin operator wrapper;
- Admission Stage 1/2 are separate contract-layer labels.

The future product must preserve useful guarantees without making this topology normative.

### 2.4 Canonical result and canonical evidence were not cleanly separated

A controlled operation can mutate or append to a domain-owned canonical result while Phase owns canonical execution evidence. For task journal:

- the task stream is the canonical domain result;
- the Phase run bundle is canonical execution evidence.

Neither adapter nor wrapper may create competing canonical surfaces.

## 3. Corrected product boundary

```text
Hermes / OpenClaw / Codex adapter
              |
              v
          Phase Tool CLI
              |
              v
          Phase Core
        /      |       \
contract   trusted       evidence/result
bundle     mechanisms    verification
   |
   +-- task_journal.v1
   +-- source_admission.v1
   +-- knowledge_admission.v1
```

### Phase Core owns

- contract loading and compatibility checks;
- immutable candidate capture at the core boundary;
- input freeze/hash and provenance manifest;
- lifecycle of a Phase run;
- execution of trusted validators and registered effect mechanisms;
- enforcement/observation of declared write scope within stated platform boundaries;
- generic operation status and failure classification;
- canonical Phase evidence bundle and final exit status;
- post-operation verification orchestration;
- deterministic inspection/replay of Phase evidence.

### Operation contract owns

- candidate schema and domain vocabulary;
- required inputs and freeze strategy;
- domain validators and policy checks by trusted validator ID;
- operation intent and allowed effect primitives;
- declared write roots/path rules;
- domain canonical result and owner;
- domain-specific verification predicates;
- success/failure semantics;
- idempotency scope/digest/result lookup;
- correction, compensation, or rollback policy;
- domain evidence requirements and privacy policy.

### Adapter/skill owns

- deciding when to invoke Phase;
- translating agent/session context into contract input;
- invoking only the public Phase Tool interface;
- presenting canonical result/evidence references;
- never duplicating contract validators, write logic, or canonical evidence.

### Domain implementation owns

Only semantics that cannot be declarative or expressed through trusted generic primitives. It must be registered and version-bound; a contract must not execute an arbitrary path, shell fragment, import, or prompt as trusted core code.

## 4. What remains valid from Iteration 0

The following become `task_journal.v1` requirements rather than Phase Core semantics:

- exact core-received original instruction boundary;
- task-local event/state model;
- task event hash chain;
- post-close recorded verification;
- corrections/amendments without rewriting task history;
- task outcomes `completed`, `partial`, `failed`, `cancelled`;
- artifact observations and unfinished items;
- list/show/search/export projections;
- ALCOA+-inspired mapping and its non-guarantees.

The following move to Phase Core or generic mechanisms:

- candidate capture;
- schema dispatch;
- freeze/hash/provenance;
- run directory and evidence ownership;
- write-scope policy enforcement hooks;
- controlled effect execution;
- generic idempotency coordination;
- failure/indeterminate classification;
- post-operation verification orchestration.

## 5. Non-goals of the correction

- Do not rename the repository now.
- Do not write or move product code now.
- Do not modify Iteration 0 documents.
- Do not claim existing Phase2/3/4 is already a universal core.
- Do not turn Phase Core into arbitrary workflow orchestration, deployment, identity, approval, taxonomy, KB, or agent runtime.
- Do not weaken source/knowledge admission guarantees to fit task journaling.
- Do not claim atomicity, rollback, write confinement, or durability without an implementation boundary and executable tests.

## 6. Decision tests

The corrected boundary is accepted only if all are true:

1. `task_journal.v1` can be removed without changing Phase Core APIs.
2. A copy-based `source_admission.v1` can use the same run/freeze/validate/evidence lifecycle.
3. `knowledge_admission.v1` can add profile/taxonomy policy without adding KB concepts to core.
4. Core does not interpret task status, knowledge type, source family, or Hermes session semantics.
5. Every mutation is mediated by a registered mechanism or explicitly classified as outside the core trust boundary.
6. Core can stay small enough to test on Windows and Linux without Phase2/3/4 wrapper topology.
