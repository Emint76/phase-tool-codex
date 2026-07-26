# Repository Transition Plan — Iteration 0.5

Status: planning only. The repository is not renamed, files are not moved, and no commit is authorized by this document.

## 1. Current state

Current repository directory/name:

```text
agent-task-journal
```

Current architectural baseline:

```text
9cb1bec117ef4ff6164f84b20a1998398093faca
```

The Git history is valuable: Iteration 0 records the task-journal discovery that motivated the first new Phase contract. That history must remain reachable and unmodified.

## 2. Decision for now

**Keep the current repository and name during Iteration 0.5.**

Reasons:

- user explicitly forbids rename now;
- product boundary is still under review;
- no product code exists to migrate;
- an in-place later rename can preserve the entire `.git` history;
- creating a second repository now risks split authority and duplicated documents.

The current name is a temporary mismatch, not a decision that the product remains task-journal-only.

## 3. Options after explicit approval

| Option | History | Benefits | Risks | Recommendation |
|---|---|---|---|---|
| Keep `agent-task-journal` permanently | Preserved | No migration | Misrepresents universal product; discourages non-task contracts | Reject unless Phase Core strategy is abandoned |
| Rename repository/directory in place to `phase-tool` | Fully preserved | One authority, simple history, task journal remains first contract | Requires remote/package/links migration later | **Preferred after architecture approval** |
| Create a new `phase-tool` repo and import history | Can be imported | Clean naming/security boundary | Split history, duplicate issues/docs, complex lineage | Use only for governance/legal ownership separation |
| Keep research repo and create clean implementation repo | Research preserved, implementation starts clean | Small product history | Loses direct file history; two canonical repos | Not preferred without a strong publication reason |

## 4. Proposed future repository structure

```text
phase-tool/                       # future name; not applied now
  pyproject.toml
  README.md
  core/
    contracts/                    # resolver and compatibility, not domain bundles
    candidate/
    freeze/
    validation/
    effects/
    verification/
    evidence/
    cli/
  contracts/
    task_journal/
      v1/
        contract.json
        schemas/
        validators/
        projections/
        tests/
    source_admission/
      v1/
    knowledge_admission/
      v1/
  adapters/
    hermes/
    openclaw/
    codex/
  skills/
    phase-tool/
    task-journal/
  tests/
    core/
    conformance/
    integration/
    platform/
    fixtures/
  docs/
    architecture/
    adr/
    roadmap/
    history/
  tools/
```

Directory names are conceptual. Python import/package naming must be decided separately; repository layout should not force arbitrary plugins into core.

## 5. Historical document treatment

The six Iteration 0 documents and seven Iteration 0.5 documents are historical architectural records.

Rules:

- do not rewrite Iteration 0 to make it appear Phase Core was always the plan;
- `STRATEGIC-CORRECTION.md` explicitly records the changed boundary;
- if files are later reorganized, use `git mv` in a dedicated approved commit;
- preserve commit `9cb1bec…` as the exact Iteration 0 baseline;
- use ADRs for superseding decisions instead of destructive editing;
- links should identify both current path and source commit when stability matters.

Potential later placement:

```text
docs/history/iteration-0/
docs/history/iteration-0.5/
```

This move is not authorized now.

## 6. Safe transition sequence

### Gate A — architecture approval

- approve/reject the seven Iteration 0.5 documents;
- resolve product name and canonical repository decision;
- define Phase Core non-goals and contract trust model;
- no code before this gate.

### Gate B — neutral contract skeleton

After explicit approval:

- add neutral directories `core/`, `contracts/`, `adapters/`, `skills/`, `tests/`;
- add ADRs and conceptual schemas/test vectors;
- keep existing documents intact;
- no Phase2/3/4 code copy.

### Gate C — optional in-place rename

Only after explicit authorization:

1. ensure clean working tree and no active processes;
2. record current commit/branches/tags/remotes;
3. rename directory/repository in place while preserving `.git`;
4. update local project binding and relative documentation links;
5. update package/CLI names in a separate commit;
6. if a remote exists later, use repository-host rename/redirect and update remote URL;
7. verify `git log --follow`, tags, tests and install paths;
8. retain compatibility aliases only for a defined period.

Do not use history-rewriting tools (`filter-repo`, rebase of published history) for a simple product rename.

### Gate D — first vertical slice

- implement core contract resolution/freeze/validation/evidence minimum;
- implement `task_journal.v1` through registered append/create mechanisms;
- add Hermes adapter only after core CLI works standalone;
- no source/knowledge migration yet.

### Gate E — admission compatibility

- express source and knowledge admission as contracts;
- run current fixtures against legacy and new paths;
- compare candidate/result/evidence and refusal behavior;
- retain legacy wrappers until parity and an explicit deprecation decision.

## 7. Legacy compatibility policy

Existing Phase2/3/4 and live skill surfaces remain external baselines. They are not moved into this repository during Iteration 0.5.

Future migration rules:

- adapt contracts/mechanisms, do not copy entire directories;
- keep exact upstream commit/path attribution;
- preserve legacy fixture expected results;
- classify differences as intentional contract changes or regressions;
- do not point live skills to the new tool before versioned adapter tests pass;
- never mutate live KB/workspace during compatibility testing; use disposable fixtures/roots.

## 8. Repository authority

Future single-source rules:

- Phase Core contract APIs: `core/` + core ADRs/tests;
- installable operation contracts: `contracts/` bundles;
- agent integration: `adapters/` and `skills/`;
- generated evidence/results: never committed as source unless explicit fixtures;
- instance taxonomy/profile config: outside canonical product repository;
- historical research: `docs/history/` after an approved move.

## 9. Migration safety checklist

Before any future move/rename:

- clean tracked working tree;
- source caches explicitly excluded or classified;
- backup/tag/commit reference recorded;
- no unpublished history rewrite;
- Windows path and Hermes project binding checked;
- no KB junction traversal;
- no live OpenClaw mount writes;
- no global package/config changes;
- independent review of planned `git mv`/rename diff;
- user authorization for commit and rename.

## 10. Current stopping condition

Iteration 0.5 stops with new uncommitted Markdown documents in the existing repository. No directory, remote, package, branch, tag, or history change is part of this iteration without another instruction.
