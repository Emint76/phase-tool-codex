# Stage 7 — `knowledge_admission.v1` Specification Candidate

Status: **non-executable, unregistered specification candidate**.

## 1. Purpose and boundary

Admit exactly one already formed immutable knowledge artifact as a verified canonical blob+descriptor pair. Phase does not create knowledge, infer claims, judge truth, approve publication, select taxonomy, or orchestrate transformation. Producer/transformation data are bounded declarations. Provenance to admitted sources is exact and revalidated.

Contract identity is `knowledge_admission.v1@1.0.0`. Runtime activation is outside this task.

## 2. Candidate schema

Normative draft: `knowledge-admission-candidate.schema.json`.

| Field | Req. | Owner | Validation | Request digest | Canonical identity | Change rule |
|---|---:|---|---|---:|---:|---|
| `candidate_version` | yes | Contract | exactly `1.0` | yes | no | new candidate version |
| `contract` | yes | Contract/caller assertion | exact ID/version | yes | yes | new exact contract |
| `operation_id` | yes | Caller | bounded opaque token | yes | no | immutable operation |
| `idempotency_key` | yes | Caller | bounded; v1 requires equality with operation ID | yes | no | different key is new operation |
| `logical_knowledge_id` | yes | Caller/domain | path-safe lowercase immutable-version ID | yes | yes | new ID for version/correction |
| `artifact_input` | yes | Caller assertion + interface binding | binding `asset`; optional expected digest/length checked against frozen bytes | yes | observed digest/length | changed assertion is new request |
| `artifact_kind` | yes | Caller/domain | generic identifier only; no domain taxonomy | yes | yes | new version to change |
| `artifact_format` | yes | Caller/domain | bounded format/media declaration | yes | yes | new version to change |
| `provenance.source_bindings` | yes, min 1 | Caller + contract validator | exact source result/descriptor/blob/receipt/contract bindings | yes | provenance digest | new version/correction |
| `provenance.producer` | yes | Caller declaration | bounded kind/id/version | yes | provenance digest | new version/correction |
| `provenance.transformation` | yes | Caller declaration | bounded id/version/parameters digest | yes | provenance digest | new version/correction |
| `placement` | yes | Contract/caller namespace | fixed root plus policy-authorized namespace | yes | yes | no caller locator |
| `supersedes` | yes, nullable | Caller/domain | exact prior knowledge result reference and inspection | yes | yes | immutable relation |
| `request_metadata` | yes | Caller/adapter | bounded closed object | yes | no | same key change conflicts |

All candidate fields enter canonical candidate/request digest; generated run/times and Phase observations do not.

## 3. Artifact capture

Input binding `asset` is frozen by `copy_and_hash`. Optional expected digest/length are assertions checked against observed bytes. Mechanisms consume only the frozen blob. `artifact_kind` and `artifact_format` are declarations; Phase does not parse or semantically validate content unless a future exact contract validator explicitly does so without changing the Core boundary.

## 4. Identity model

| Concept | Definition |
|---|---|
| Artifact content identity | SHA-256 of exact frozen artifact bytes |
| Logical knowledge identity | caller-supplied immutable-version `logical_knowledge_id` |
| Source provenance identity | ordered, deduplicated canonical set of exact verified source result bindings |
| Operation identity | scoped idempotency tuple |
| Result identity | `knowledge-result-<hex>` over canonical knowledge identity projection |
| Locator | computed relative placement, not identity itself |

The canonical identity projection is serialized with `admission_canonical_json_v1` from Decisions D-09 and contains exact contract, namespace, logical knowledge ID, observed artifact digest/length, artifact kind/format, provenance digest, and exact supersedes reference/null. `knowledge_result_id` is `knowledge-result-` plus lowercase SHA-256 of those exact canonical bytes including terminal LF.

Normative rules:

- Multiple knowledge artifacts may derive from one exact source result.
- One knowledge artifact may bind multiple exact source results (1..64); before `admission_canonical_json_v1` serialization, the contract validator sorts bindings by `(source_result_id, source_descriptor_digest, source_content_digest)` and rejects duplicates.
- Same knowledge ID with any different artifact bytes, kind/format, source binding, producer/transformation declaration, namespace, or supersedes relation is conflict.
- Identical artifact bytes with changed provenance are a different identity projection and conflict under the same logical ID.
- A new version/correction uses new logical/result IDs and exact `supersedes`; no existing bytes or descriptor are rewritten.
- V1 requires at least one verified source admission result. Born-digital/manual knowledge without a source binding is rejected and needs a future explicit policy/version.

## 5. Verifiable source binding

Normative draft: `source-result-binding.schema.json`. Caller cannot supply only a source ID. Every binding includes:

- source canonical result ID;
- logical source ID;
- source content digest and canonical blob locator;
- source descriptor digest and locator;
- exact `source_admission.v1@1.0.0` contract;
- source Phase run ID and exact receipt digest.

Before planning and again before effect 0, the Stage 7 contract-owned validator MUST:

1. resolve source descriptor under installed read authority, not a caller path;
2. verify descriptor bytes/digest/schema and source result ID derivation;
3. resolve and hash the source blob; verify digest/length and descriptor binding;
4. resolve source Phase receipt by run authority; validate digest/schema/status `succeeded_verified`;
5. verify receipt exact contract/result reference/effect evidence matches the descriptor and blob;
6. reject changed, missing, partial, committed-unverified, indeterminate, or inaccessible source state;
7. freeze the validated source-binding observations/tokens into intent and revalidate at the pre-operation boundary.

Caller-provided provenance structure alone is never trusted.

## 6. Placement

Before intent the planner computes:

```text
blob = blobs/sha256/<artifact hex[0:2]>/<artifact hex>
descriptor = namespaces/<namespace>/knowledge-results/<logical_knowledge_id>/<knowledge_result_id>.json
```

The root is fixed `admission_result_root`. Caller supplies no absolute/relative locator. No KB-specific domain layout, taxonomy, PCR/formulation/cosmetics fields, or document-family routing appears in contract/Core.

## 7. Canonical knowledge descriptor

Normative draft: `knowledge-result.schema.json`.

It contains:

- schema/version;
- deterministic knowledge result ID and logical knowledge ID;
- observed artifact digest/length;
- artifact kind/format declarations;
- canonical blob and descriptor locators;
- complete exact source result bindings plus producer/transformation metadata;
- provenance digest;
- exact admission contract/version;
- Phase run ID and receipt authority rule;
- Phase-observed time;
- exact supersedes reference/null.

The descriptor is canonical metadata/provenance authority; the blob owns artifact bytes. The Phase receipt is execution evidence and cannot replace the descriptor. A post-finalization knowledge result-reference value object adds exact descriptor and receipt digests for transfer/inspection; it is reconstructed from descriptor+receipt and is not a third persisted target/effect.

## 8. Static effects

Exactly two ordered effects:

1. content-addressed copy/verify of frozen artifact;
2. exclusive create of pre-serialized immutable knowledge descriptor.

Mechanisms do not parse source bindings, producer metadata, artifact kind, or knowledge content. All domain validation and serialization occurs before the static plan. Neutral multi-effect rules, durable journal, no rollback and no false atomicity apply.

## 9. Version/correction policy

V1 selects policy **new logical and result ID with exact prior reference**:

- same logical knowledge ID + different identity projection always conflicts;
- corrected/revised artifact gets new logical knowledge ID and deterministic result ID;
- candidate/result `supersedes` points to the exact prior knowledge result reference;
- prior descriptor/blob/receipt remain immutable;
- supersession does not make prior execution unsuccessful and does not claim semantic correction was approved by Phase.

## 10. Idempotency/conflict/partial matrix

| Situation | Required behavior |
|---|---|
| same operation + same request + exact verified result/receipt | revalidate pair, provenance bindings and evidence; verified reuse |
| same operation + different request | pre-mutation idempotency conflict |
| same knowledge ID + exact artifact/provenance | exact result reuse only after full revalidation |
| same knowledge ID + different artifact | logical identity conflict |
| same artifact + changed provenance | provenance/identity conflict |
| source result changed/tampered after planning | pre-effect revalidation rejects; after effect attempt, classify by observed state |
| artifact blob created, descriptor absent | `failed_partial` if newly created; inspect and safely complete only under exact recovery |
| descriptor exists, artifact absent | inconsistent result; reject/inspect; no silent adoption |
| source no longer passes inspection | result cannot be reused or newly admitted; reject before mutation, otherwise unverified/indeterminate according to boundary |
| prior `failed_partial` | inspect every target and source binding; no blind replay |
| prior `committed_unverified` | verify/finalize existing pair; no replay |
| prior `indeterminate` | retry forbidden until inspection resolves |

A preexisting artifact blob may be verified/reused for different logical knowledge IDs, but every descriptor is distinct and no run claims creation of reused bytes.

## 11. Partial-state inspection

Inspection verifies:

- original intent/plan/journal/effect sets;
- artifact blob digest/length/locator;
- descriptor digest/schema/result ID and artifact binding;
- every source descriptor/blob/receipt binding;
- provenance digest and canonical ordering;
- run/result-reference/receipt linkage;
- exact supersedes relation;
- retry/recovery eligibility.

Inspection is read-only. It does not regenerate knowledge, repair provenance, select a replacement source, or rewrite canonical objects.

## 12. Review and truth boundary

Knowledge admission has no semantic review/approval field in v1. Phase validates that a fully formed artifact and exact source provenance satisfy the contract. It does not assert artifact truth, completeness, scientific quality, regulatory status, or appropriateness for a KB.

## 13. Future validators and acceptance tests

Runtime implementation must register exact contract-owned validators and prove:

- min-one exact source binding; arbitrary source ID rejected;
- tampered source descriptor/blob/receipt rejected before mutation;
- multi-source canonical ordering/deduplication;
- same ID/different artifact and same artifact/changed provenance conflicts;
- no-source born-digital request rejected;
- deterministic placement/result/provenance digests;
- full two-effect partial/evidence failure matrix;
- descriptor is canonical metadata owner, not receipt;
- mechanisms/Core contain no knowledge/source field routing;
- immutable supersession with prior objects unchanged.
