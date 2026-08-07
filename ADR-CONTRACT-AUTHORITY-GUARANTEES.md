# ADR: Contract Authority Guarantee Admission

Status: Accepted for Loop 5

## Context

An exact mutation mechanism identity is necessary but not sufficient to admit a transition. The same mechanism can be installed behind platform authorities with materially different path, concurrency, verification, and durability properties. A provider must not be able to admit itself merely by reporting a stronger profile.

Loop 4 already binds the exact contract package, mechanism, authority provider/profile, and effect-plan digest in transition evidence. Loop 5 adds an admission decision before candidate capture and preserves the exact Loop 4 package generations for inspection.

## Decision

### Contract requirements

Every current contract declares `operation.required_guarantees`:

- `vocabulary` binds the exact guarantee vocabulary ID, version, and descriptor digest;
- each `mechanisms` entry binds one exact mechanism ID, version, and package digest;
- `all_of` names technology-neutral guarantees required from the authority used by that mechanism.

Requirements select neither an operating system nor a provider. Per-mechanism requirements are mandatory because one contract can authorize several mechanisms with different authority usage.

A mechanism-managed mechanism, currently expected-head append, declares an empty `all_of`. It does not consult `AuthorityProvider` and cannot borrow provider guarantees.

### Installation trust boundary

`Installation.authority_profile_binding` is trusted configuration selected at the composition boundary. `AuthorityProvider.guarantee_profile_binding()` is only a consistency report. For provider-backed mechanisms, Core requires exact equality between configured and reported bindings before coverage resolution.

The installation also qualifies every declared target root before capture. The bundled v1 policy admits POSIX production only on non-WSL Linux roots identified as `ext4` or `overlay`, and Windows compatibility only on fixed volumes identified as NTFS. Other hosts, volume classes, and filesystem types fail closed with `guarantee.profile_scope_unsupported`.

The registry then resolves the exact profile descriptor and verifies its bound implementation identity and artifact digest. Unknown vocabulary/profile versions, digest disagreement, unknown guarantees, incomplete/duplicate/extra mechanism mappings, provider disagreement, and insufficient profile coverage fail closed.

### Lifecycle ordering

The lifecycle is:

```text
resolve exact contract generation
→ verify target-root qualification and contract requirements against the exact installation profile
→ capture
→ freeze
→ validate
→ plan
→ reverify the actual plan mechanism closure
→ persist intent
→ broker/mutate
```

Admission failure persists an exact contract-bound rejected receipt. It creates no plan, intent, progress, attachments, blobs, broker call, or mutation. Operational evidence roots and locks may exist as empty infrastructure.

### Evidence and inspection

Requirements are not duplicated into implementation binding. The exact contract package digest already binds their bytes; implementation binding already binds the exact profile/provider/mechanism and effect-plan digest. Avoiding duplicated mutable interpretation prevents two nominal sources of truth.

Inspection independently resolves the exact contract and profile descriptors and repeats coverage validation for current generations. Historical Loop 4 contracts have no `required_guarantees`; their exact archived package and schema bytes remain resolvable and retain their historical validation semantics.

### Platform semantics

- POSIX production profile advertises only executable guarantees established by the POSIX authority implementation and its platform tests.
- Windows remains an explicit compatibility profile. It admits contracts whose minimum requirements it actually covers, such as the baseline exclusive-create fixture, and rejects stronger namespace/durability requirements before capture.
- Descriptor text alone is not proof. Claims remain bounded by executable platform evidence and filesystem qualification.

## Consequences

- Contract/package digests change and require a new current generation.
- Loop 4 contract and phase-contract schema bytes are archived as immutable historical resources.
- Registry invariants require exactly one current generation for each exact contract binding and schema reference.
- Adding a guarantee requires a new versioned vocabulary descriptor and executable profile evidence.
- Adding or changing mechanism requirements changes the exact contract package and cannot be hidden behind provider selection.
