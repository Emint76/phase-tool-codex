# Stage 1 Independent Read-Only Review

- **Reviewer set:** one independent Codex CLI process plus three parallel read-only subagents (schema/cross-document invariants; status/freeze/effect/platform stress; conformance catalog/universality)
- **Codex mode:** `--sandbox read-only --ephemeral`
- **Subagent batch:** `deleg_e68a0910`; all three reported no file modifications
- **Reviewed boundary:** current uncommitted Stage 1 ADR/spec/schema/contract/fixture artifacts
- **Baseline:** Iteration 0.5 commit `329d22a499c47a7f6c265ea478e7e15e72535c0c`
- **Mutation/runtime:** prohibited; none performed
- **Independent validator limitation:** Codex sandbox policy rejected its attempted schema-validation commands, so its schema review was manual/read-only. The primary session independently ran Draft 2020-12 validation and reports those real results separately.

## Severity summary after disposition

- Critical: **0**
- High resolved in Stage 1 artifacts: **5 categories**
- Medium resolved/strengthened: **2**
- High remaining implementation blockers to Stage 2: **5 categories**

## Independent findings and disposition

### H1 — Effect-plan conditional gaps

Finding: append plans allowed an irrelevant `expected_digest`; create/copy `concurrency_token` was not constrained.

Disposition:

- fixed append/correction schema to require null `expected_digest`;
- create/copy token remains nullable by design because it may bind observed parent/destination identity at publication boundary;
- exact meaning and equality are mechanism semantic tests, not proof from JSON shape;
- Stage 2 remains blocked on executable plan semantic tests.

### H2 — Relative locator regex too weak

Finding: prior regex allowed backslash traversal/rooting, colon/ADS-like values, trailing dots/spaces, and Windows reserved names.

Disposition:

- replaced in contract/effect-plan/result-reference schemas with a strict portable ASCII component subset;
- backslash, colon, absolute/root forms, empty components, leading/trailing dot-like forms are structurally excluded;
- Windows reserved aliases (`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`, including extensions) are structurally excluded;
- physical symlink/reparse/mount/parent replacement containment still requires future handle/descriptor implementation and race tests;
- regex is explicitly not the security boundary.

### H3 — Stage 2 executable specification gaps

Finding: canonical serialization, registry/package digest construction, platform no-replace/path/locking designs, crash/evidence harness, and aggregate semantic tests remain unresolved.

Disposition: confirmed; retained as High Stage 2 blockers rather than overclaimed guarantees.

### M1 — Receipt schema aggregate/status gaps

Finding: shape did not require blockers/effect evidence for several non-success statuses and left aggregate consistency to prose.

Disposition:

- strengthened schema conditionals for rejected/aborted/no-effect/partial/committed-unverified/indeterminate/success;
- rejected/aborted prohibit effect receipts and require blockers;
- no-effect/partial/committed-unverified require effect receipts and blockers;
- committed-unverified requires a canonical result reference;
- executed success requires validator/effect results; verified reuse requires exact prior receipt digest and no new effect receipt; both require finalized evidence, no blockers, no recovery, and exit 0;
- effect-set equality, timestamp ordering, and aggregate status derivation remain semantic conformance tests and Stage 2 blockers.

### M2 — Deferred CAS represented in v1 schema

Finding: `update` and `compare_and_swap_replace` appeared in the v1 contract schema despite CAS being deferred.

Disposition: removed from v1 contract schema. CAS/update remains prose-only deferred design and requires a future approved schema revision/ADR/tests.

### H4 — Terminal classification ambiguity

Fan-out finding: the prior matrix did not fully distinguish `not_executed`, newly `executed`, and verified reuse, and used weak “appears committed” wording.

Disposition:

- added `execution_disposition` to receipt schema;
- added deterministic classification precedence;
- `committed_unverified` now requires positively observed complete commit/result state;
- `failed_no_effect` requires an actual mechanism attempt plus positive no-effect observation;
- added full golden receipts for all seven statuses and a separate verified-reuse success.

### H5 — Multi-effect crash recovery ambiguity

Fan-out finding: one durable intent plus one final receipt cannot establish the reached subset after a crash between effects.

Disposition:

- added `effect-journal-entry.schema.json`;
- specified durable `attempt_started` before each effect and `observation_recorded` before proceeding;
- marker chain is immutable recovery evidence under `attachments/effect-journal/`;
- runtime must reject multi-effect plans until this protocol is implemented and crash-tested.

### H6 — Implicit operational writes and control-plane drift

Fan-out finding: temp files, locks, directory creation, cleanup and evidence writes were not fully separated from target effects; generic compensation/snapshot/rollback references broadened Core toward orchestration.

Disposition:

- separated target, evidence, blob, staging/lock and forbidden capabilities;
- required broker accounting for operational writes without calling them target effects;
- removed generic compensation, snapshot restore and rollback-contract references from executable v1 schema;
- reduced physical primitives to `exclusive_create`, `append_record`, and `copy_blob`;
- correction remains semantic intent over an already trusted primitive.

## Six required answers

### 1. Does Core schema contain domain vocabulary?

**No, under the explicit token gate.** The eight Core schemas contain none of:

```text
task source knowledge KB taxonomy profile Hermes OpenClaw Codex
Phase2 Phase3 Phase4 approval routing orchestration
```

Domain terms occur only in non-executable domain contract instances/prose. This is lexical evidence, not proof that future implementation will remain neutral.

### 2. Do append and copy fixtures require different Core pipelines?

**No.** They share:

```text
exact resolve
→ contract/candidate/input validation
→ freeze/value binding
→ durable intent
→ static effect plan
→ trusted effect broker
→ mechanism-specific bounded effect
→ post-verification
→ canonical receipt/evidence
```

They select different trusted mechanisms and validators. A future separate top-level lifecycle/status/evidence implementation would falsify this answer.

### 3. Do task, source, and knowledge fit one meta-model?

**Schema/design fit is plausible; execution proof does not exist.**

- both source and knowledge design probes validate against the unchanged meta-schema;
- provenance/review/placement/profile/taxonomy stay in contract instances and validator bindings;
- append fixture plus the existing task-journal proposal demonstrates a structural mapping for task journaling;
- no domain contract is executable in Stage 1;
- no admission parity is claimed;
- universality still requires two mutation-bearing implementations and later differential domain validation.

### 4. Has Core become a workflow/control-plane engine?

**No in current Stage 1 artifacts.** Core has no routing, approval, scheduling, orchestration, registry administration, remote execution, plugin execution, or agent planning. Effect plans are finite/static and cannot add work dynamically.

Risk remains because registry and declarative lifecycle concepts are control-adjacent. `ADR-ANTI-CONTROL-PLANE-BOUNDARY.md` must remain a hard rejection gate.

### 5. Can every guarantee be tied to a mechanism and test?

**Every proposed guarantee has a future owner/boundary/evidence/test row in `GUARANTEE-TRACEABILITY.md`, but none is implemented or proven.**

Where a guarantee still lacks an executable serialization/platform/crash/aggregate test definition, it remains a blocker and cannot be used as a product claim.

### 6. Which High/Critical risks block Stage 2?

Critical: **none identified in the specification after fixes.**

High blockers:

1. **Canonical serialization and digest construction:** no final request/plan/intent/receipt canonical byte profile or complete golden corpus.
2. **Registry/package trust executable model:** snapshot/package digest construction, immutable lookup, trust-root verification, schema logical-ID resolution, and capability denial are not implemented/tested.
3. **Platform effect/path qualification:** Windows/Linux no-replace publication, handle/descriptor containment, lock, short-write, flush, directory durability, WSL, and unsupported filesystem refusal need exact test designs and implementations.
4. **Crash/evidence/aggregate semantics:** no executable kill-point harness, intent/receipt recovery finalizer, effect-set equality checker, or terminal classifier conformance suite.
5. **Universality proof absent:** append and copy are schemas/vectors only; two independent mutation-bearing implementations do not exist, and domain parity/differential tests have not run.

Additional Stage 2 design concern: serialized candidate/config/attachment size limits and privacy enforcement require an explicit resource/security policy before runtime accepts untrusted input.

## Review conclusion

Stage 1 is suitable as a specification baseline, not as implementation evidence. Stage 2 must not begin under the current authorization and remains blocked by the High categories above.
