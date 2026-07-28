# Stage 6 — `source_admission.v1` Specification Candidate

Status: **non-executable, unregistered specification candidate**.

## 1. Purpose and boundary

Admit exactly one caller-supplied immutable source asset as a verified canonical pair: a content-addressed blob and an immutable source descriptor. Phase hashes and verifies bytes, validates contract-owned metadata/provenance shape, computes placement, executes bounded no-replace effects, and records evidence. It does not inspect meaning, classify content, approve a source, assign taxonomy, or run a review workflow.

Contract identity is `source_admission.v1@1.0.0`. Runtime activation is outside this task.

## 2. Candidate schema

Normative draft: `contracts/spec-candidates/admission-v1/schemas/source-admission-candidate.schema.json`.

| Field | Req. | Owner | Validation | Request digest | Canonical identity | Change rule |
|---|---:|---|---|---:|---:|---|
| `candidate_version` | yes | Contract | exactly `1.0` | yes | no | new contract candidate version |
| `contract` | yes | Contract/caller assertion | exact ID/version | yes | yes | new exact contract request |
| `operation_id` | yes | Caller | bounded opaque logical token | yes | no | immutable for operation |
| `idempotency_key` | yes | Caller | bounded; v1 semantic validator requires equality with `operation_id` | yes | no | different key is new operation |
| `logical_source_id` | yes | Caller/domain | path-safe lowercase immutable-version ID; never inferred from filename | yes | yes | different ID for a new version |
| `asset_input.binding_id` | yes | Contract | exactly `asset`; external interface resolves input, candidate carries no path | yes | no | fixed |
| `asset_input.expected_digest` | no/null | Caller assertion | SHA-256; must equal observed frozen bytes if supplied | yes | via observed digest | changed assertion is new request |
| `asset_input.expected_length` | no/null | Caller assertion | non-negative; must equal observed length if supplied | yes | via observed length | changed assertion is new request |
| `declared_media_type` | yes | Caller assertion | bounded media-type syntax; no content sniffing claim | yes | yes | immutable descriptor; new version to change |
| `original_filename` | no/null | Caller metadata | basename only; no slash/backslash/control/`.`/`..` | yes | descriptor/result identity, **not content identity** | new version/correction relation |
| `provenance` | yes | Caller/contract | source provenance schema and semantic validator | yes | provenance digest | new version/correction relation |
| `placement.target_root_binding` | yes | Contract assertion | exactly `admission_result_root`; installation resolves it | yes | yes | cannot be redirected by caller |
| `placement.namespace` | yes | Caller/domain | strict identifier, authorized by installation policy | yes | yes | new result placement/request |
| `supersedes` | yes, nullable | Caller/domain | exact prior source result reference; must inspect successfully | yes | yes | immutable relation |
| `request_metadata` | yes | Caller/adapter | bounded closed object, no secrets | yes | no | same key change conflicts |

All candidate fields are captured in the canonical candidate digest and canonical request digest. Generated run ID/times and Phase observations are excluded.

## 3. Input capture

The interface receives the asset separately from candidate JSON through input binding `asset`; a filesystem path/URI is never a target locator and is not embedded as trusted authority. Freeze strategy is `copy_and_hash`:

1. read exact bytes once into Phase frozen evidence;
2. compute observed SHA-256 and length;
3. compare optional caller assertions;
4. consume only frozen evidence thereafter.

A mutable upstream locator is untrusted provenance metadata and is not reread by a mechanism.

## 4. Identity model

| Concept | Definition |
|---|---|
| Content identity | `sha256:<hex>` of exact frozen asset bytes |
| Logical source identity | caller-supplied `logical_source_id`, domain-owned opaque identity for this immutable version |
| Operation identity | `operation_id`/idempotency tuple, identifying one request attempt lineage |
| Result identity | `source-result-<hex>` over the canonical source identity projection |
| Locator | contract-computed relative address under an installation-bound root; never identity by itself |

Canonical source identity projection, serialized with `admission_canonical_json_v1` from Decisions D-09, contains: exact contract ID/version, namespace, logical source ID, observed content digest/length, declared media type, original filename/null, provenance digest, and exact supersedes reference/null. `source_result_id` is `source-result-` plus lowercase SHA-256 of those exact canonical bytes including terminal LF.

Normative behavior:

- Source ID is caller-supplied, never computed from filename.
- Different logical source IDs may refer to identical bytes; they produce distinct descriptors and may reuse one blob.
- One logical source ID represents one immutable source version. Same ID with different content, filename, provenance, namespace, or supersedes projection is conflict.
- Same bytes with a different filename do not change content identity, but create a different descriptor identity; they require a new logical source ID and optional `supersedes` relation.
- A new version uses new logical/result IDs and exact `supersedes`; no old bytes/descriptor are changed.
- V1 has no in-place correction. Immutable supersession is supported; review/approval is not.

## 5. Placement

The planner computes and freezes both locators before intent:

```text
blob = blobs/sha256/<content hex[0:2]>/<content hex>
descriptor = namespaces/<namespace>/source-results/<logical_source_id>/<source_result_id>.json
```

Both use root binding `admission_result_root`, strict relative path policy, no-follow/reparse rejection and no-replace publication. Namespace is policy-validated; no concrete KB layout, source family, collection path, absolute destination, filename-derived path, or user-supplied locator is accepted.

## 6. Canonical source descriptor

Normative draft: `source-result.schema.json`.

Required canonical fields:

- `result_schema_version`;
- deterministic `source_result_id`;
- `logical_source_id`;
- observed content digest and length;
- declared media type;
- canonical blob and descriptor locators;
- original filename metadata/null;
- canonical provenance object and its digest;
- exact admission contract/version;
- Phase `run_id` plus receipt authority rule (not final receipt digest; see decision D-06);
- Phase observation time;
- exact supersedes reference/null.

The descriptor is canonical metadata authority. The blob is canonical byte authority. Success requires both and their binding. Phase receipt is not the source descriptor and cannot substitute for a missing descriptor.

After receipt finalization, `source-result-reference.schema.json` represents the transferable exact value object with source result/logical IDs, content and descriptor digests/locators, exact source contract, and exact Phase run/receipt digest. It is reconstructed from descriptor+receipt and is not a separately persisted third target/effect. Stage 7 embeds this exact information in its source bindings.

## 7. Provenance

Normative draft: `source-provenance.schema.json`.

- `origin.kind`, locator and label describe where the caller says the file came from.
- Origin locator/URI is untrusted metadata; it is not opened by the mutation mechanism and proves neither authorship nor truth.
- `supplied_by` records who/what passed the asset to admission as a declaration, not authenticated identity unless external policy establishes that.
- Phase-observed time belongs to canonical result/evidence, not caller provenance.
- Verified content digest/length come from frozen bytes, not provenance.
- Relation to prior admitted content is the exact `supersedes` result reference.

No author trust, regulatory status, semantic class, review verdict, source family, or KB taxonomy is inferred.

## 8. Static effects

Exactly two effects, per the neutral specification:

1. `effect.0.blob`: bundled `content_addressed_copy@1.0.0`, source=frozen asset, target=content locator, precondition `absent_or_same_digest`;
2. `effect.1.descriptor`: bundled `mechanism.exclusive_create_v1@1.0.0`, source=pre-serialized descriptor bytes, target=descriptor locator, precondition `absent`.

Descriptor bytes are frozen before intent and include run ID but not intent/receipt digest, avoiding digest cycles. Durable intent and effect journal precede invocation.

## 9. Idempotency/conflict matrix

| Situation | Required behavior |
|---|---|
| same operation key + same request digest + exact verified pair/receipt | reverify pair and evidence; `succeeded_verified`, `reused_existing`, no mechanism invocation |
| same operation key + different request digest | `rejected`, idempotency conflict |
| same logical source ID + same identity projection | exact descriptor/result reuse only after descriptor, blob, and receipt revalidation |
| same logical source ID + different content or metadata projection | `rejected`, logical identity conflict |
| same content + different logical source ID | allowed; blob may be verified existing, new descriptor required |
| blob exists + descriptor absent | verify blob as existing, then create descriptor if the current request/intent safely binds it |
| descriptor exists + blob absent | inconsistent canonical result; reject/inspect; do not silently fill blob under it |
| identical descriptor exists | verify exact descriptor bytes, referenced blob, result ID and prior receipt before reuse |
| conflicting descriptor exists | conflict, no overwrite; if blob newly created earlier, aggregate `failed_partial` |
| prior `failed_partial` | inspect all effects; complete only exact absent safe effect under recovery rules |
| prior `committed_unverified` | verify/finalize existing pair, no blind replay |
| prior `indeterminate` or unverifiable | retry forbidden pending inspection |

A same-digest orphan blob has content identity but no source domain identity until a descriptor is safely created. It is never attributed as created by this run when reused.

## 10. Partial states and inspection

- no effect attempted: rejected/aborted evidence only;
- blob absent after attempted effect with positive proof: `failed_no_effect`;
- newly created verified blob, descriptor not verified: `failed_partial`;
- verified-existing blob, descriptor conflict, positive proof no mutation: `failed_no_effect`;
- both objects present, aggregate/result/evidence check incomplete: `committed_unverified`;
- any attempted effect state unavailable: `indeterminate`.

Inspection verifies plan/journal/effect sets, blob digest/length/locator, descriptor digest/schema/result ID, descriptor-to-blob binding, run binding, receipt linkage, and reuse eligibility. It never repairs target state.

## 11. Review policy

Review is not required by `source_admission.v1`. Phase performs structural/provenance/content/placement validation only. A future version may require an external review reference, but semantic approval remains outside Phase.

## 12. Future validators and acceptance tests

Candidate-only required validator responsibilities are named in the inert descriptor. Runtime implementation must register exact trusted bindings and test at least:

- expected digest/length match and mismatch;
- filename never chooses content identity or path;
- arbitrary absolute destination rejection;
- deterministic locator/result ID vectors;
- same/different logical/content identity matrix;
- two-effect crash/failure at every marker/effect/evidence boundary;
- existing/missing/conflicting blob/descriptor matrix;
- verified reuse with tampered result/receipt rejection;
- immutable supersession;
- Core/domain token architecture scans.
