# Stage 5 Spec Deviations

This candidate implements `fixture_copy.v1` as a single-effect content-addressed copy/create slice only.

## Versioned Locator Algorithm

For `fixture_copy.v1@1.0.0`, the canonical result locator is:

```text
objects/<lowercase-sha256-hex-of-frozen-payload-bytes>
```

The user-provided destination/name fields remain candidate data for validation and idempotency context, but they do not select the target path. Planning emits exactly one static `copy_blob` effect for the frozen payload digest.

## Publication Boundary

The implementation writes directly to the final digest locator using exclusive create (`O_CREAT|O_EXCL`) plus a full binary write loop, file fsync, and exact readback digest/length verification. It does not use a temp-and-publish sequence.

This is intentionally classified as a partial-visibility mechanism: if a write fails after create, the receipt reports `failed_partial` when the target exists and records the observed bytes written/state. It does not claim multi-effect atomicity, target invisibility during write, or directory-entry fsync on Windows.

## Same-Digest Existing Targets

An existing target with the exact digest and length is verified and succeeds with `bytes_written: 0`. If there is a prior exact verified Phase receipt for the same idempotency binding, Core returns `execution_disposition: reused_existing` with no new effect receipt. Without prior exact Phase reuse, the run is still broker-executed because the mechanism must observe and verify the existing target.

## Multi-Effect Copy

Runtime rejects any plan with more than one effect before mutation. The durable per-effect recovery journal required by the Stage 1 evidence model is not implemented in this Stage 5 slice.

## Durability Claim

The declared policy is `file_data_synced`. Directory-entry durability is best-effort only on non-Windows platforms and is not claimed on Windows.
