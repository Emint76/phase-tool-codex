# Graph Decision — Итерация 0

## Решение

**Рабочий dependency/knowledge graph сейчас не создавать.**

Для следующих итераций достаточно:

- `SOURCE-INVENTORY.md`;
- `REUSE-MAP.md`;
- conceptual component/ownership map в `ARCHITECTURE-PROPOSAL.md`;
- ADR для contract decisions;
- Git-tracked development journal в будущем проекте.

## Проверка условий пользователя

| Условие | Оценка |
|---|---|
| Уменьшит риск пропустить важные связи | Частично, но реальные критические связи уже линейны и явно подтверждены contracts/scripts. |
| Реально будет использоваться в следующих итерациях | Не доказано. Iterations 1–3 требуют event contract и CLI, не graph traversal. |
| Можно строить воспроизводимо | Теоретически да, но пришлось бы определять extraction schema/builder и versioning. |
| Можно обновлять при изменении источников | Да только с дополнительной automation, которой пока нет и которая расширит scope. |
| Больше пользы, чем таблица/ADR | Нет на текущем размере decision surface. |

Поскольку одновременно выполняются не все условия, graph build был бы преждевременной архитектурой.

## Почему таблица лучше сейчас

1. Для task-journal полезны около пятнадцати Phase concepts, уже отражённых в `REUSE-MAP.md`.
2. Реальная execution chain линейна: router → preparation → preflight → wrapper → canonical owner → evidence.
3. Основные риски — hash/canonicalization, locking, state transitions, correction semantics и overclaiming; они лучше контролируются ADR и test vectors.
4. Graphify добавил бы tool/runtime/output artifacts, source-drift и review burden, не улучшая contract decisions.
5. Создание graph proposal как канонического артефакта могло бы ошибочно придать extracted/inferred edges нормативный статус.
6. Пользователь прямо запретил граф ради графа.

## Что всё же зафиксировано

Вместо graph создана воспроизводимая conceptual ownership map; стрелки показывают основной вызов/ownership, а не полный dependency graph:

```text
Agent adapters
  -> Core CLI
    -> Application use cases
      -> Domain state replay
      -> Schema validation
      -> Canonical codec / SHA-256
      -> Artifact hashing
      -> Journal store / controlled append
    -> Verifier
    -> Read-only projections
```

Verifier при этом использует schema registry, canonical codec, journal store и artifact policy; упрощённая схема не отрицает эти зависимости.

Source-to-guarantee trace:

```text
Max live skill
-> referenced crab contract
-> schema/script
-> validation/apply behavior
-> evidence owner
-> task-journal reuse decision
```

Точные paths и hashes находятся в `SOURCE-INVENTORY.md`.

## Условие пересмотра

Вернуться к graph decision только если появится хотя бы одно из следующего:

- adapters/plugins/contracts становятся многочисленными и имеют many-to-many version compatibility;
- source inventory превышает возможности ручной dependency table;
- регрессии регулярно возникают из-за пропущенных связей schema ↔ command ↔ adapter ↔ guarantee;
- нужен автоматический impact analysis при изменении schemas;
- builder может извлекать **declared** dependencies детерминированно из package metadata/tests, без LLM-inferred normative edges.

## Если граф понадобится позже

Предварительная, неактивная спецификация:

- **Назначение:** impact analysis и проверка покрытия guarantee → implementation → test → adapter.
- **Типы узлов:** command, event type, schema, state rule, guarantee, module, adapter, test, ADR.
- **Связи:** validates, appends, verifies, projects, invokes, constrained-by, tested-by, versioned-by.
- **Источник данных:** repository manifests, imports, CLI registry, schema `$id`/`$ref`, explicit test metadata; не свободный LLM extraction как canonical source.
- **Builder:** deterministic Python script внутри repository.
- **Output:** versioned JSON + optional HTML; generated, non-canonical.
- **Update:** CI/regeneration при изменении declared source files.
- **Запросы:** «какие tests покрывают/проверяют hash-chain guarantee?», «какие adapters затронуты schema v2?», «какие commands обходят controlled append?».

Этот proposal не активирован и graph artifacts в Итерации 0 не создавались.
