# Admission v1 Specification Candidates

Status: **non-executable and unregistered**.

This directory contains draft artifacts for `source_admission.v1@1.0.0` and `knowledge_admission.v1@1.0.0`. Nothing here is loaded by `src/phase_tool/data/registry.json`, bundled under `src/phase_tool/data/contracts/`, imported by runtime, or executable.

## Activation guards

- `activation_state` is fixed to `non_executable_unregistered`.
- Contract descriptors validate only against the local candidate descriptor schema, not the active Phase contract schema.
- Future domain validator IDs are listed as **required registrations before activation**, not trusted registry references.
- The two mechanism bindings are exact references to already bundled generic mechanisms; current runtime still cannot execute mixed ordered effects and must continue to fail closed.
- No implementation module, command, absolute path, live KB layout, or active registry mutation appears here.

## Layout

```text
contracts/
  source_admission.v1.candidate.json
  knowledge_admission.v1.candidate.json
schemas/
  admission-canonical-json-vector.schema.json
  admission-contract-descriptor-candidate.schema.json
  admission-semantic-case.schema.json
  ordered-effect-plan.schema.json
  ordered-effect-progress.schema.json
  source-admission-candidate.schema.json
  source-provenance.schema.json
  source-result.schema.json
  source-result-reference.schema.json
  source-result-binding.schema.json
  knowledge-admission-candidate.schema.json
  knowledge-provenance.schema.json
  knowledge-result.schema.json
  knowledge-result-reference.schema.json
fixtures/
  positive/
  negative/
  partial/
  semantic/
  semantic-invalid/
  golden/
fixture-catalog.json
manifest.sha256
```

`fixture-catalog.json` separates schema-valid pairs, schema-invalid negative pairs, and schema-valid-but-semantically-invalid pairs with expected neutral reason codes. `manifest.sha256` covers every candidate artifact except itself. Golden vectors bind `admission_canonical_json_v1` values to exact UTF-8 hex and SHA-256 digests.

## Normative companion documents

- `ADMISSION-CONTRACT-DECISIONS.md`
- `ADMISSION-MULTI-EFFECT-SPEC-CANDIDATE.md`
- `STAGE-6-SOURCE-ADMISSION-SPEC-CANDIDATE.md`
- `STAGE-7-KNOWLEDGE-ADMISSION-SPEC-CANDIDATE.md`
- `ADMISSION-CONTRACT-OWNERSHIP-MATRIX.md`
- `ADMISSION-GUARANTEE-TRACEABILITY.md`

## Validation meaning

Passing draft validation proves JSON/schema consistency and fixture expectations only. It does not prove registry trust, executable planning, durable multi-effect sequencing, recovery correctness, platform path safety, or admission behavior. Those require the future implementation and executable acceptance tests named in traceability.
