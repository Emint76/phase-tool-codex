# ADR: Contract Trust and Installation Registry

- **Status:** Accepted for Stage 1 specification
- **Decision ID:** ADR-CONTRACT-TRUST-REGISTRY
- **Scope:** Phase Tool v1 contract, validator, and mechanism resolution
- **Implementation status:** Specification only

## Context

A contract that names an executable validator or mutation mechanism creates a code-loading trust boundary. Exact IDs alone do not prevent mutable aliases, package substitution, ambiguous resolution, or arbitrary code execution. Contract data must not decide what code is trusted.

## Decision

### 1. Installation-controlled registry

Phase Tool resolves contracts, schemas, validators, policies, and mutation mechanisms from an installation-controlled registry snapshot.

The registry is:

- outside operation contract control;
- immutable for one Phase run;
- captured by digest in `intent.json`;
- populated only by an explicit installation/upgrade action outside operation execution;
- unavailable for runtime self-registration;
- not a routing, package-discovery, or remote plugin marketplace;
- resolved before candidate validation that depends on extensions.

A run MUST NOT mutate registry content or trust roots.

### 2. Exact binding

Every resolvable entry has, at minimum:

```text
kind
id
version
package_digest
artifact_digest or schema_digest
capabilities
trust_root_id
publisher identity/reference
installation state
```

Contracts bind:

- exact `id`;
- exact semantic `version`;
- exact SHA-256 `package_digest`;
- required capability class.

Version ranges are permitted only for declaring Core compatibility, never for selecting a validator or mechanism implementation at execution time.

A name-only, version-only, latest, floating tag, mutable path, or PATH lookup is invalid.

### 3. Trust roots

Trust roots are installation policy. They may be:

- Phase release bundle digests pinned by the installer;
- explicitly imported publisher signing keys with pinned identity and algorithm policy;
- an installation-local allowlist of exact package digests.

A signature without a configured trusted key and verification policy does not create trust. Digest equality proves byte identity, not publisher authority or code safety.

The registry snapshot records which trust root admitted each entry. Unknown, disabled, expired/revoked according to installation policy, or unverifiable trust roots cause fail-closed rejection.

Stage 1 does not define remote trust discovery, transparency logs, certificate PKI, revocation services, or automatic updates.

### 4. Bundled mutation mechanisms

Phase Tool v1 allows target mutation only through release-bundled mechanisms:

- exclusive create;
- expected-head append under lock;
- content-addressed copy/create.

They are part of the Core trusted computing base and are bound by exact release/package digest. CAS update is deferred and not a v1 mutation capability.

The registry may describe bundled mechanisms, but cannot replace their implementation with a third-party package under the same ID.

### 5. Read-only validator extensions

Optional third-party validators may be considered only when a future implementation provides a specified read-only worker/sandbox boundary. Such a validator:

- receives immutable values/frozen references;
- receives no target write handle;
- has no effect-broker capability;
- has bounded CPU/time/memory/output;
- has network disabled unless a separate future ADR explicitly permits it;
- returns only a schema-valid validator result;
- cannot load another extension;
- cannot alter registry/trust configuration.

Registration is not isolation. Until the worker boundary and negative tests exist, only release-bundled validators are trusted for execution.

### 6. Third-party mutation executors

Third-party mutation executors are prohibited in v1.

A contract that requests a non-bundled mutation mechanism, executable adapter, shell command, script, import path, executable URI, or free-form command is rejected before mutation.

### 7. Contract content prohibition

An operation contract MUST NOT contain:

- shell commands or shell fragments;
- executable/import/module/class paths;
- arbitrary filesystem paths to executables;
- PATH-resolved program names;
- package-manager coordinates that trigger installation;
- remote executable URLs;
- prompts treated as trusted validators;
- embedded executable bytecode/source;
- registry administration instructions;
- credentials, tokens, or connection strings.

Schema references and declarative configuration are allowed only when their digests and registered owners are resolved through the trusted snapshot. Validator configuration is restricted to inert policy identifiers and bounded scalar parameters; it cannot provide a path, import, command, or entry point.

Contract identity inside the declarative document contains ID, version, and Core compatibility. It does **not** contain its own package digest: a digest covering the contract file would otherwise be self-referential. The installation registry binds `(ID, version)` to the exact package digest, and resolution records that external exact binding in `intent.json` and `receipt.json`.

## Resolution algorithm

For every contract/validator/mechanism reference:

1. Load one immutable registry snapshot.
2. Select entries matching exact kind, ID, version, package digest, and required capability.
3. Require exactly one match.
4. Verify artifact bytes against the recorded digest.
5. Verify admission by an enabled installation trust root.
6. Verify Core compatibility and capability policy.
7. Record registry-snapshot digest and resolved entry digests in intent.
8. Reject before mutation on any discrepancy.

No fallback to another version, alias, PATH entry, remote package, or best-effort mode is allowed.

## Required rejection behavior

| Condition | Required result |
|---|---|
| Zero exact matches | `rejected`, code `registry.entry_not_found` |
| More than one exact match | `rejected`, code `registry.entry_ambiguous` |
| Mutable/floating alias | `rejected`, code `registry.mutable_reference` |
| Package/artifact digest mismatch | `rejected`, code `registry.digest_mismatch` |
| Unknown/disabled trust root | `rejected`, code `registry.untrusted` |
| Capability mismatch | `rejected`, code `registry.capability_mismatch` |
| Unsupported Core compatibility | `rejected`, code `contract.core_incompatible` |
| Third-party mutation mechanism | `rejected`, code `mechanism.third_party_mutation_forbidden` |
| Validator isolation unavailable | `rejected`, code `validator.isolation_unavailable` |
| Registry changes after intent snapshot | `rejected` before mutation, or `indeterminate` if detected after mutation began |

All rejection receipts use non-zero exit status. Before mutation, no canonical domain result may be claimed.

## Registry ownership and administration

Registry installation, upgrade, removal, publisher admission, and trust-root management are explicitly outside Phase Core operation execution. They belong to installer/administrator tooling governed by a future separate specification.

Core may read and verify a registry snapshot. It must not expose contract-driven registry CRUD, dependency solving, marketplace search, update scheduling, or automatic network retrieval.

## Evidence

`intent.json` must record:

- registry snapshot digest;
- contract entry ID/version/package digest;
- every validator entry ID/version/package digest/trust-root ID;
- mechanism ID/version/package digest/trust-root ID;
- Core version and package digest;
- resolution timestamp.

`receipt.json` records resolution outcome and any mismatch code, but need not duplicate full packages.

## Future implementation boundaries and tests

| Claim | Boundary | Mandatory negative tests |
|---|---|---|
| Exact resolution | registry resolver | same ID/version with two digests; wrong digest; missing entry |
| Snapshot immutability | captured registry bytes/digest | registry replaced between plan and execute |
| Trust admission | installer trust store + verifier | unknown key; disabled root; valid signature from untrusted key |
| Validator read-only | worker/sandbox capability boundary | filesystem/network/process/effect-broker attempts denied |
| Bundled mutation only | broker + release manifest | contract requests third-party mutation executor |
| No arbitrary code in contract | contract schema + semantic scanner | shell/import/path/URL payloads rejected |

## Consequences

- v1 has a deliberately narrow extension model.
- Operation contracts remain portable declarative data but require installed trusted dependencies.
- Package digest pinning improves reproducibility but does not by itself prove safety.
- Registry administration cannot turn Core into a plugin control plane.
