# Reuse Map — Phase → agent-task-journal

Цель карты — переиспользовать проверяемые идеи, а не механически копировать admission stack.

## Карта механизмов

| Phase concept | Task-journal equivalent | Решение | Причина |
|---|---|---|---|
| Candidate | Candidate event, собранный CLI/adapter до записи | **Adapt** | Полезно отделить пользовательский/агентский input от canonical event; отдельный package tree не нужен. |
| Validation | JSON Schema + domain/state validation + path/artifact checks | **Reuse directly (principle)** | Fail-closed validation до mutation — базовая гарантия. Реализовать проще в одном Python pipeline. |
| Controlled apply | Controlled append под lock с replay последнего состояния, hash calculation, binary append, `fsync` и read-back | **Adapt** | Apply здесь — одна логическая append operation, а не копирование package в KB. Crash может оставить detectable partial tail; абсолютная atomicity не заявляется. |
| Evidence | Сами execution events: artifacts, hashes, errors, unfinished items, outcome; successful recorded verification event | **Adapt** | Не нужен отдельный громоздкий evidence run tree для каждого события. Integrity-verification failure для повреждённой chain остаётся external/non-canonical, пока нет отдельного trusted stream. |
| Manifest | Event envelope и artifact array | **Reject as separate artifact** | Для одной event append отдельный manifest дублирует данные. Manifest возможен только для batch import/export в будущем. |
| Hash verification | SHA-256 event preimage и previous hash chain; artifact checks с явным scope | **Reuse directly (principle)** | Journal integrity детерминирована; historical artifact hash — point-in-time observation, если journal не владеет snapshot. Canonicalization версионируется. |
| Canonical promotion | Valid event append в task stream | **Adapt** | Это validation/ownership boundary, но не обещание общей transactional atomicity; torn tail остаётся invalid/corrupt. |
| Rollback | Нет rollback canonical history; correction/amendment/supersedes event | **Reject for history; adapt for operation failure** | Удаление старой записи нарушит append-only. Crash может физически оставить partial tail; verifier обязан считать его corruption, а не event. |
| Registry | Bundled schema-version registry / code mapping | **Adapt minimally** | Нужен dispatch по `schema_version`; внешний mutable registry не нужен в v0.1 и подвержен drift. |
| Router | Agent adapter решает, является ли поручение journal-worthy; core CLI не маршрутизирует знания | **Adapt only in adapters** | Core принимает явные команды. Сложный admission router не относится к task lifecycle. |
| Immutable history | Никогда не редактировать ранее записанные bytes; только append | **Reuse directly** | Основной enduring/complete инвариант. OS-level WORM не заявляется. |
| Correction | Новый `correction`/`amendment` event с `supersedes_event_id` и reason | **Adapt** | Сохраняет историю. Требуется чёткая projected-view семантика в ADR. |
| Idempotency | Stable operation/event id или idempotency key; same key+same payload → existing event, mismatch → fail | **Adapt** | Нужна retry safety для CLI/agents. Нельзя путать с «destination already has same hash». |
| Deterministic verification | Replay bytes line-by-line: decode/schema/hash/prev hash/sequence/state/artifacts | **Reuse directly (principle)** | Verifier не должен зависеть от LLM или сервера. |
| Frozen input | Binary input boundary + strict UTF-8/BOM policy + отдельно названные raw/text hashes | **Adapt** | Python text mode может менять CRLF/BOM; существующий Phase runtime повторно читает mutable upstream и имеет TOCTOU, поэтому обе реализации требуют собственных vectors. |
| Canonical owner | Task stream — единственная canonical truth; show/list/index — projections | **Reuse directly** | Исключает competing reports и split-brain. |
| Thin wrapper | Hermes/OpenClaw/Codex instructions вызывают один core CLI | **Reuse directly (principle)** | Adapter не должен дублировать validation/hash/state machine. |
| Write-surface containment | Journal root + `tasks/<safe-task-id>.jsonl`; безопасные IDs и path containment | **Reuse directly (principle)** | Защита от traversal и machine-specific paths обязательна. |
| Fail-closed | Invalid event/state/hash/lock/artifact precondition → no append | **Reuse directly** | Частично записанная или недопустимая event недопустима. |
| Exact-HEAD Phase2 baseline | Schema/tool version recorded in events and package metadata | **Reject Phase2; adapt version binding** | Выполнять полный baseline на каждую задачу избыточно; достаточно versioned code/schema и tests. |
| Phase4 wrapper evidence | Adapter invocation metadata внутри attributable fields | **Reject separate wrapper run tree** | Отдельная wrapper evidence surface создаёт путаницу без пользы. |
| Admission Stage 1/2 | CLI input DTO → validated event | **Reject layers; adapt boundary** | Две contract layers не нужны для локального task event. |
| Semantic admission | Нормализованная цель, существенность события | **Reject from core guarantees** | Это решение агента/адаптера. CLI валидирует форму и переходы, но не истинность/полноту смысла. |

## Что переиспользовать напрямую

Под «напрямую» понимается принцип/инвариант, а не копирование shell/Python файлов:

1. Единственный canonical owner.
2. Fail-closed validation перед mutation.
3. Безопасные identifiers и write-surface containment.
4. Frozen/hashed representation принятого input.
5. SHA-256 до и после artifact copy/hashable operation, когда artifact доступен.
6. Обязательное evidence для execution failures; integrity-verification failure report не append-ится в уже недоверенную chain.
7. Wrapper не переписывает canonical outputs.
8. Deterministic verifier и tests, не LLM-verification.
9. Чёткие forbidden claims и boundary statements.

## Что адаптировать

1. Candidate package → in-memory candidate event.
2. Controlled apply → append under cross-platform lock.
3. Phase run directory → per-task JSONL stream.
4. Evidence tree → event payload + optional generated verification report.
5. Destination idempotency → event operation idempotency.
6. Registry → bundled schema dispatch.
7. Rollback → correction/amendment; никогда не deletion/rewrite.
8. Exact-HEAD relationship → `tool_version`, `schema_version`, `hash_algorithm_version` в событиях/exports.

## Что относится только к knowledge admission и не нужно

- source vs knowledge routing;
- source containers и child-source admission;
- knowledge distillation flow matrix;
- knowledge profiles;
- taxonomy config и `knowledge_type` placement;
- Stage 1/Stage 2 admission packages;
- review decision для допуска в KB;
- Phase2 reusable control-plane baseline;
- Phase4 operator wrapper tree;
- byte-for-byte promotion в canonical KB corpus;
- wiki-derived knowledge routes;
- semantic claim taxonomy и domain-specific extraction.

## Что нельзя переносить как архитектурную избыточность

1. Несколько Phase labels для одной локальной append operation.
2. Дублирующие canonical/report surfaces.
3. Отдельный manifest для каждого одиночного event.
4. Множество shell wrappers и run directories.
5. Mutable вручную поддерживаемый registry hashes без автоматической drift verification.
6. Machine-specific absolute paths в portable exports/installable package; raw local events могут иметь отдельный private locator только по privacy policy.
7. Предположение, что schema/hash validation доказывает semantic accuracy.
8. Полный rollback apparatus для immutable history.
9. Постоянный daemon, БД или control plane без доказанной потребности.
10. Заявления о transactional apply/rollback, если реализация допускает partial copy или создаёт только rollback plan.

## Полезные механизмы crab-control-plane

- `run_id`/path validation и direct-child containment;
- JSON Schema Draft 2020-12;
- structured failure evidence;
- same-hash idempotency и different-hash fail-closed;
- pre-apply/post-apply hash checks;
- reached-step artifact requirements;
- explicit canonical-vs-wrapper ownership;
- tests, проверяющие forbidden writes и failure propagation;
- отделение semantic decisions от scripted guarantees.

Ограничения, которые служат отрицательным опытом: общий frozen-input digest не reverify-ится непосредственно перед apply; materialization повторно читает mutable upstream; late copy failure может оставить partial apply; declared scope не доказывает отсутствие иных writes; aggregate reports не schema-validated.

## Что лучше реализовать заново проще

- event envelope и task state machine;
- deterministic canonical JSON profile;
- hash-chain preimage;
- cross-platform file lock/append protocol;
- task replay and projections;
- correction projected view;
- artifact hashing policy;
- agent-neutral CLI and exit codes;
- schema migration/version dispatch.

## Предлагаемое соответствие pipeline

```text
candidate event
-> syntactic JSON Schema validation
-> task stream replay + state-transition validation
-> artifact observation/hash (если доступен)
-> lock + re-read current head
-> assign sequence + previous_event_hash
-> deterministic event_hash
-> controlled binary append + flush/fsync
-> immediate read-back verification
-> release lock
-> canonical per-task journal
```

Нормативные adapters, skills и LLM workflow обязаны использовать этот pipeline. Это не техническая защита от процесса или администратора с прямым write access к journal root; threat boundary описывается отдельно.
