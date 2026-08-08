# Platform Guarantee Matrix

Status: Loop 5 executable admission matrix. This document separates guarantees admitted by the current exact profiles from unimplemented qualification work. Filesystem scope bounds every claim.

## 1. Platforms in scope

Current executable profiles cover:

- native Linux, plus Linux containers whose process root is identified as `overlay`, using the bundled POSIX authority implementation on qualified `ext4` or `overlay` target-root scope;
- Windows 10/11 using the bundled Windows compatibility authority implementation on tested local NTFS configurations.

Out of scope for strong guarantees unless separately qualified:

- SMB, NFS, CIFS, SSHFS, FUSE, cloud-synced and cluster filesystems;
- removable or unreliable media;
- WSL-native and WSL `/mnt` filesystems until separately qualified; marker files alone do not establish a container boundary, while an `overlay` process root does;
- remote object stores;
- power-loss durability beyond an explicitly named crash protocol.

## 2. Admission profiles

Contracts express technology-neutral minimum requirements through the exact, versioned guarantee vocabulary. Core compares each exact mechanism requirement with the trusted installation-selected profile before candidate capture. The provider reports its profile only for consistency checking; it cannot select installation policy.

| Exact profile | Classification | Qualified root scope | Admitted guarantees | Explicitly not admitted |
|---|---|---|---|---|
| `phase.posix.authority.v1@1.0.0` | production | Linux roots identified as `ext4` or `overlay` | `exclusive_create`, `readback_verification`, `cross_process_serialization`, `namespace_bound_mutation`, `atomic_replace`, `namespace_metadata_flush_attempted` | power-loss durability, distributed locking, non-cooperating-writer exclusion, automatic process-crash recovery |
| `phase.windows.authority.v1@1.0.0` | compatibility | Windows roots on fixed volumes identified as NTFS | `exclusive_create`, `readback_verification`, `cross_process_serialization` | `namespace_bound_mutation`, `atomic_replace`, `namespace_metadata_flush_attempted`, process-crash recovery |

A contract requiring a guarantee outside the selected profile, a missing/symlink-resolved root, or a root outside the profile's qualified filesystem scope is rejected before capture, including mechanism-managed operations. Intent binds each resolved root identity. Broker execution rejects custom reparse-detector and write-primitive callbacks, revalidates roots after the remaining callbacks, and requires each opened root handle to match the intent-bound device/volume and inode/file identity before leaf creation or open. Mechanism-managed append uses this pinned-root identity check without claiming provider-backed guarantees.

## 3. Current implementation boundaries

| Capability | Windows compatibility boundary | POSIX production boundary | Current claim |
|---|---|---|---|
| Parent traversal | Opens each directory with `CreateFileW(..., FILE_FLAG_OPEN_REPARSE_POINT)` and rejects reparse points, but leaf operations remain pathname-based | Walks with `openat`-style `dir_fd`, `O_DIRECTORY` and `O_NOFOLLOW`; retains parent descriptors and checks recorded device/inode bindings | Only POSIX admits `namespace_bound_mutation`; Windows does not claim parent-rebinding detection |
| Cooperating-writer lock | `Local\phase-tool-effect-<digest>` named mutex derived from root identity and scope | `flock(LOCK_EX)` on the opened root directory descriptor | Cross-process serialization for cooperating writers on the same host; Windows scope is the same logon/session namespace, not a machine-global or distributed lock |
| Exclusive create | `CreateFileW(..., CREATE_NEW, ...)`, reparse/special-file checks, binary descriptor | `os.open(..., O_CREAT|O_EXCL|O_NOFOLLOW, dir_fd=parent_fd)` | Existing destination is never replaced by the create operation |
| Read-back | Reads through the opened leaf descriptor and recomputes digest/length | Reads through an `O_NOFOLLOW` descriptor relative to pinned parent | Verified bytes may still be cache-resident; this is not durability |
| Replacement | No admitted replacement guarantee | `os.replace(..., src_dir_fd=..., dst_dir_fd=...)` under pinned parents | Only POSIX admits atomic replacement visibility |
| Namespace metadata flush | No implementation/profile claim | `fsync` on the pinned parent directory descriptor | Attempted namespace metadata flush only; no generic power-loss claim |
| Reparse/symlink policy | Rejects traversed and final reparse points/symlinks | Rejects symlinks via no-follow descriptor operations and identity checks | No bounded-follow mode |
| Append | `mechanism.expected_head_append_v1` owns its locking and head protocol; it does not call `AuthorityProvider` | Same mechanism-managed boundary | No authority-profile guarantee is claimed by append |

## 4. Exact guarantee meanings

- **`exclusive_create`:** the leaf create operation succeeds only when the name is absent and never replaces an existing target.
- **`readback_verification`:** resulting bytes are read and matched to the expected digest/length.
- **`cross_process_serialization`:** cooperating Phase processes using the same provider and scope serialize; this excludes distributed and non-cooperating writers.
- **`namespace_bound_mutation`:** target operations use pinned parent descriptors and detect parent identity rebinding within the implementation boundary.
- **`atomic_replace`:** observers see the old or new complete leaf at the replacement operation, not an intentionally exposed missing/partial intermediate.
- **`namespace_metadata_flush_attempted`:** the implementation invokes the supported parent-directory metadata flush and propagates failure.

These definitions come from the digest-bound `phase.mutation-guarantees@1.0.0` descriptor. Contract prose cannot strengthen them.

## 5. Locking and append limits

Current authority locks establish only cooperating-writer serialization at their named scope. They do not establish:

- administrator or non-cooperating-process exclusion;
- distributed locking;
- durability;
- Windows machine-global serialization across sessions;
- target namespace identity unless the selected profile separately admits it.

The append mechanism separately performs expected-head revalidation and read-back. It does not claim indivisible crash-atomic records, WORM semantics, or exclusion of direct external writes.

## 6. Flush and durability terminology

- **write completed:** the OS API accepted bytes; not durable;
- **read-back verified:** a subsequent read returned expected bytes; it may still be cache-resident;
- **file data synced:** the selected file sync primitive returned success on a qualified boundary;
- **namespace metadata flush attempted:** the POSIX parent-directory `fsync` call returned success;
- **power-loss durable:** requires a dedicated hardware/VM/filesystem crash protocol and is not claimed by either v1 profile.

Receipts record attempted mechanisms and observations, not a stronger generic word “durable.”

## 7. Executable evidence

Profile claims are backed by the platform-specific suites:

- `tests/mutation/common/test_guarantee_profiles.py` — descriptor, digest and implementation binding integrity;
- `tests/mutation/common/test_guarantee_requirements.py` — contract admission, negative matrix and pre-capture rejection;
- `tests/mutation/common/test_authority_provider_boundary.py` — trusted provider boundary;
- `tests/mutation/posix/test_authority_conformance.py` and `test_guarantee_conformance.py` — POSIX authority and stronger guarantees;
- `tests/mutation/windows/test_authority_conformance.py` — Windows compatibility guarantees and explicit non-claims.

The final CI split runs POSIX production and Windows compatibility as independent required jobs without `continue-on-error`.

## 8. Remaining qualification work

The following remain future work and do not strengthen current profile claims:

1. power-loss/crash harnesses by filesystem and mount options;
2. Windows machine-global or cross-session locking, if required;
3. Windows handle-relative namespace mutation and rebinding detection;
4. Windows atomic replacement and directory metadata flush qualification;
5. WSL-native versus `/mnt` qualification;
6. explicit unsupported-filesystem detection beyond the current documented scope;
7. remote/distributed filesystem semantics;
8. non-cooperating writer and administrator threat models.
