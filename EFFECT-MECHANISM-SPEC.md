# Effect Mechanism Specification

Status: Stage 1 design for future release-bundled trusted mechanisms. No mechanism is implemented here.

## 1. Shared effect boundary

V1 mechanisms:

- `exclusive_create`;
- `expected-head append under lock` (`append_record`; `correction` is a semantic contract intent using this same primitive);
- `content-addressed copy/create` (`copy_blob`).

CAS update is deferred design only and is absent from the v1 effect-plan schema.

Every mechanism:

1. is release-bundled and exact-digest bound;
2. receives a complete static effect and frozen inputs;
3. resolves only installation-bound roots;
4. applies write-scope/path policy;
5. performs no domain validation;
6. records before/after observations and byte counts;
7. performs immediate post-verification;
8. returns an effect receipt;
9. never invokes another contract/mechanism;
10. never expands the plan after mutation begins.

## 2. Exclusive create

### Inputs

- target root binding and relative locator;
- pre-serialized content bytes/digest/length;
- `existence: absent` precondition;
- path/symlink/reparse policy;
- durability policy;
- effect/run IDs.

### Preconditions

- canonical root binding is valid;
- every parent component passes containment and no-follow policy;
- final destination is absent under race-resistant create boundary;
- full content bytes are frozen/value-snapshotted;
- no replacement/overwrite is allowed;
- plan is complete and broker-authorized.

### Concurrency token

Destination non-existence plus directory/parent identity. No separate application token is required, but exclusive OS creation must decide the race.

### Intended implementation boundary

- POSIX/Linux: descriptor-relative `openat`/equivalent with `O_CREAT|O_EXCL`, safe parent resolution, and no-follow controls where available.
- Windows: `CreateFile` with `CREATE_NEW`, handle-based final-path/reparse validation, and sharing flags chosen/tested for exclusive creation.

Lexical `exists()` then normal `open()` is not sufficient.

### Durability

Possible declared levels:

- bytes written/read back only;
- file data flushed (`fsync`/`FlushFileBuffers`);
- file plus containing-directory entry durability where a tested platform method exists.

No cross-platform directory durability claim is implied.

### Partial states

- destination absent: `failed_no_effect` if verified;
- destination exists with zero/partial bytes after write failure: `failed_partial`;
- full bytes present but read-back/evidence failed: `committed_unverified`;
- state unreadable after crash: `indeterminate`.

### Idempotency

A later same-key same-digest request may return prior verified result. A destination that merely has the same bytes without matching durable intent is `adopted_existing` only if the contract explicitly permits it; it is not claimed as created by this run.

### Post-verification

- target identity/locator;
- exact digest and length;
- no replacement occurred;
- expected schema/state predicate;
- result reference and effect receipt agree.

## 3. Expected-head append under lock

### Inputs

- target root/relative locator;
- pre-serialized one-record bytes/digest/length;
- expected head token and concurrency token;
- lock scope/provider;
- record-boundary/tail validator;
- durability policy.

### Preconditions

- target exists and is a regular supported object;
- stream validates through expected head;
- no invalid/truncated tail exists;
- expected head/length/digest equals state recomputed under lock;
- record bytes are complete before opening write path;
- idempotency key is absent or matches an existing verified record.

### Lock boundary

Lock is acquired before final state revalidation and held through write, flush/read-back, and resulting-head computation.

Locks serialize only cooperating processes using the identical provider/scope. Core MUST NOT claim exclusion of administrators, non-cooperating writers, or remote clients.

### Write boundary

- use a write loop that handles short writes;
- do not use text-mode I/O;
- do not split one logical record intentionally;
- record exact offset and bytes written;
- flush/sync according to policy;
- read back from expected offset and verify full record/new head.

`O_APPEND` or one `WriteFile` call does not alone guarantee crash-atomic record append. A torn tail remains possible and must be detected.

### Partial states

- stale head rejected under lock: `failed_no_effect`;
- zero bytes written and unchanged target verified: `failed_no_effect`;
- some bytes written/truncated tail: `failed_partial`;
- full record present but post-verification/evidence failed: `committed_unverified`;
- state unavailable/changed by non-cooperating writer: `indeterminate`.

### Idempotency

Record format must bind stable operation ID and request digest or provide equivalent canonical lookup. Same ID/digest/exact record returns existing result; same ID/different digest is conflict.

### Platform tests

- native Windows LockFileEx/handle behavior;
- native Linux advisory lock behavior;
- concurrent processes;
- crash/kill at every write/sync/read-back point;
- WSL native filesystem and `/mnt` separately;
- short-write fault injection;
- stale lock/abandoned process behavior.

## 4. Content-addressed copy/create

### Inputs

- frozen blob binding/digest/length;
- destination root/relative locator;
- `absent_or_same_digest` precondition;
- static finite effect set;
- durability/path policy;
- idempotency key/request digest.

### Preconditions

- operation reads only the frozen blob, not mutable upstream;
- blob digest/length verify immediately before copy;
- all effects and destinations are preflighted before first mutation;
- no destination replacement is permitted;
- same-hash existing object handling is contract-declared;
- different-hash destination is conflict;
- multi-effect atomicity is not claimed.

### Intended publication boundary

Preferred implementation:

1. create Core-owned temporary file in the destination filesystem/directory scope;
2. write frozen bytes with short-write handling;
3. flush and read-back verify temp;
4. publish without replacement using a tested platform primitive;
5. verify destination identity/digest/length;
6. clean up temp where safe.

If no tested atomic no-replace publication primitive exists, implementation must expose possible partial visibility and classify failures truthfully. Normal rename that replaces an existing destination is forbidden.

### Concurrency token

Destination absence or exact same digest, plus parent identity. The OS no-replace publication decides the destination race; earlier `exists()` is only preflight.

### Partial states

Single effect:

- temp-only failure, canonical destination absent: `failed_no_effect`;
- canonical destination partially created/visible: `failed_partial`;
- full destination present but verification/evidence failed: `committed_unverified`;
- destination race leaves unknown identity: `indeterminate`.

Multi-effect:

- earlier verified destinations remain after a later failure;
- aggregate status `failed_partial`;
- no automatic deletion/rollback;
- before each effect, a durable `attempt_started` journal entry is required;
- after observation, a durable `observation_recorded` entry is required before the next effect;
- effect receipts identify applied/not-attempted items;
- without the implemented and crash-tested effect-journal protocol, plans with more than one effect must be rejected before mutation.

### Idempotency

- same key + same request digest + verified receipt: return existing;
- same-hash existing with contract permission: return `execution_disposition: reused_existing`, no effect receipt and no write;
- different hash: conflict before mutation;
- previous partial/indeterminate: inspect all declared destinations before retry.

### Post-verification

- destination exact digest/length;
- result locator under canonical root;
- publication did not replace another object;
- all required effects have receipts;
- aggregate result matches static plan.

## 5. Correction intent

`correction` is semantic intent represented mechanically by the ordinary `append_record` primitive (or, in a future separately approved contract, another already trusted bounded primitive). The contract defines relation/reason/projection rules. Core has no `append_correction` executor and only enforces the selected primitive's generic concurrency/durability rules. No prior bytes may be rewritten by the v1 append mechanism.

## 6. Deferred CAS update

Not a v1 mechanism. Future design would require:

- exact before digest/version token;
- frozen full replacement bytes;
- race-resistant compare-and-swap publication;
- before-image retention policy;
- post-update verification;
- partial/crash recovery;
- Windows/Linux replacement semantics;
- two mutation-bearing use cases and separate approved ADR.

The Stage 1 v1 contract and effect-plan schemas intentionally reject `update` and `compare_and_swap_replace`. A future approved schema version may represent CAS only after the stated proof obligations are met.

## 7. Mandatory future conformance

- complete-plan validation before mutation;
- target traversal/link/reparse/path races;
- wrong mechanism digest/untrusted mechanism;
- short/torn writes;
- stale head and concurrent append;
- source blob mutation/tampering;
- destination absent/same hash/different hash;
- destination creation race;
- multi-effect failure after each effect index;
- crash before/after publication and sync;
- post-verification/evidence finalization failure;
- truthful mapping to every terminal status.
