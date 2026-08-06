# Stage 5 Content-Addressed Copy Walkthrough

This walkthrough is based on the freshly accepted CLI run written to `.stage5-tmp/final-cli/stage5-cli-acceptance-summary.json` by `scripts/stage5_cli_acceptance.py`. The summary is disposable evidence and is not tracked.

## Accepted Example

Scenario: `03_execute_new_text`

Command path: real `phase execute` CLI with `PYTHONPATH` unset.

Source payload verification:

- before: `exists=true`, `length=16`, `sha256=d6631fa3b666c3f252ddda64da2b2d0c6a11b494f68da7e8afd0aa38609092cb`
- after: `exists=true`, `length=16`, `sha256=d6631fa3b666c3f252ddda64da2b2d0c6a11b494f68da7e8afd0aa38609092cb`

Content binding:

- SHA-256 digest: `sha256:d6631fa3b666c3f252ddda64da2b2d0c6a11b494f68da7e8afd0aa38609092cb`
- length: `16`
- canonical locator: `objects/d6631fa3b666c3f252ddda64da2b2d0c6a11b494f68da7e8afd0aa38609092cb`

Target verification:

- before target tree: empty
- after target tree: `objects/d6631fa3b666c3f252ddda64da2b2d0c6a11b494f68da7e8afd0aa38609092cb`, `length=16`, `sha256=d6631fa3b666c3f252ddda64da2b2d0c6a11b494f68da7e8afd0aa38609092cb`

Canonical result reference:

```json
{
  "authority_rule": "authority.content_digest_v1",
  "contract": {
    "id": "fixture_copy.v1",
    "package_digest": "sha256:87e9c905d7c078c00526ae0633523a129b4bd65fa5998ee4aa46dadfb105e06c",
    "version": "1.0.0"
  },
  "locator": "objects/d6631fa3b666c3f252ddda64da2b2d0c6a11b494f68da7e8afd0aa38609092cb",
  "owner_id": "fixture.copy.owner",
  "reference_version": "1.0",
  "root_binding": "fixture_result_root",
  "state": {
    "digest": "sha256:d6631fa3b666c3f252ddda64da2b2d0c6a11b494f68da7e8afd0aa38609092cb",
    "exists": true,
    "head_token": null,
    "length": 16
  }
}
```

Evidence paths for run `copy-execute`, relative to `.phase/runs/copy-execute/`:

The listed `intent.json` and `receipt.json` hashes are captured root-identity-bound evidence from the preserved acceptance root used for this run, not cross-root reproducibility invariants. Recreating the resolved target root intentionally changes the idempotency root identity and its downstream intent/receipt linkage; the effect plan, copied bytes, canonical result, and root-independent attachments remain stable.

- `attachments/effect-plan.json`, `length=1361`, `sha256=3120fcf7816bc61ebfd3caad01fe50da04fe4af940d2ae39ce3b00a1207940d7`
- `attachments/effect-receipts.json`, `length=532`, `sha256=6175ae761e454460a08857a0ea6419745d6aac0fc9aaa80e56a721cc586aec7a`
- `attachments/pre-validator-results.json`, `length=2426`, `sha256=573d6c593a76f64863d032ebc3bf6534c0d80578f498f02c9a32dd598db8046b`
- `attachments/validator-results.json`, `length=2755`, `sha256=ec919f0cd70c465f04ee9714d031f4c050fd0df83630cde8b090991695225dc5`
- `blobs/d6631fa3b666c3f252ddda64da2b2d0c6a11b494f68da7e8afd0aa38609092cb`, `length=16`, `sha256=d6631fa3b666c3f252ddda64da2b2d0c6a11b494f68da7e8afd0aa38609092cb`
- `intent.json`, `length=2677`, `sha256=d23213ceaf844710cb70cd61bc77c4c5a302a96f316a4d0fa2fdb39e1fc693be`
- `receipt.json`, `length=5750`, `sha256=a3de22b3b90efa2389728c155567bf5dea513be6b7b5205bfb9eb809009894be`

## Runtime Path

1. `src/phase_tool/core.py:460` coordinates `PhaseCore.run`: resolve contract, capture candidate, freeze declared inputs, calculate idempotency digests, validate, plan, write intent, call the broker, verify, and write the receipt.
2. `src/phase_tool/planning/__init__.py:174` derives the copy effect from the frozen input digest. The user-provided destination is not used as the final locator.
3. `src/phase_tool/planning/__init__.py:200` validates the static plan shape, root bindings, effect count, effect type, and locator safety before execution.
4. `src/phase_tool/mutation/broker.py:30` and `src/phase_tool/mutation/broker.py:122` reread durable intent and the effect-plan attachment, revalidate the locked plan, load the frozen blob, and dispatch only supported mechanisms.
5. `src/phase_tool/mutation/content_addressed_copy.py:90` enforces content digest, content length, locator-digest binding, safe path containment, exclusive create, readback verification, and no overwrite on conflict.
6. `contracts/fixtures/fixture_copy.v1.json:46` defines `fixture_copy.v1`; `contracts/fixtures/fixture_copy.v1.json:72` binds it to `content_addressed_copy`.

## Acceptance Coverage

The summary records 17 scenarios with command order, exit, terminal status, disposition, mutation flag, blockers, artifacts, source snapshots where applicable, and before/after target trees. It covers validate; plan with no target mutation; execute new text; inspect run and target; exact prior operation reuse; same operation key with different request digest conflict; existing-identical no-prior; existing-different; binary copy; unsafe locator rejection; corrupted frozen blob rejection via controlled Core helper; fixture create; fixture append; task journal; multi-effect execution rejection via controlled Core helper; destination-appears planning; and destination-appears conflict.
