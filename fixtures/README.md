# Stage 1 Fixtures

These files are deterministic specification vectors. They do not invoke Phase runtime and do not mutate a target.

## Layout

```text
fixtures/
  schemas/
    conformance-case.schema.json
    fixture-append-candidate.schema.json
    fixture-copy-candidate.schema.json
  positive/
  negative/
  adversarial/
  golden/
  catalog.json
  manifest.sha256
```

## Synthetic contracts

- `contracts/fixtures/fixture_append.v1.json` — neutral exclusive-create/expected-head append model;
- `contracts/fixtures/fixture_copy.v1.json` — neutral content-addressed copy/create model.

They contain no task/source/knowledge/admission vocabulary.

## Case classes

- **positive:** expected verified success or verified idempotent reuse;
- **negative:** malformed/untrusted/conflicting/stale input that must fail closed;
- **adversarial:** path races, concurrency, torn/partial effects, evidence failure, and unknown state.

Each case declares:

- contract fixture;
- required coverage tags;
- abstract setup/stimulus;
- expected validator summaries;
- terminal status;
- mutation-attempt fact;
- retry/recovery disposition;
- explicit `target_mutation_permitted_in_stage1: false`.

## Golden vectors

- `exact-byte-hash-vectors.json` binds SHA-256 to exact bytes only;
- `terminal-status-vectors.json` records compact status/exit invariants;
- `terminal-receipts/*.json` provides schema-valid receipts for all seven statuses plus verified reuse;
- `effect-journal.*.valid.json` provides the before-attempt and post-observation marker pair.

The exact-byte vectors do not define general JSON canonicalization.

## Determinism

Generated contract/probe instances, case vectors, golden instances, and `catalog.json` use sorted object keys, two-space indentation, UTF-8, and one final newline. Hand-authored `*.schema.json` files preserve semantic/readability ordering and are checked by their content digest rather than key sorting. `manifest.sha256` is sorted by repository-relative path and excludes itself.

Regeneration must be byte-identical. This formatting rule is an artifact-generation convention, not the canonical request digest specification.

## Safety

There are no fixture executors in Stage 1. Paths, faults, locks, destinations, and effects are data only. Future executable conformance tests require separate Stage 2 authorization and must use disposable targets.
