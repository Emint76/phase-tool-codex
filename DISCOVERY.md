# Итерация 0 — discovery

Дата исследования: **2026-07-25**

Рабочая директория: `C:\Users\Gennady\HermesWorkspace\Research\agent-task-journal`
Статус: discovery и архитектурное проектирование; код продукта не создавался.

## Цель и границы

Исследовать применимые механизмы Phase/OpenClaw, актуальный `crab-control-plane` и фактические возможности Hermes, затем предложить минимальную переносимую архитектуру **ALCOA+-inspired task journaling** для жизненного цикла пользовательской задачи:

```text
task_open -> task_event* -> task_close -> task_verify
```

Здесь `task_verify` — **записанное событие полного journaled lifecycle**. Его нужно отличать от read-only integrity check, который CLI `verify` может выполнять в любой момент и который сам по себе не меняет journal. Закрытая, но ещё не имеющая recorded `task_verify`, задача должна быть видна как `closed_unverified`, а не считаться прошедшей полный lifecycle.

В v0.1 не предлагается журналировать системные процессы, весь компьютер, внутренние рассуждения, каждое файловое или сетевое действие. Объект журнала — пользовательская задача, существенные события исполнения, результат, ошибки, артефакты и незавершённые пункты.

## Метод

1. Проверены локальные версии Hermes, Codex CLI, Python, Git, `uv`, Docker и WSL.
2. Установлен фактический способ исследования среды Макса: `docker exec` в работающий контейнер OpenClaw. Намеренные write-команды не выполнялись; использовались чтение, `stat`, Git-inspection и SHA-256. Mount был writable, поэтому отсутствие любых изменений workspace независимо не доказано.
3. Прочитаны актуальные live skills Макса и их stack registry; прослежены ссылки на контракты, схемы, wrappers, canonical evidence и hash verification.
4. Клонирован актуальный публичный `crab-control-plane` в локальный source cache `_sources/crab-control-plane`; исследован `main` на зафиксированном commit.
5. Проверены официальные Hermes docs, локальный Hermes checkout, CLI help и реально доступные tools.
6. Запущены read-only архитектурный проход Codex CLI и отдельный review-субагент; подтверждённые замечания внесены в документы.

## Фактическая среда

| Компонент | Фактическое значение |
|---|---|
| Hermes | `v0.19.0 (2026.7.20)`; upstream marker `07e97d2f`; local checkout `7cbdcf1ba6f79b2e509963e142b4a77915eea523` |
| Codex CLI | `codex-cli 0.140.0` |
| Python | `3.11.15` |
| uv | `0.11.31` |
| Git | `2.53.0.windows.3` |
| Docker | `29.3.1` |
| OpenClaw container | `openclaw-openclaw-gateway-1`, image `ghcr.io/openclaw/openclaw:2026.6.6`, healthy |
| Host | Windows 10; Hermes terminal uses Git Bash/MSYS |

## Доступ к среде Макса

Подтверждены пути внутри контейнера:

- `/home/node/.openclaw/workspace/skills`
- `/home/node/.openclaw/workspace/repos/crab-control-plane`
- `/home/node/.openclaw/workspace/registries/admission-skill-stack-v1.yaml`
- `/home/node/.openclaw/workspace/docs/architecture/admission-skill-stack-v1.md`
- `/home/node/.openclaw/workspace/.runtime/phase-python/`

Docker mount для `/home/node/.openclaw/workspace` технически `RW=true`; поэтому read-only intent обеспечивался дисциплиной вызовов, а не mount-level enforcement. Transcript подтверждает отсутствие намеренных write-команд, но не является независимым before/after доказательством неизменности. Это отмечено как риск. Ожидаемые пути не обнаружены непосредственно на Windows/MSYS host. Доступ через контейнер является фактически подтверждённым способом.

## Изученная цепочка Phase

Фактическая схема live stack Макса:

```text
AGENTS.md
-> admission-router-skill
-> source-admission | knowledge-admission | STOP missing route
-> prepared package + handoff + execution target + manifest
-> phase-execution-skill
-> standalone policy preflight
-> exact-HEAD Phase2 baseline
-> Phase4 thin wrapper
-> Phase3 kb_admission
-> canonical Phase3 evidence + destination hash verification
```

### Разделение ответственности

- **Router** выбирает маршрут и умеет STOP; он не готовит package и не запускает Phase.
- **Source/knowledge skills** принимают семантические решения и готовят candidate/package/handoff; они не являются canonical execution owner.
- **Phase2** доказывает готовность control-plane на точном Git HEAD; не допускает конкретный asset.
- **Phase4** — тонкий operator wrapper, не владеющий canonical report/exit status.
- **Phase3** замораживает входы, валидирует target/manifest, выполняет controlled apply, пишет единственную canonical evidence surface и проверяет hashes.
- **Semantic correctness** остаётся за producer/agent/review boundary; scripted Phase гарантирует форму, границы записи, hashes и воспроизводимые evidence, но не истинность содержания.

### Реальные гарантии, подтверждённые кодом

`operations/harness-phase3/bin/run_phase3_bundle.sh`:

- валидирует безопасный `run_id`;
- проверяет containment canonical run directory;
- freeze-ит upstream inputs;
- пишет hashes frozen input;
- последовательно выполняет pre-apply, reverify, staging, apply, evidence collection, post-apply и report;
- fail-closed пропускает последующие шаги после blocking failure;
- требует artifacts для достигнутых шагов;
- сохраняет `exit_code` и отчёты даже при раннем отказе, когда это технически возможно.

`operations/harness-phase3/bin/kb_admission_lib.py`:

- использует JSON Schema Draft 2020-12;
- проверяет manifest и runtime integration;
- нормализует KB-relative paths и containment;
- сравнивает source SHA-256 с `expected_sha256`;
- допускает idempotent existing destination только при том же hash;
- fail-closed отклоняет существующий destination с другим hash;
- после copy повторно hash-ирует destination;
- пишет структурированное evidence как при success, так и при failure.

### Ограничения фактической реализации Phase

Независимый read-only проход по scripts выявил границы, которые нельзя превращать в гарантии task-journal:

- `input.sha256` создаётся, но общий frozen-input digest непосредственно перед apply не пересчитывается;
- runtime-ready package не полностью копируется в frozen input: после manifest/hash последующие шаги снова читают mutable upstream;
- между `reverify_runtime_ready.py` и `materialize_phase3_staging.py` остаётся TOCTOU-окно;
- Phase3 admission copy не является общей транзакцией: поздний failure может оставить ранее скопированные файлы;
- rollback artifacts/plans существуют, но общего исполняемого rollback для admission нет;
- `declared_scope` не является системным аудитом всех writes, а canonical aggregate reports не проходят отдельную JSON Schema validation.

Поэтому в этой документации «freeze», evidence и rollback рассматриваются как полезные **намерения и частичные scripted controls**, а не как полностью доказанные end-to-end свойства существующей системы.

## Существенные наблюдения

1. **Canonical owner должен быть один.** Wrapper metadata нельзя смешивать с canonical journal events.
2. **Validation не равна promotion.** Проверенный candidate ещё не canonical event, пока controlled append не завершён.
3. **Hash verification не равна semantic correctness.** Это важнейшая граница для честных заявлений о гарантиях.
4. **Rollback неприменим к истории журнала.** Для append-only journal исправление — новый correction/amendment event; rollback допустим только для побочных операций/артефактов и не должен удалять события.
5. **Phase-архитектура полезна как набор инвариантов, но слишком тяжела для v0.1 task journal.** Не нужны Phase2/3/4, admission packages, taxonomy, profile registry и отдельные wrapper run trees.
6. **Live stack имеет drift.** Hashes `knowledge-admission` и `phase-execution-skill` в registry/architecture note не совпадают с фактическими live файлами. Это прямое доказательство, что task-journal не должен полагаться на вручную поддерживаемый registry как на единственную гарантию.
7. **Per-task JSONL лучше соответствует v0.1**, чем один глобальный ledger: меньше lock contention и blast radius, естественный lifecycle replay, простые backup/export/show. Цена — отсутствие единого глобального total order; список строится детерминированным scan/projection.
8. **Contract claims нужно проверять по коду и negative tests.** В Phase обнаружены TOCTOU, non-transactional partial apply и planned-only rollback; task-journal не должен наследовать эти заявления только из prose contracts.

## Вывод discovery

Рекомендуется маленькое Python-приложение без daemon и БД, где canonical truth — append-only JSONL stream каждого task. Каждый candidate event проходит schema/domain validation под lock, получает sequence и hash link, затем controlled append делает его canonical. Crash во время append всё ещё может оставить обнаруживаемый partial tail; v0.1 должна обнаруживать его и fail closed, а не обещать невозможную абсолютную atomicity. `show`, `list` и read-only integrity verification строят состояние replay-ем событий; mutable index не является canonical и для v0.1 не нужен.

Все окончательные решения по event envelope, state machine, canonical JSON, lock protocol, correction semantics и `verify`/`task_verify` должны быть приняты и зафиксированы ADR в Итерации 1.
