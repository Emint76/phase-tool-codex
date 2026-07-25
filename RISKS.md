# Risks — agent-task-journal

Приоритет: High / Medium / Low. Здесь перечислены существенные риски, обнаруженные в Итерации 0.

## R1. Hash chain может быть переоценена

- **Priority:** High
- **Риск:** SHA-256 chain обнаруживает изменение при наличии trusted head/checkpoint, но пользователь с write access может переписать весь stream и пересчитать hashes.
- **Мера:** явно называть механизм tamper-evident, не tamper-proof; документировать trust boundary; предусмотреть export/head checkpoint; signatures/remote anchoring не включать без отдельного scope.

## R2. Недетерминированная canonicalization

- **Priority:** High
- **Риск:** разные JSON serializers, Unicode/float/newline rules дадут разные event hashes на Windows/Linux.
- **Мера:** ADR с byte-level preimage, domain separation, UTF-8, key ordering, separators и golden vectors на обеих платформах. Запретить floats/`-0.0`/нецелые numbers в v0.1 либо полностью определить numeric serialization; не заявлять JCS без полной реализации стандарта.

## R3. Concurrency и partial append

- **Priority:** High
- **Риск:** два агента одновременно append-ят на один task, stale head создаёт fork; crash оставляет truncated line.
- **Мера:** cross-platform per-task lock, re-read under lock, заранее сериализованный binary record, OS append semantics, short-write handling, file/directory sync где поддерживается, read-back, detection без auto-repair и adversarial concurrency/crash tests. Partial tail после crash остаётся возможным и должен переводить task в `corrupt/unverifiable`.

## R4. Original instruction может быть изменён до core boundary

- **Priority:** High
- **Риск:** shell quoting, adapter preprocessing, newline normalization или platform transport меняют исходный текст до `open`.
- **Мера:** binary stdin/file input до decoding; strict UTF-8/BOM policy; отдельные raw-byte и decoded-text hashes; запрет `.strip()`/normalization; CRLF/LF/BOM/NUL/invalid-UTF-8 vectors на Windows/Linux. Не обещать transport bytes, которых CLI не видел.

## R5. `verify` и lifecycle `task_verify` неоднозначны

- **Priority:** High
- **Риск:** read-only verification и append verification evidence смешиваются; verifier меняет объект, который проверяет; failure невозможно безопасно append-ить в повреждённую chain.
- **Мера:** ADR: `verify` read-only по умолчанию; explicit `--record` завершает полный lifecycle только после successful verification predecessor head, затем проверяет новую запись; failure report остаётся external/non-canonical либо идёт в отдельный trusted stream в будущей версии.

## R6. Correction projected view может скрыть историю

- **Priority:** High
- **Риск:** UI/show применяет correction так, что ошибки, unfinished items или partial outcome исчезают.
- **Мера:** raw view всегда доступен; corrections не удаляют события и не меняют raw terminal transition; projected view показывает original terminal status, amended outcome, superseded chain и reason; no reopen в v0.1.

## R7. Artifact hash TOCTOU и недоступность

- **Priority:** High
- **Риск:** файл меняется во время hashing; path позже отсутствует; symlink указывает на другой target; Windows sharing semantics отличаются.
- **Мера:** stat до/после, streaming hash, явный hash status, regular-file-only policy v0.1, symlink decision. Разделить journal integrity, current external-object check и managed-snapshot verification; исторический hash без snapshot — только point-in-time observation.

## R8. Append-only — не абсолютная filesystem guarantee

- **Priority:** High
- **Риск:** обычный пользователь с правами может редактировать JSONL; backup может быть неполным; network filesystem может нарушать lock/append assumptions.
- **Мера:** честно описать logical append-only и supported local filesystems; verifier; backups/exports; не заявлять WORM/compliance.

## R9. Per-task streams не дают глобальный total order

- **Priority:** Medium
- **Риск:** события разных задач нельзя строго упорядочить только по clocks; timezone offsets не устраняют clock skew.
- **Мера:** гарантировать sequence только внутри task; ADR фиксирует sorting key/tie-breakers и placement corrupt entries, но не объявляет causality; global ledger/anchor рассматривать только при доказанной потребности.

## R10. Idempotency может породить скрытые дубликаты или конфликты

- **Priority:** High
- **Риск:** retry после timeout создаёт второй close/event; слишком слабый key ошибочно объединяет разные события.
- **Мера:** scoped operation ID + canonical request digest; same key/different payload fail; tests для crash-before-response и concurrent retry.

## R11. Schema evolution ломает старые journals

- **Priority:** High
- **Риск:** новый CLI не умеет verify старую schema или интерпретирует старые bytes по новым правилам.
- **Мера:** immutable bundled validators для поддерживаемых versions; hash algorithm version; verifier выбирает schema по event; никогда не мигрирует old events in place.

## R12. Schema validation создаёт ложное чувство Accuracy

- **Priority:** High
- **Риск:** корректная форма и hashes воспринимаются как доказательство истины outcome или факта выполнения.
- **Мера:** documentation boundary: scripted validation доказывает структуру/целостность/наблюдавшийся hash, а не semantic truth; verification status отделить от execution outcome.

## R13. Registry/adapter drift

- **Priority:** Medium
- **Evidence:** live Max registry содержит устаревшие hashes для `knowledge-admission` и `phase-execution-skill`.
- **Риск:** skill обещает workflow, не соответствующий core CLI/schema version.
- **Мера:** adapters versioned в repository; installation checks core version; generated compatibility checks/tests; не делать ручной hash registry единственной гарантией.

## R14. Source workspace Макса не имеет mount-level read-only защиты

- **Priority:** Medium
- **Риск:** ошибочная команда могла бы изменить canonical workspace, хотя discovery разрешает только чтение.
- **Мера:** в Итерации 0 намеренные writes не выполнялись, но отсутствие любых изменений независимо не доказано. В будущем использовать read-only mount/snapshot или before/after manifest/tree hashes и сохранять command transcript.

## R15. crab-control-plane может быть механически скопирован с избыточностью

- **Priority:** Medium
- **Риск:** Phase2/3/4, handoff/package/manifest, wrapper reports и десятки evidence файлов превратят маленький CLI в control plane.
- **Мера:** один candidate-event pipeline и один canonical stream; reuse invariants, не topology/filenames; каждую dependency и layer обосновывать acceptance criterion.

## R16. Cross-platform locking/path behavior

- **Priority:** High
- **Риск:** POSIX locking/mode bits/symlink assumptions не работают на Windows; MSYS path conversion уже продемонстрировал возможность ошибочного пути.
- **Мера:** `pathlib`, native explicit workdir, portable ASCII ID profile с Windows reserved-name/case/normalization tests, filesystem/durability matrix, Windows sharing/reparse и POSIX directory-sync tests; оценить маленькую locking dependency вместо хрупкого самописного решения.

## R17. Sensitive data в исходном поручении и events

- **Priority:** High
- **Риск:** original instruction/errors/artifact paths могут содержать secrets/PII; append-only делает удаление намеренно трудным.
- **Мера:** privacy/security ADR до первой append: data classification, refusal-before-write/explicit confirmation, permissions/ACL, retention/deletion, export redaction, trusted-root и symlink/junction/reparse policy, local writer/admin boundary. Optional redaction означает потерю `Original`; secure deletion не обещается.

## R18. Search/list могут скрыть повреждённую задачу

- **Priority:** High
- **Риск:** parser пропускает corrupt file, и задача исчезает из списка, нарушая Complete/Available.
- **Мера:** scan перечисляет каждый task file; parse/integrity failure отображается как `corrupt/unverifiable`; non-zero/diagnostic; никогда silently skip.

## R19. Lockfile stale recovery может повредить active writer

- **Priority:** Medium
- **Риск:** автоматическое удаление «старого» lock по времени конфликтует с медленной/приостановленной операцией.
- **Мера:** owner metadata, bounded operation, conservative timeout; force-unlock только явной operator action с evidence; решение подтвердить platform tests.

## R20. Dependency compromise / JSON Schema dependency cost

- **Priority:** Medium
- **Риск:** лишние dependencies ухудшают переносимость и supply-chain surface; самописный validator опаснее.
- **Мера:** минимальный dependency set, pinned development lock, package metadata, CI на clean installs, ясное обоснование каждой runtime dependency.

## R21. Rollback/replay/root substitution не обнаруживаются без anchor

- **Priority:** High
- **Риск:** attacker может удалить stream, откатить его до прежнего valid head, скопировать/replay-ить valid stream или подменить journal root; compromised adapter может записать false-but-valid events, а clock может быть spoofed.
- **Мера:** отдельный integrity threat model; explicit trusted-root assumption; optional external head checkpoint/export; journal/task binding в hash preimage; не заявлять detection rollback/deletion без независимого anchor и не считать integrity доказательством semantic truth.

## R22. Prose contract может обещать больше, чем фактический script

- **Priority:** High
- **Evidence:** в изученном Phase runtime frozen-input digest не пересчитывается перед apply, materializer снова читает mutable upstream, late copy может оставить partial result, а rollback остаётся planned-only.
- **Риск:** механическое переиспользование contract wording создаст необоснованные гарантии atomicity, freeze, exhaustive write audit или rollback.
- **Мера:** каждую гарантию agent-task-journal связывать с executable negative tests и конкретной implementation boundary; ADR не считать доказательством; не использовать слова transactional/atomic/rollback без проверенного поведения на Windows и Linux.

## High-risk release gates

`Open` означает, что риск не закрыт документом Итерации 0. Owner здесь — роль/итерация, а не конкретный человек.

| Risk | Disposition | Owner | Required ADR/test | Verification criterion | Release blocking |
|---|---|---|---|---|---|
| R1/R21 | Accept limitation + mitigate | Iteration 1 integrity contract | Threat-model/anchor ADR + rewrite/rollback vectors | Claims match detected and undetected cases | Да для integrity claims |
| R2 | Open | Iteration 1 codec | Canonical-hash ADR + cross-platform golden vectors | Identical bytes/hashes on Windows/Linux | Да |
| R3/R8 | Open | Iteration 1–2 storage | Durability/FS ADR + crash/concurrency matrix | Detect partial tail; no silent success; supported FS explicit | Да |
| R4 | Open | Iteration 1 input contract | Exact-input ADR + CRLF/BOM/NUL/invalid UTF-8 vectors | Boundary and hashes reproducible per input mode | Да |
| R5 | Open | Iteration 1 lifecycle | Verify/task_verify ADR + success/failure vectors | No append into untrusted chain; lifecycle unambiguous | Да |
| R6 | Open | Iteration 1 domain | Correction projection ADR + raw/projected tests | Superseded facts remain visible | Да |
| R7 | Open | Iteration 1–2 artifacts | Artifact-scope ADR + TOCTOU/missing/snapshot tests | Point-in-time/current/snapshot results never conflated | Да для artifact claims |
| R10 | Open | Iteration 1 domain | Idempotency ADR + timeout/concurrent retry tests | Same key/same digest dedupes; mismatch fails | Да для retry-safe claim |
| R11 | Open | Iteration 1 versioning | Compatibility ADR + old-version fixtures | New verifier validates every declared supported version | Да |
| R12 | Open | Iteration 1 lifecycle | Outcome/unfinished schema + negative tests | Partial/errors cannot be omitted or hidden | Да |
| R16 | Open | Iteration 1–2 portability | Portable-ID/path/lock ADR + Windows/Linux/WSL matrix | Reserved/collision/reparse cases fail safely | Да |
| R17 | Open | Iteration 1 security | Privacy/security ADR + refusal/ACL/export tests | No first append before explicit policy acceptance | Да |
| R18 | Open | Iteration 3 projection | Deterministic list/search ordering + corrupt fixtures | Every task file appears or emits explicit diagnostic | Да для list/search release |
| R22 | Ongoing control | Every iteration | Guarantee→implementation→negative-test trace | No normative claim without executable boundary/evidence | Да |

## Открытые вопросы, требующие решения до кода CLI

1. Per-task JSONL окончательно или global ledger?
2. Точный canonical JSON/hash preimage?
3. Lock implementation и поддерживаемые filesystem semantics?
4. Записывает ли `verify` `task_verify`, и когда?
5. Correction folding и post-close допустимые events?
6. Idempotency key format/scope?
7. Artifact symlink/deleted/directory policy?
8. Privacy/secret handling для immutable original instruction?
9. Timezone field: offset, IANA name или оба?
10. Backward compatibility window для schemas?
