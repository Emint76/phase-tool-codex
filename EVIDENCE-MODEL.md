# Evidence Model

Status: Stage 1 normative specification; no evidence writer exists.

## 1. Minimal canonical surface

```text
.phase/runs/<run_id>/
  intent.json
  receipt.json
  blobs/
  attachments/
```

No Phase3-style report tree is required. Human reports, summaries, dashboards, and logs are rebuildable projections and are not canonical outcomes.

## 2. Ownership

- Domain canonical owner owns the canonical domain result.
- Phase Core owns `intent.json` and `receipt.json` semantics.
- Effect broker emits effect receipts to the finalizer.
- Validators emit validator results.
- Evidence finalizer writes required attachments and the canonical receipt.
- Adapters may render evidence but must not redefine status or hashes.

## 3. `intent.json`

Intent is a durable pre-mutation recovery marker. It binds:

- run/Core version;
- immutable registry snapshot digest;
- exact resolved contract ID/version/package digest;
- candidate digest/representation;
- frozen input digests/manifests/blobs/revalidation tokens;
- write-scope digest;
- operation intent and exact mechanism binding;
- idempotency scope/key/request digest;
- static effect-plan digest;
- creation time and `intent_recorded` state.

Ordering:

1. resolve/validate/freeze/plan;
2. serialize and validate intent;
3. create intent exclusively;
4. flush according to qualified evidence policy;
5. only then authorize mutation.

Intent proves planned binding and recovery context. It does not prove an effect was attempted or succeeded.

If required intent durability cannot be established, mutation is rejected/aborted before mechanism invocation.

## 4. `receipt.json`

Receipt is the sole canonical machine-readable Phase outcome. It binds:

- exact run/Core/contract;
- one terminal status;
- mutation-attempt fact and result state;
- canonical result reference when known;
- complete validator/effect receipt sets or explicit not-reached state;
- evidence finalization status and attachment digests;
- retry disposition, recovery requirement, blockers, exit code;
- start/finish observations.

A receipt must validate structurally and semantically before publication. `succeeded_verified` additionally requires all success predicates and required attachments.

Receipt is written at most once as the canonical final outcome. Recovery after an absent receipt may create it from intent/observations. Corrections to already finalized evidence require a separately linked correction/evidence record; silent overwrite is prohibited.

## 5. `blobs/`

Content-addressed immutable evidence/input bytes:

```text
blobs/<sha256-hex>
```

Rules:

- name is exact SHA-256 of exact file bytes;
- publish no-replace;
- existing same digest is read-back verified before reuse;
- operation consumes frozen blob, not mutable upstream;
- no secrets unless contract privacy policy explicitly allows and protects them; default rejects/redacts;
- blob presence alone does not establish provenance, trust, or operation success.

A compromised privileged local actor can alter/delete storage. Content addressing is tamper-evident on read, not tamper-proof.

## 6. `attachments/`

Attachments contain bounded supporting evidence that does not belong inline, such as:

- complete effect-plan/effect-receipt set;
- validator detail;
- manifests;
- registry snapshot reference/copy where policy allows;
- platform/environment qualification;
- recovery inspection observations.

Every required attachment is addressed by digest from receipt. Unreferenced logs are noncanonical diagnostics. Attachment failure after target commit leads to `committed_unverified` or `indeterminate`, not success.

### 6.1 Durable per-effect recovery journal

A multi-effect plan (`maximum_effects > 1`) is executable only if the future Core can durably publish an append-only marker stream under:

```text
attachments/effect-journal/
  <sequence>-<entry-digest>.json
```

Each marker validates against `schemas/effect-journal-entry.schema.json` and is content-addressed. Required ordering for every effect is:

1. durable `attempt_started` marker, bound to run ID, plan digest, ordinal and effect ID;
2. mechanism attempt;
3. target observation;
4. durable `observation_recorded` marker referring to the observation digest.

The first marker must be durable before the effect can be handed to the mechanism. The second is written after observation and before the next effect. Missing post-attempt observation yields `indeterminate`; it never implies no effect. Sequence and `previous_entry_digest` form a tamper-evident recovery chain, not tamper-proof storage.

`receipt.json` remains the only canonical terminal outcome. Journal entries are recovery evidence and may not be rewritten. If this journal protocol is not implemented and crash-tested, runtime must reject plans with more than one effect.

## 7. Effect and validator evidence

Effect receipt records:

- static effect identity/kind;
- attempted/not-attempted;
- before/after state certainty;
- bytes written;
- verification refs;
- error and timing.

Validator result records:

- exact validator binding;
- lifecycle phase;
- pass/fail/unknown/not-reached;
- stable code;
- expected versus actual;
- observation references/blockers;
- timing.

A validator crash/timeout is unknown. Missing results are not pass.

## 8. Finalization ordering and crash states

| Crash/failure point | Required interpretation |
|---|---|
| Before durable intent | No authorized mutation; no run guarantee beyond diagnostics |
| After intent, before mechanism | Recoverable intent; inspect, normally resolve no attempt |
| During effect | Inspect; classify no-effect/partial/indeterminate |
| After effect, before post-verification | Result may be committed; inspect, never blind replay |
| After verified effect, before required attachments | `committed_unverified` unless evidence can be safely finalized |
| During receipt publication | Intent plus target/attachment inspection; receipt absence is not success |
| After valid succeeded receipt | Verified terminal outcome subject to later tamper/deletion limitations |

Receipt finalization must use exclusive/no-replace publication or an equally tested immutable boundary. A temporary file/rename design may not overwrite an existing canonical receipt.

## 9. Canonical serialization and digest limits

Stage 1 uses deterministic formatting for fixtures only. General canonical JSON serialization for request/plan/intent/receipt digests is not yet fixed. Until a versioned serialization ADR and golden corpus exist:

- package/request/plan/receipt digest computation is not implementable;
- examples use deterministic label-derived digests;
- no runtime reproducibility guarantee may be claimed.

This is a High Stage 2 blocker.

## 10. Privacy and security

Evidence must never store credentials, tokens, connection strings, or secrets. Validators emit minimal diagnostics and `[REDACTED]` placeholders. Candidate/attachment policies define retention and redaction before durable write.

Hashing sensitive low-entropy content may still disclose it through guessing. Digest-only evidence is not automatically private.

Local evidence is tamper-evident only when revalidated against digests and bindings. Without independent anchoring/WORM/signature trust:

- full deletion may be invisible;
- rollback to an older valid head may be invisible;
- a privileged actor may recompute a chain;
- timestamps are local observations, not trusted time.

## 11. Evidence completeness invariants

Future semantic conformance must establish:

1. intent contract/mechanism bindings equal receipt bindings;
2. receipt effect IDs equal static plan effect IDs;
3. every blocking validator is present and passed for success;
4. every required attachment digest resolves and matches;
5. canonical result contract/owner/root agrees with contract;
6. status agrees with all effect/validator/evidence states;
7. only succeeded receipt uses exit 0;
8. unknown/partial/committed-unverified requires correct recovery disposition;
9. intent/receipt cannot be replaced by adapter or human projection;
10. no receipt claims an unobserved effect.

## 12. Claim boundary

Allowed after implementation/tests:

- “this receipt binds the observed Phase run to exact contract/effect/result evidence”;
- “required evidence for `succeeded_verified` validated at finalization.”

Not allowed without stronger controls:

- immutable/tamper-proof audit trail;
- proof no other writes occurred;
- trusted timestamp/non-repudiation;
- regulatory compliance;
- proof historical evidence was never deleted or rolled back.
