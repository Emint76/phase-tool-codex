# Phase Contract Model — Iteration 0.5

Status: minimal conceptual model for a versioned operation contract. This is not an implementation schema.

## 1. Contract role

A Phase contract is a declarative, versioned policy bundle that tells Phase Core:

- what candidate and inputs are valid;
- what must be frozen or revalidated;
- which trusted validators/mechanisms may run;
- what effects are allowed and where;
- what result is canonical;
- how success, failure, idempotency, correction, and rollback are interpreted;
- what evidence must exist.

A contract is not executable arbitrary code and is not itself evidence that an operation succeeded.

## 2. Minimal conceptual structure

```yaml
contract:
  id: <domain_operation>.v1
  version: 1.0.0
  digest_algorithm: sha256
  core_compatibility: ">=x,<y"

candidate:
  schema_ref: schemas/candidate.schema.json
  input_mode: structured_json | utf8_bytes | bundle
  privacy_policy_id: <registered-policy-id>

inputs:
  - id: <input-id>
    required: true
    schema_ref: <optional-schema>
    freeze_strategy: copy_and_hash | manifest_and_hash | lock_snapshot_revalidate | value_snapshot
    provenance_required: true

validators:
  - phase: candidate | input | policy | pre_operation | post_operation | evidence
    validator_id: <registered-id>
    version: <exact-version>
    blocking: true
    config: <declarative-data>

write_scope:
  roots:
    - binding: <target-binding>
      path_policy_id: <registered-policy-id>
  forbidden_roots: []
  symlink_policy: reject | bounded
  reparse_policy: reject | bounded

operation:
  intent: append | copy | create | update | correction
  mechanism_id: <registered-mechanism-id>
  allowed_effects: [append_bytes, copy_blob, create_file]
  concurrency_policy: <policy-id>
  atomicity_claim: none | single_effect | declared_boundary

canonical_result:
  owner: <domain-owner-id>
  locator_template: <contract-relative-template>
  result_schema_ref: <schema>
  authority_rule: <declarative-rule>

verification:
  verifier_ids: [<registered-id>]
  required_predicates: []
  external_artifact_scope: historical | current | managed_snapshot

evidence:
  schema_ref: <domain-evidence-schema>
  required_checks: []
  retention_class: <policy-id>
  redaction_policy_id: <policy-id>

outcomes:
  success_predicates: []
  no_effect_failure_predicates: []
  partial_effect_policy: fail_partial
  indeterminate_policy: indeterminate

idempotency:
  key_required: true | false
  scope: <scope-expression>
  request_digest_profile: <profile-id>
  success_lookup: canonical_result | phase_evidence
  same_key_same_digest: return_existing
  same_key_different_digest: conflict

recovery:
  policy: none | append_correction | compensating_operation | snapshot_restore
  rollback_contract_ref: <optional-separate-contract>
  automatic: false
```

Field names are provisional. Iteration 1 must produce a real schema only after adversarial examples validate this split.

## 3. Core-owned invariants versus contract-owned policy

| Concern | Core fixes | Contract supplies |
|---|---|---|
| Identity | Exact contract ID/version/digest binding | Domain contract name/version |
| Candidate capture | Immutable core-boundary snapshot + digest | Candidate schema, input mode, privacy rules |
| Freeze | Supported strategies and truthful evidence | Which inputs use which strategy |
| Validation | Ordered runner, structured result, fail-closed blocking | Schemas, registered validator IDs/config |
| Write scope | Safe binding/path resolution and effect broker | Allowed roots, path policy, forbidden surfaces |
| Operation | Registered mechanism interface and effect result model | Intent, mechanism ID, allowed effects, domain parameters |
| Canonical result | One explicit result reference in Phase result | Domain owner, locator, schema, authority rule |
| Verification | Runner and status aggregation | Domain predicates/verifiers and artifact scope |
| Evidence | Core evidence envelope, manifest, final status/exit | Required domain checks/evidence schema/retention class |
| Idempotency | Generic key/digest/conflict protocol | Scope, digest projection and canonical lookup |
| Failure | Generic truthful terminal classes | Domain success/no-effect/partial predicates |
| Rollback/correction | Never assume success; invoke only declared policy | None, append correction, compensation, or separate rollback contract |

## 4. Contract trust model

A contract bundle may reference only:

- bundled JSON Schemas by content hash;
- registered validators by exact ID/version;
- registered effect mechanisms by exact ID/version;
- registered path/privacy/retention policies;
- declarative configuration validated against each extension's config schema.

Registry/trust ownership is outside the operation contract. Phase Core resolves entries from an installation-controlled registry; the installation trust policy determines trusted release/publisher digests. Every reference binds ID, exact version and package digest. In v1, mutation mechanisms are release-bundled core TCB components and all mutation flows through the effect broker. Optional third-party validators require a separately specified read-only worker/sandbox; registration alone does not make extension code safe. Third-party mutation executors are not supported in v1.

A contract must not contain:

- shell commands;
- import paths or arbitrary executable paths;
- free-form prompts treated as validators;
- unrestricted target paths;
- credentials/secrets;
- an instruction to bypass the effect broker;
- claims of approval, rollback, atomicity, or confinement without required mechanisms/tests.

Human/LLM semantic review can produce a candidate or approval artifact, but Phase treats it as declared input and validates only the contractually checkable bindings.

## 5. Candidate model

Candidate is operation-specific but its envelope has universal metadata:

- candidate ID;
- contract ID/version;
- actor/invocation declarations;
- received timestamp;
- input mode/encoding;
- payload or bundle references;
- optional idempotency key;
- provenance references.

Contract payload examples:

- `task_journal.v1`: task command and event data;
- `source_admission.v1`: reviewed source package, payload and placement request;
- `knowledge_admission.v1`: reviewed knowledge package, profile/taxonomy bindings and placement request.

Core does not interpret these payloads beyond schema and registered validators.

## 6. Validators

Validator categories:

1. **Core invariants:** contract digest, run containment, supported versions.
2. **Structural:** JSON Schema and encoding/shape.
3. **Binding/provenance:** references, hashes, identity equality.
4. **Domain policy:** state transition, review decision, profile/taxonomy mapping.
5. **Plan/write scope:** complete effect plan, target containment, expected pre-state.
6. **Post-operation:** destination/result state, hashes, state machine, chain/head.
7. **Evidence:** required reached-step artifacts and schema.

Each validator result contains ID/version, status (`pass`, `fail`, `unknown`, `not_reached`), observed/expected, source references, blockers, and timing. A passing schema validator never implies semantic truth.

## 7. Write scope and effect model

`write_scope` is capability data, not only a prose allowlist. Before mutation, core must resolve bindings to canonical roots and validate the entire planned effect set.

Supported operation intents and expected mechanisms:

| Intent | Typical mechanism | Required policy |
|---|---|---|
| `append` | lock + expected-head + append bytes | stream format, concurrency, torn-tail handling |
| `copy` | content-addressed copy | source/destination hashes, overwrite rule, preflight all items |
| `create` | exclusive create | destination absent, path containment, durability |
| `update` | compare-and-swap replacement | expected before hash, before image, partial/recovery semantics |
| `correction` | append correction or separate compensating operation | target reference, reason, projection/authority rules |

Operation intent does not prove atomicity. `atomicity_claim` must name the exact boundary: for example, one exclusive create/rename on a supported local filesystem. Multi-effect operations remain partial-failure capable unless a tested transaction mechanism exists.

## 8. Canonical result and evidence

The contract must identify:

- canonical result owner ID;
- locator derivation from safe bindings;
- result schema/invariants;
- whether result pre-exists and is appended/updated;
- how Phase links result digest/head/state token;
- which surface wins if wrapper output disagrees.

Phase Core always owns the canonical Phase evidence bundle. The contract extends, but does not replace, the core evidence envelope.

A success result requires:

1. operation completed according to mechanism output;
2. post-operation predicates pass;
3. canonical result reference is resolvable under the contract rules;
4. required evidence exists and validates;
5. final status/exit code are emitted.

If result commit is observed but evidence finalization fails, status is `committed_unverified`, not success and not no-effect failure.

## 9. Idempotency

The contract defines domain identity; core runs the protocol:

1. derive canonical request digest from the contract profile;
2. bind the key to contract ID/version and declared scope;
3. search the contract-declared canonical lookup surface;
4. same key + same digest + verified success → return existing result/evidence reference;
5. same key + different digest → conflict;
6. previous partial/indeterminate → do not replay automatically; require recovery/inspection policy.

For task journaling, operation ID is found in the task stream. For admission, same destination and content hash may be idempotent. These lookup semantics stay contract-specific.

## 10. Failure, rollback, and correction

The contract must distinguish:

- validation rejection before effect;
- failed operation with verified no effect;
- partial effects;
- committed but unverified result;
- indeterminate target state;
- verified success.

Rollback is never inferred from a plan file. Allowed policies:

- `none`: preserve result/evidence and require operator action;
- `append_correction`: append a new domain record; never rewrite history;
- `compensating_operation`: execute a separately validated effect plan;
- `snapshot_restore`: only if an exact before-image and tested restore mechanism exist;
- separate rollback contract for high-risk mutation.

Automatic rollback defaults to false because it can compound partial failure.

## 11. Minimum contract conformance suite

Before a contract is installable, tests must prove:

- valid/invalid candidate fixtures;
- missing/mutated input behavior;
- validator ID/version/config rejection;
- write-scope traversal/symlink/reparse/collision rejection;
- operation preconditions and conflicting state;
- idempotent replay and key conflict;
- operation failure before/after first effect;
- post-verification failure and `committed_unverified` classification;
- evidence schema and reached-step requirements;
- platform-specific guarantees actually claimed by the contract.

The installation/extension layer must separately prove registry tamper detection, trust-root behavior, exact package-digest binding, capability denial, and refusal to load untrusted or mutable name-only entries.
