# Task Journal Contract Proposal — `task_journal.v1`

Status: first proposed real operation contract for Phase Tool; no schema or implementation is created in Iteration 0.5.

## 1. Position in the product

`task_journal.v1` is not a standalone core. It is a contract bundle executed by Phase Core.

```text
Hermes/OpenClaw/Codex adapter
→ Phase Tool + task_journal.v1
→ Phase Core controlled append/correction
→ canonical task stream
→ canonical Phase evidence
```

The contract preserves Iteration 0 requirements while moving generic execution mechanics into Phase Core.

## 2. Contract scope

The contract journals only user-task lifecycle records:

```text
task_open → task_event* → task_close → task_verify
```

It does not journal all system processes, network calls, hidden reasoning, desktop activity, or every tool invocation.

Supported candidate actions:

- `open`;
- `event`;
- `close`;
- `verify_record`;
- `correction` / `amendment`.

Read-only verification, show/list/search/export are Phase Tool/application query modes over the same contract/result format; only `verify_record` mutates the task stream.

The Phase Tool read-only `verify` mode never writes a domain result. `verify_record` is submitted as an ordinary `task_journal.v1` candidate through `execute`, passes the same preconditions/effect broker/post-verification pipeline as every other append, and has no privileged core path.

## 3. Candidate

The candidate envelope is core-owned. The `task_journal.v1` payload supplies:

- action;
- task ID or request to allocate one;
- original instruction for `open`;
- optional normalized goal as a separate field;
- actor/agent/executor/session/source declarations;
- event kind and event payload;
- outcome/errors/unfinished items for `close`;
- artifact observations;
- correction target/reason/replacement facts;
- optional operation/idempotency ID.

### Original instruction boundary

The contract requires:

- binary stdin/file capture before text decoding when those modes are used;
- explicit strict UTF-8/BOM policy;
- separately named raw-input hash and deterministic decoded-text hash where applicable;
- no `.strip()`, newline normalization, or semantic rewrite;
- API string guarantee limited to received Unicode code points;
- `normalized_goal` never replaces `original_instruction`.

This is task-journal-specific policy, not Phase Core semantics for every contract.

## 4. Inputs and freeze strategy

| Input | Strategy | Reason |
|---|---|---|
| Candidate request | `value_snapshot` / binary candidate capture | Preserve exact core-boundary request |
| Existing task stream | `lock_snapshot_revalidate` | Capture head hash/sequence/length and re-read under per-task lock immediately before append |
| Artifact files | point-in-time `manifest_and_hash` by default | Record observation without pretending to own an enduring copy |
| Optional managed artifact snapshot | `copy_and_hash` only when explicitly requested/policy-approved | Enables later snapshot verification but expands privacy/storage scope |

For `open`, target absence is the precondition. For subsequent actions, current stream head/state is the concurrency token.

## 5. Validators owned by the contract

### Structural

- task candidate schema;
- event envelope/payload schema;
- portable task ID profile;
- timestamp/encoding/artifact-entry formats.

### State/policy

- `task_open` exactly once at sequence 1;
- normal `task_event` only while execution state is open;
- `task_close` exactly once from open;
- full journaled lifecycle includes post-close `task_verify`;
- correction/amendment may be post-close but does not erase raw lifecycle;
- no reopen in v1 unless a later contract version adds it;
- partial/failed/cancelled/errors/unfinished facts cannot be hidden by projection;
- privacy/security policy passes before the first append.

### Pre-operation

- task path is inside declared journal root;
- ID avoids Windows reserved names, trailing spaces/dots, separators, case collisions and traversal;
- stream is structurally valid through the expected head;
- idempotency key/digest has no conflict;
- event canonical bytes/hash/sequence derive deterministically;
- artifact observation status is explicit.

### Post-operation

- exactly one valid new line/record appears after the expected head;
- sequence and previous hash match;
- new event hash verifies;
- replayed task state equals expected transition;
- stream has no invalid partial tail;
- Phase effect receipt and task head reference agree.

## 6. Operation and write scope

Main intents:

- `create` for `open`: exclusive creation writes the already serialized first `task_open` record as one effect;
- `append` for event/close/verify records after open;
- `correction` as semantic intent implemented by append of a new correction/amendment record;

Allowed canonical write surface:

```text
<journal-root>/tasks/<task-id>.jsonl
```

Operational lock/evidence paths are core-owned and separate. The contract forbids adapters from writing task streams directly.

Durability/atomicity claims are bounded:

- lock + expected-head revalidation;
- pre-serialized binary record;
- short-write handling;
- file flush/sync and platform-specific directory semantics where supported;
- immediate read-back;
- a torn/truncated tail is `corrupt/unverifiable`, never a valid event;
- no WORM or administrator-resistance claim.

## 7. Canonical result and evidence

### Canonical result

The task JSONL stream is the domain canonical result. Its authority is task-local order and hash chain.

Result reference includes:

- journal-root identity or portable binding;
- task ID;
- sequence;
- head hash;
- byte length;
- execution and verification states.

### Canonical evidence

Phase Core owns the Phase run bundle for each attempted operation. It records:

- contract/candidate/input digests;
- expected and resulting task head;
- validation checks;
- effect receipt;
- post-verification;
- terminal Phase status;
- result reference and exit code.

Phase evidence does not replace the task stream, and the stream does not replace Phase execution evidence.

## 8. Hash and canonicalization policy

The contract, not core globally, fixes the event hash profile:

- SHA-256;
- domain-separated preimage;
- versioned deterministic JSON bytes;
- no floats/non-integer JSON numbers in v1;
- `event_hash` excluded from its own preimage;
- previous event hash included;
- task/journal identity bound into preimage;
- Unicode/newline rules covered by golden vectors.

Phase Core supplies canonical-codec and hash mechanism interfaces. Other contracts may use byte-for-byte artifact hashes without task event chaining.

## 9. Idempotency

`task_journal.v1` requires stable operation ID for agent adapters.

- scope: contract version + journal root identity + task ID/action;
- request digest: canonical candidate projection excluding receive-time metadata;
- same ID + same digest + verified event → return existing result/evidence reference;
- same ID + different digest → conflict;
- prior partial/indeterminate operation → inspect/recover; no automatic replay.

The task stream is the canonical idempotency lookup for successful events; Phase evidence assists recovery.

## 10. Verification modes

### Read-only integrity verification

- verifies decode/schema/hash/sequence/state/corrections;
- optionally checks current external artifacts as a separate scope;
- does not append or advance lifecycle.

### Recorded task verification

- first verifies the predecessor head;
- appends `task_verify` through the controlled operation;
- records the verified predecessor head/scope/tool identity/result;
- structurally verifies the new record;
- never appends a success record to a corrupt/untrusted chain.

### Artifact scopes

- historical artifact hash is a point-in-time observation;
- current path comparison reports changed/missing/unavailable separately;
- managed snapshot verification is available only when an explicit content-addressed copy exists.

## 11. Correction/rollback policy

The contract uses `append_correction`:

- prior bytes are never rewritten by conforming tooling;
- correction references target event ID/hash;
- reason and corrected/additional facts are required;
- raw view remains available;
- projected view shows original terminal status, amendment and superseded chain;
- correction cannot silently convert partial/failure into an unqualified success.

Rollback of journal history is forbidden. Filesystem restore/deletion is not a task-journal recovery mechanism.

## 12. Mapping from Iteration 0 architecture

| Iteration 0 concept/module | New ownership |
|---|---|
| CLI command parsing | Phase Tool + thin adapter |
| Application service orchestration | Phase Core run coordinator |
| Task event types/state replay | `task_journal.v1` validators/domain package |
| Schema registry | Core contract resolver + contract schemas |
| Canonical JSON/event hash profile | Registered generic codec + task contract configuration |
| Journal store/lock/append | Registered append mechanism in Phase Core |
| Artifact hasher | Reusable core mechanism; scope chosen by contract |
| Task verifier | Contract validators executed by core verifier runner |
| Show/list/search/export | Task contract projections/query package |
| Hermes/OpenClaw/Codex instructions | Adapters/skills only |
| Privacy/ALCOA+ mapping | Task contract policy/documentation |

## 13. Thin adapters

### Hermes adapter

- captures exact user instruction/session attribution declarations;
- selects `task_journal.v1` action;
- invokes Phase Tool;
- returns result/evidence references;
- does not open JSONL directly.

### OpenClaw adapter

Same responsibilities using OpenClaw task/session context. It does not reuse knowledge-admission routing for task semantics.

### Codex adapter

Provides explicit task/action metadata from coding-agent context and invokes Phase Tool. It does not derive correctness from a Codex self-report.

Adapter conformance tests prove public-interface invocation and absence of direct canonical writes in adapter code paths. Out-of-band local writes remain possible for a process/admin with filesystem rights.

## 14. Cross-contract proof

The proposal is acceptable only if Phase Core remains unchanged when:

- task state validator is replaced by source review/placement validators;
- append mechanism is replaced by copy/create mechanism;
- task stream result locator is replaced by admitted source/knowledge destinations;
- task hash-chain verification is replaced by destination hash/lineage/profile verification.

If implementation adds `if task_event`, `task_status`, `knowledge_type`, or `source_family` to core, the boundary has failed.
