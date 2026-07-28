# Admission Contract Decisions — Stage 6–7 Candidate

Status: **non-executable specification candidate**. This file does not activate contracts, validators, mechanisms, registry entries, or runtime behavior.

## D-01 — Admission result architecture

**Decision: Variant A, ordered immutable blob then immutable canonical descriptor.**

One admission operation has exactly two statically planned target effects:

1. `effect.0.blob`: `copy_blob` publishes or verifies the frozen payload at a content-addressed locator;
2. `effect.1.descriptor`: `exclusive_create` publishes the pre-serialized canonical domain descriptor.

The canonical domain result is the pair **verified blob + verified descriptor**, with the descriptor as metadata authority and the blob as byte authority. The Phase receipt references the descriptor as canonical result and binds both effect observations; it is execution evidence, not the domain metadata database.

### Why A fits the repository

- `EVIDENCE-MODEL.md` already separates Phase evidence from domain canonical ownership.
- Stage 5 proves frozen content-addressed, no-replace blob creation and read-back verification.
- Stage 3 proves no-replace immutable record creation.
- Existing terminal statuses already represent partial, committed-unverified, and indeterminate outcomes.
- Existing neutral effect-journal design already prohibits false multi-effect atomicity and blind replay.
- Domain descriptors remain portable and inspectable independently of `.phase/runs/`.

### Why not B — immutable package

B would reduce lifecycle work by fitting one currently supported target effect, but it would require a new package object model, exact package byte profile, package builder/validator/extractor, payload addressing rules, and a decision whether Stage 5 `objects/<payload-digest>` remains authoritative. It either duplicates payload bytes or makes raw-byte identity subordinate to a package digest. Therefore B is not an implementation-free shortcut: it shifts the new architecture into the domain artifact and its consumers. That is a material change to the accepted Stage 5 content-addressed object model, not the minimal domain baseline chosen here.

### Why not C — blob as result

C leaves provenance and logical identity only in Phase receipt/evidence. This violates the repository rule that the Phase receipt is the canonical execution outcome but not the canonical domain result. It would make retention or movement of admitted assets dependent on the run evidence tree and would make independent domain indexing unable to reconstruct authoritative metadata.

## D-02 — Neutral multi-effect extension is required

Variant A requires a neutral ordered-effect extension before runtime activation. This is a necessity of the selected A architecture, not a claim that every conceivable admission format requires multiple effects. The active effect-plan model has one top-level mechanism and Stage 5 intentionally rejects more than one effect. The future neutral extension must bind a mechanism per effect while retaining one Core lifecycle and one aggregate Phase receipt.

Admission v1 maximum is exactly **2 effects**. No general workflow language, branching, loops, dynamic planning, rollback, scheduling, or domain routing is introduced.

## D-03 — Existing terminal model is sufficient

No new terminal statuses are introduced. Ordered effect state is represented in structured effect receipts, durable journal entries, and an `ordered-effect-progress` attachment. Aggregate classification uses existing precedence:

- unknown state after attempt → `indeterminate`;
- known new blob but descriptor incomplete → `failed_partial`;
- both canonical objects observed but required verification/evidence incomplete → `committed_unverified`;
- positively no canonical mutation after attempted verification/conflict → `failed_no_effect`;
- all predicates and evidence verified, including verified reuse → `succeeded_verified`.

## D-04 — Placement

Caller supplies only a bounded namespace and the fixed root-binding assertion `admission_result_root`; it never supplies a destination locator.

Frozen placement policy `canonical_admission_placement_v1` computes before durable intent:

```text
blob:
  blobs/sha256/<digest[0:2]>/<64 lowercase hex>

source descriptor:
  namespaces/<namespace>/source-results/<logical_source_id>/<source_result_id>.json

knowledge descriptor:
  namespaces/<namespace>/knowledge-results/<logical_knowledge_id>/<knowledge_result_id>.json
```

All components pass strict relative-locator policy. The installation resolves `admission_result_root`; the candidate cannot provide an absolute path.

## D-05 — Identity and immutable versioning

Content identity is exact SHA-256 of frozen bytes. It is distinct from caller-supplied logical identity, operation identity, result identity, and locator.

`source_result_id` and `knowledge_result_id` are deterministic lowercase SHA-256 identifiers over canonical JSON identity projections defined by the Stage specs. They do not use filename as content identity and do not include Phase receipt digest.

V1 never changes an existing logical identity to new bytes or provenance. Same logical identity plus a different identity projection is a pre-mutation conflict. A new version/correction uses:

- a new logical ID;
- a new result ID;
- an exact immutable `supersedes` result reference.

Prior blob and descriptor bytes are never rewritten. Supersession is a relation, not retroactive approval or deletion.

## D-06 — No final receipt digest inside the descriptor

A descriptor contains `admission_run.run_id` and `receipt_authority: phase_evidence_by_run_id`, but not the final receipt digest. Including the final receipt digest would create a cycle: descriptor digest → effect plan/intent → receipt → descriptor. The final Phase receipt binds the descriptor digest and locator.

After finalization, a result-reference object containing the exact receipt digest is deterministically reconstructed from the immutable descriptor plus receipt. It is returned/embedded by later candidates as a value object; admission v1 does not persist it as a third canonical target and therefore does not add a third effect.

## D-07 — Review boundary

Neither admission v1 contract requires review. Existing design-probe review/profile/taxonomy assumptions are not promoted to normative behavior. A future contract version may accept a schema-valid external review reference and verify its form/binding; Phase must never make the semantic approval decision.

## D-08 — Knowledge requires verified source

Knowledge admission v1 requires at least one exact verified `source_admission.v1@1.0.0` result binding. Multiple knowledge artifacts may cite one source; one knowledge artifact may cite multiple sources. Born-digital/manual knowledge without a source admission result is rejected in v1 and requires a separately approved policy/version.

## D-09 — Canonical serialization

Admission uses the new candidate codec profile `admission_canonical_json_v1`; it does **not** claim that the repository has already accepted a general `canonical_json_v1` profile. Activation requires an exact validator/codec package binding and the golden corpus under `contracts/spec-candidates/admission-v1/fixtures/golden/`.

The complete byte profile is:

1. The input data model is JSON `null`, booleans, strings, arrays, objects, and integers in `[-9007199254740991, 9007199254740991]`. Floating-point values, NaN/Infinity, and negative-zero number spellings are rejected before canonicalization.
2. A parser MUST reject duplicate object keys. Object keys and all string values MUST contain only Unicode scalar values, MUST already be Unicode NFC, and MUST contain no unpaired surrogate code points. Canonicalization does not silently normalize accepted input.
3. Object keys are ordered by ascending Unicode scalar-value sequence after the NFC check. Arrays retain input order.
4. Strings use JSON double quotes. `"`, `\\`, U+0008, U+0009, U+000A, U+000C, and U+000D are encoded as `\"`, `\\\\`, `\b`, `\t`, `\n`, `\f`, and `\r`. Other U+0000..U+001F controls use lowercase `\u00xx`. `/` and every other Unicode scalar are emitted unescaped as UTF-8.
5. Literals are exactly `null`, `true`, and `false`. Integers use the shortest base-10 spelling with no leading plus or zeroes; integer zero is `0`.
6. Separators are exactly `,` and `:` with no surrounding whitespace. No BOM is permitted.
7. `admission_canonical_json_v1(value)` is the resulting UTF-8 byte sequence followed by exactly one LF byte (`0a`). Every candidate-defined structured digest and every result-ID identity-projection digest is SHA-256 over those exact bytes, including the terminal LF.

Draft source JSON may be pretty-printed for review, but it is never itself a digest preimage. The contract-owned codec first parses with duplicate-key rejection, performs the scalar/NFC/range checks above, and emits the exact canonical bytes. Golden preimage/hex/digest vectors are normative for the candidate baseline.
