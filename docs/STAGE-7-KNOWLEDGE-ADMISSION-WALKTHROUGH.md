# Stage 7 — Knowledge admission walkthrough

## Boundary

Stage 7 activates `knowledge_admission.v1@1.0.0` as a contract-owned adapter over the existing `PhaseCore.run` lifecycle. It does not add a knowledge pipeline, a second Core, or a separate mutation engine.

The exact active registry binding exercised below is:

```text
knowledge_admission.v1@1.0.0
package_digest: sha256:d015367dc85347bd3f36abb6a2ba5158ef1b135f3b4add544bbc94f632cebad8
```

## Reused generic mechanisms

The contract reuses the accepted ordered multi-effect lifecycle:

1. capture and freeze the structured candidate and artifact input;
2. run exact contract, candidate, source-binding, provenance, identity, placement and result validators;
3. persist durable intent and ordered effect plan before mutation;
4. execute `effect.0.blob` with `content_addressed_copy`;
5. execute `effect.1.descriptor` with `mechanism.exclusive_create_v1` only after the verified prefix permits it;
6. verify the aggregate knowledge result;
7. finalize the Phase receipt;
8. reconstruct and verify the knowledge result/reference/binding through normal run inspection.

Knowledge-specific semantics remain in:

- `schemas/knowledge-*.schema.json` and their bundled mirrors;
- code-owned static validator and hook bindings;
- `src/phase_tool/contracts/knowledge_admission_v1.py`;
- contract result/reference/binding reconstruction and inspection.

The generic runtime additions are domain-neutral: contract hooks may normalize a structured candidate before request hashing, validators and brokers receive a generic evidence-root context, brokers invoke a generic pre-effect hook, and inspection passes the same evidence-root context to result verification.

## Exact source evidence

A knowledge candidate cannot rely on a bare `source_result_id`. Each source binding carries:

- exact source contract identity;
- source result and logical source identifiers;
- source blob locator and content digest;
- source descriptor locator and digest;
- source Phase run ID and receipt digest.

The contract validates the descriptor schema and canonical bytes, recomputes source provenance and source-result identity, verifies the blob, and authenticates the complete source Phase evidence set through normal read-only inspection. Receipt, descriptor, effect-receipt and binding run IDs, exact package digest, effect order/status/kind, intent/plan/attachment bindings and target state must all agree. The same evidence is rechecked before each effect. The canonical source-binding set is sorted and duplicate-free before the request digest is calculated.

## Result identity and placement

The artifact is stored at its content-addressed locator. The canonical descriptor is exclusively created at:

```text
namespaces/{namespace}/knowledge-results/{logical_knowledge_id}/{knowledge_result_id}.json
```

`knowledge_result_id` is derived from the exact contract identity, namespace, logical identity, artifact identity, artifact kind/format, provenance digest and exact `supersedes` reference. The descriptor binds the artifact and the source evidence. A changed request under the same idempotency key conflicts. An exact normalized result reuses the existing verified receipt even when the caller supplies a different operation key, but only after current candidate/source validation and complete inspection of the prior evidence and target.

## Real CLI acceptance

The executable harness is:

```bash
env -u PYTHONPATH .venv/Scripts/python.exe scripts/stage7_cli_acceptance.py \
  --tmp-root .stage7-tmp/final-cli-post-review
```

Observed output:

```json
{"scenario_count":13,"success":true,"summary":"C:\\Users\\Gennady\\HermesWorkspace\\Research\\agent-task-journal\\.stage7-tmp\\final-cli-post-review\\stage7-cli-acceptance-summary.json"}
```

The structured summary records 13 subprocess scenarios and no failures. Public `phase` CLI commands prove source bootstrap, source inspection, knowledge validation, planning, execution, inspection, exact reuse, same-key conflict, malformed/missing source evidence and logical-identity conflict. Controlled helpers use the same `PhaseCore`, evidence store and broker only for deterministic failure boundaries unavailable as public CLI flags.

Observed result evidence:

```text
knowledge_result_id: knowledge-result-a866b7f2632659c692df19e90cc896c9f59203d8b717704e722360efecd489bb
artifact_digest: sha256:d54268eed56a38b646fed498979912aa51209fbf6548d202445d86c93dce8767
descriptor_digest: sha256:ae1d522532c21d38a8df81a50e52bf10716443a49bd95429bd2bd436fc51e2d4
receipt_digest: sha256:4a2786bec110e9e371bfe99fec5aba3b0002229ca7ceff0bc96106a74a904ca2
```

All structured checks were true:

- exact active contract binding;
- `PYTHONPATH` absent in subprocesses;
- ordered effects exactly `effect.0.blob`, then `effect.1.descriptor`;
- descriptor binds the observed artifact blob;
- exact source binding preserved;
- inspected target verified;
- result/run/receipt linkage verified;
- effect-0 and effect-1 failures reported truthful partial outcomes.

The result, descriptor and receipt digests above are evidence from that exact root-authority-bound run; they are not asserted as cross-root constants.

## Windows long-path regression

Two clean isolated reproductions used descriptor paths of 275 characters. In both runs `os.walk` returned the exact descriptor while the ordinary path produced `os.path.lexists == false`, `Path.exists == false`, `Path.lstat` failure and `Path.open` failure. The same path with the Windows `\\?\` prefix produced `lexists == true`, `exists == true`, a regular 2,072-byte file, and a successful read. The descriptor and its parent had no symlink or reparse attributes. Execute and inspection subprocesses had already returned, their handles were closed, and cleanup had not started.

This established a Windows `MAX_PATH` access defect rather than stale locator, cleanup race, open mutation handle or publication failure. Evidence freezing, evidence writes, evidence inspection/enumeration, source and supersedes receipt verification, idempotency scans, broker evidence reads and the acceptance harness now use the existing platform-path adapter where a long Windows path requires it. Platform conversion preserves lexical paths so symlink/reparse checks are not bypassed by resolution. Regressions cover the complete CLI acceptance under a descriptor path of at least 260 characters and long evidence paths for source, supersedes and same-key conflict handling; no sleep or retry logic is used.

## Claims not made

Phase Tool validates deterministic admission evidence; it does not determine whether a knowledge claim is true. Per-effect durability is proven, not cross-effect atomicity. The Stage 7 result is root-authority-bound evidence and is not claimed to be a cross-root reproducibility invariant.
