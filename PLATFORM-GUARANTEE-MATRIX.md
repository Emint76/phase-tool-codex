# Platform Guarantee Matrix

Status: Stage 1 planning matrix. Every guarantee is provisional until the named implementation boundary and executable platform test exist.

## 1. Platforms in scope

- Windows 10/11 on tested local NTFS configurations;
- native Linux on tested local filesystems;
- WSL on its native Linux filesystem, tested separately;
- WSL paths backed by Windows (`/mnt/...`) are a separate compatibility class.

Out of scope for strong v1 guarantees:

- SMB/NFS/CIFS/SSHFS/FUSE/cloud-synced/cluster filesystems;
- removable/unreliable media without explicit qualification;
- remote object stores;
- containers/VM shared mounts unless separately tested;
- filesystems with unknown sync/locking/case/link semantics.

## 2. Matrix

| Capability | Windows boundary | Linux/WSL-native boundary | Claim before tests | Mandatory future tests |
|---|---|---|---|---|
| Root/path identity | Handle-based final path, volume/file identity, reparse inspection | `openat`/descriptor-relative resolution, device/inode/mount policy | No strong claim | root/parent replacement; volume/device change |
| Advisory/exclusive locking | `LockFileEx`/tested handle sharing model | `flock` or `fcntl` selected consistently | Cooperating-writer serialization only | two processes; crash/abandon; non-cooperating writer |
| Atomic exclusive create | `CreateFile(..., CREATE_NEW, ...)` | `openat(..., O_CREAT|O_EXCL, ...)` | Destination race decided by OS create only | simultaneous create; reparse/symlink final; crash |
| Append serialization | lock + expected-head revalidation + binary `WriteFile` loop | lock + expected-head + binary write loop, optionally `O_APPEND` | No crash-atomic record claim | concurrent writers; stale head; short write; kill points |
| File data flush | `FlushFileBuffers` on file handle | `fsync`/selected `fdatasync` policy | Data-flush attempt only on qualified FS | power/crash harness or strongest practical process/VM tests |
| Directory entry durability | No portable general guarantee identified; mechanism-specific qualification required | directory `fsync` after create/rename on supporting local FS | Unsupported unless separately proven | create/publish crash tests per filesystem |
| No-replace publication | `CREATE_NEW`; temp publication needs tested hard-link/rename alternative without replacement | `linkat` or `renameat2(RENAME_NOREPLACE)` where available; fallback explicit | No generic atomic publication claim | destination race; same/cross filesystem; crash |
| Rename/replacement | `MoveFileEx`/`ReplaceFile` semantics vary and may replace; update deferred | `rename` replaces; `renameat2` availability varies | Replacement forbidden in v1 | ensure normal replace path rejected |
| Symlink handling | handle/reparse-tag checks; default reject | no-follow descriptor APIs; default reject | Lexical check alone insufficient | insertion/removal race every component |
| Junction/reparse handling | default reject descendants/final reparse points | not applicable in same form; mount/symlink separate | No bounded-follow claim | junction/mount substitution |
| Case behavior | NTFS commonly case-insensitive but per-directory options exist | usually case-sensitive; filesystem-dependent | Installation-observed policy only | case collision and per-directory behavior |
| Reserved names | Win32 device names, ADS, trailing dot/space, namespace prefixes rejected | Windows names may be legal but strict portable subset may reject | Strict portable policy | each reserved alias/extension |
| Unicode normalization | Win32/filesystem behavior varies | filesystem generally byte-oriented; applications vary | No canonical equivalence claim | composed/decomposed/case variants |
| Path length | API/manifest-dependent, long-path configuration varies | filesystem/API limits vary | Enforce configured tested maximum | boundary lengths/components |
| Sparse/compressed/encrypted files | NTFS metadata semantics not preserved by byte copy unless specified | filesystem metadata semantics vary | Content bytes only | byte digest plus metadata non-claim |
| Hard links | file identity/ownership ambiguity; default reject for canonical target where unsafe | inode aliases; default reject where unsafe | No uniqueness claim | hard-link target substitution |
| Special files | devices/pipes rejected | device/FIFO/socket rejected | regular files only | each special type |
| WSL `/mnt` | Windows-backed semantics exposed through WSL layer | not equivalent to native Linux | Unsupported for strong v1 durability/locking until qualified | same suite on `/mnt` versus native ext4 |
| Network/remote FS | Semantics provider-dependent | semantics provider-dependent | Explicitly unsupported | rejection/classification test only |

## 3. Locking guarantees

A successful future lock test may establish only:

- processes using the same Phase lock provider/scope serialize;
- expected state is recomputed while lock is held;
- abandoned/crashed lock behavior is understood for the platform.

It does not establish:

- administrator exclusion;
- distributed locking;
- exclusion of non-cooperating opens/writes;
- durability;
- target path identity without handle/path controls.

## 4. Atomic create guarantees

The implementation boundary must combine:

- validated root/parent handle;
- no-follow/reparse policy;
- OS exclusive create primitive;
- content write/read-back;
- selected flush policy;
- final identity/digest verification.

Exclusive name creation does not make subsequent content write crash-atomic. A created partial file is `failed_partial` unless removed before canonical visibility by a tested publication design.

## 5. Append guarantees

A future qualified append mechanism may claim:

- cooperating-writer serialization;
- stale-head rejection before write;
- short-write handling;
- resulting record/head read-back;
- detection of invalid/torn tail.

It may not claim:

- indivisible crash-atomic record append;
- WORM/immutability;
- non-cooperating-writer exclusion;
- directory durability from file flush;
- identical behavior on remote/shared filesystems.

## 6. Flush and durability terminology

- **write completed:** OS API accepted bytes; not durable.
- **read-back verified:** subsequent read returned expected bytes; may still be cache-resident.
- **file data synced:** `fsync`/`FlushFileBuffers` returned success on a qualified boundary.
- **directory entry synced:** containing directory publication persistence was exercised through a tested platform method.
- **power-loss durable:** requires a dedicated hardware/VM/filesystem crash protocol; not claimed by ordinary unit tests.

Receipt records the attempted policy and result, not a stronger generic word “durable.”

## 7. Test environments to record

Every future platform result records:

- OS/kernel/build;
- Python/runtime version;
- filesystem type/version/mount/options;
- native/WSL/container/VM context;
- local versus shared/remote classification;
- drive/volume identity;
- long-path/case configuration;
- mechanism and test package digests;
- fault-injection method;
- exact passed/skipped/unsupported cases.

## 8. Stage 2 blocking qualification plan

Before mutation implementation begins, Stage 2 needs test designs for:

1. Windows exclusive create/path/reparse race;
2. Linux descriptor-relative no-follow path walk;
3. lock/crash behavior on both;
4. short/torn append fault injection;
5. temp/publish no-replace mechanism or an explicit weaker partial-visibility model;
6. file versus directory sync semantics;
7. WSL-native and `/mnt` separation;
8. unsupported filesystem detection/refusal;
9. result committed while evidence finalization fails;
10. cleanup that never deletes pre-existing same-hash objects.

Until those boundaries exist, Stage 1 schemas describe intended evidence/status, not implemented guarantees.
