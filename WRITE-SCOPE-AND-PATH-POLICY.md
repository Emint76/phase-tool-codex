# Write Scope and Path Policy

Status: Stage 1 normative policy; no path broker exists.

## 1. Claim boundary

A contract-declared allowlist is policy data, not proof of observed filesystem writes. V1's strongest planned claim is:

> All writes performed by the trusted effect broker were resolved and executed through approved root bindings and effect receipts.

This is not an OS-wide write audit. It does not observe writes by adapters, validators that escaped isolation, other processes, administrators, kernel components, malware, or filesystem services.

## 2. Canonical root binding

A writable root is installed/bound outside contract control. Contract data names a `root_binding`; it does not supply an arbitrary absolute path.

Before intent finalization Core records:

- binding ID;
- installation registry/policy digest;
- configured root locator;
- canonical/handle-resolved identity where supported;
- filesystem/device/volume identity;
- local/native versus unsupported remote classification;
- case-sensitivity behavior;
- link/reparse policy;
- observation timestamp.

Contract locator templates and effect locators are relative to the binding.

## 3. Lexical validation

Reject before filesystem access:

- empty path unless root itself is explicitly permitted;
- absolute POSIX path;
- drive-qualified/rooted Windows path;
- UNC/device/extended namespace supplied by contract;
- `.` or `..` segments;
- `/` or `\` ambiguity outside one normalized separator model;
- NUL/control characters;
- alternate data stream separator `:` in Windows components;
- overlong component/path for supported policy;
- invalid Unicode/encoding;
- glob, wildcard, environment expansion, home expansion, or URI interpretation;
- components normalized to empty/`.`/`..`.

Lexical containment is necessary but insufficient.

## 4. Physical containment

Future implementation must resolve path components relative to an already validated root handle/descriptor where the OS permits. It must:

- avoid string concatenation as the security boundary;
- reject or safely bound every symlink/reparse/mount transition;
- verify parent and final object identity at the operation boundary;
- prevent escape through junctions, mount points, hard-link policy, and replaced parent directories;
- use no-follow/descriptor-relative APIs when available;
- compare final resolved volume/filesystem/root identity;
- revalidate after race-sensitive publication/read-back.

`Path.resolve()` followed by a later normal open is not sufficient.

## 5. Traversal

Reject all direct and encoded/normalized traversal variants, including:

- `../x`, `a/../../x`, backslash variants;
- percent/Unicode lookalikes when a preceding layer decodes them;
- trailing separators that alter final-component behavior;
- case/normalization aliases to parent components;
- Windows drive-relative `C:x` and rooted `\x` forms.

Phase Tool must define exactly one decode/normalization order and test pre/post-normalization containment.

## 6. Symlinks and POSIX special files

Default v1 write policy: reject symlinks in any target path component and reject a symlink final target.

Also reject unless a future mechanism explicitly supports and tests them:

- sockets, FIFOs, block/character devices;
- procfs/sysfs-like virtual filesystems;
- mount transitions;
- hard-linked canonical targets where replacement/identity policy cannot be established;
- non-regular final object for file mechanisms.

`bounded_no_follow` may be introduced only with descriptor-relative implementation and tests; it is not implied by the schema enum.

## 7. Windows reparse points and aliases

Default v1: reject reparse points in target root descendants, including junctions and symlink-like tags. The implementation must inspect handles/components rather than rely only on attributes observed before open.

Reject Windows reserved device basenames case-insensitively, with or without extension:

```text
CON PRN AUX NUL
COM1..COM9
LPT1..LPT9
```

Also reject:

- components ending in space or dot;
- colon/alternate data stream syntax;
- device namespaces (`\\.\`, `\\?\`, `\??\`);
- UNC paths supplied by contract;
- names that Win32 normalization aliases to a different component;
- case-fold collisions under the bound filesystem policy.

A contract locator is portable only if it passes the strict common subset or declares a platform-specific result policy outside Core schema.

## 8. Case and Unicode collisions

Before multi-effect mutation, compare all normalized target locators under:

- byte-exact identity;
- installation-declared case behavior;
- Windows invariant case-fold approximation used by tests;
- selected Unicode normalization policy;
- trailing-dot/space normalization;
- reserved-name rules.

Two planned targets that may resolve to one object are a pre-mutation rejection.

The policy must not claim complete Unicode/filesystem equivalence without platform-specific tests.

## 9. Destination replacement

V1 create/copy mechanisms are no-replace:

- exclusive create requires absent destination;
- copy permits absent or contract-approved same-digest existing destination;
- different digest is conflict;
- normal rename/copy APIs that overwrite are forbidden;
- update/replacement is deferred.

Same-digest existing bytes do not prove the current operation created the object. Receipt must distinguish `execution_disposition: reused_existing` from `executed`; a reused outcome has no new effect receipt and must reference exact prior verified evidence.

## 10. Check-to-use race

Unsafe pattern:

```text
resolve/check path
→ attacker or concurrent process replaces parent/final entry
→ normal path-based open/copy
```

Required future boundary:

- bind root/parent handles;
- resolve/open final target relative to trusted handles;
- use OS exclusive/no-replace primitives;
- re-check final handle identity and root containment;
- keep lock/handles across precondition and mutation where applicable;
- treat inability to establish identity as rejection before mutation or `indeterminate` after mutation begins.

Post-copy hash can detect content drift after mutation; it does not prove prevention of destination path substitution.

## 11. Multi-effect preflight

Before first effect:

- validate complete static effect set;
- validate every root/locator/collision;
- verify all frozen inputs;
- classify every destination absent/same/conflict;
- capture expected parent identities/tokens;
- reject unsupported cross-filesystem publication requirements.

Preflight reduces predictable partial apply but cannot guarantee all-effects transaction.

## 12. Target scope versus Core operational scope

The write model has separate, non-interchangeable capabilities:

1. **target roots** — contract-authorized canonical result effects;
2. **run/evidence root** — `intent.json`, `receipt.json`, and required attachments;
3. **frozen blob root** — immutable content-addressed captures;
4. **staging/lock root** — temporary files and lock artifacts needed by a bundled mechanism;
5. **forbidden roots** — explicitly denied regardless of overlap.

The installation boundary resolves these capabilities and their precedence. A target contract cannot redirect an operational root or promote an operational artifact into a canonical result.

The effect broker must account for operational writes as well as target effects. Parent-directory creation, temporary-file creation, lockfile creation, rename/publication, cleanup, metadata change, and evidence publication are not invisible implementation details: each must be enabled by a named bundled mechanism policy, confined to its resolved operational capability, and represented in mechanism/evidence observations. They do not count as target effects for terminal classification.

If cleanup fails, the artifact and blocker are recorded. Cleanup may not erase evidence of a target attempt. Failure to observe operational writes exhaustively limits the claim to broker-mediated actions; it never becomes proof that the process performed no other writes.

## 13. Observed-write evidence

Effect receipts include only broker actions:

- effect ID;
- target root binding and relative locator;
- resolved identity observations;
- attempted operation and byte counts;
- before/after state;
- publication result;
- verification refs;
- error/status.

Allowed wording:

- “broker-observed effects stayed within resolved contract scope”;
- “no out-of-scope broker effect was planned/executed.”

Forbidden wording without an independent OS audit/sandbox:

- “no writes occurred outside scope”;
- “filesystem was unchanged except...”;
- “declared scope proves containment of all process writes.”

## 14. Mandatory future tests

- direct/normalized traversal;
- root binding substitution;
- symlink inserted at every component race point;
- junction/reparse insertion/removal on Windows;
- mount/rename parent race on Linux;
- final destination race;
- reserved names and extensions;
- alternate data streams/device paths/UNC;
- case and Unicode collisions;
- trailing dots/spaces;
- hard-link/special-file targets;
- cross-device publication;
- adapter/validator direct write denied by capability boundary;
- external process write demonstrates claim limitation;
- WSL native versus `/mnt` behavior;
- remote/network filesystem rejected for strong v1 claims.
