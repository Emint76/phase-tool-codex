# Source Inventory — Итерация 0

Дата фиксации: **2026-07-25**. Hashes — SHA-256 содержимого файлов. Намеренные write-команды в workspace Макса и каноническую KB не выполнялись; из-за `RW=true` отсутствие любых изменений независимо не доказано.

## 1. Среда Макса / OpenClaw live workspace

### Доступ

- Container: `openclaw-openclaw-gateway-1`
- Image: `ghcr.io/openclaw/openclaw:2026.6.6`
- Container user: `uid=1000(node)`
- Workspace: `/home/node/.openclaw/workspace`
- Фактический доступ: read-only-intent команды через `docker exec`; mount технически writable (`RW=true`).

**Scope note:** read-only относится к исследуемым внешним/source workspaces Макса и к запрету продуктового кода. Локальные discovery caches в текущем разрешённом workspace намеренно создавались. File write/patch tools перечислены как доступные инструменты и использовались только для шести discovery-документов, не для кода продукта или внешних source workspaces.

### Актуальные live skills

| Файл | SHA-256 |
|---|---|
| `/home/node/.openclaw/workspace/skills/admission-router-skill/SKILL.md` | `6f6744620860a38dfca78aad8c6058eafaeed3fc45103a3d10ca5e6aa5d4826d` |
| `/home/node/.openclaw/workspace/skills/source-admission/SKILL.md` | `c4a8602b63ea282ed79fb46eee5bb55b80e4d6578eb9089654bbbb3771628044` |
| `/home/node/.openclaw/workspace/skills/knowledge-admission/SKILL.md` | `f94841d6bfbbddbba02b28b64494a6821d65b3b95c22afa7be370cf6a3c2562e` |
| `/home/node/.openclaw/workspace/skills/phase-execution-skill/SKILL.md` | `3452481b4d688a0a162060a4e4b7e1e04d9b633a8fee21bbf3faa90aa51c77b1` |
| `/home/node/.openclaw/workspace/skills/wiki-skill-router/SKILL.md` | `9621b5a1a57681e01abaf93e4bb6144bad56c51edaac9bdf9c2606a7937ee83b` |
| `/home/node/.openclaw/workspace/skills/graphify-kb/SKILL.md` | `489a3569bc276d88427433a9688a51a828dd0f70232cb85aae7b34cb61d3aef1` |
| `/home/node/.openclaw/workspace/skills/source-admission/references/source-admission-example.md` | `b05a4d593d192570f5eb34e04589191f86ebbbd937d0e602108ad8028991acfc` |
| `/home/node/.openclaw/workspace/skills/source-admission/tests/test_source_admission_package.sh` | `05fc3a948625be57d2b5e9bd93dd98f05c2a42ad77d1c1f041c29c23ca065dfd` |
| `/home/node/.openclaw/workspace/skills/knowledge-admission/references/knowledge-admission-example.md` | `6d27ef4b8a4aaf5fc5311ec55de7558ecce38aa95f4f15f9502f5eceb1391c3a` |
| `/home/node/.openclaw/workspace/skills/knowledge-admission/tests/test_knowledge_admission_package.sh` | `29d13da100becf2ac525f0f15cd838e3d1aec2c1dc7e2252ab61d41807bc0f83` |

### Stack registry и architecture note

| Файл | SHA-256 | mtime UTC |
|---|---|---|
| `/home/node/.openclaw/workspace/registries/admission-skill-stack-v1.yaml` | `0719bdfd5752d0c277294753c12141903edc2aff6a749ca106d809bc80b9cfb4` | `2026-07-08 12:58:15` |
| `/home/node/.openclaw/workspace/docs/architecture/admission-skill-stack-v1.md` | `cd34e24c1fdaed15fad0e20a69a6a68fa959615b9a932ce4b68ab817248747d2` | `2026-07-08 12:58:15` |

Обнаружен registry drift:

- registry указывает `knowledge-admission` hash `9ce4a99a...`, фактический live hash — `f94841d6...`;
- registry указывает `phase-execution-skill` hash `fd78497a...`, фактический live hash — `3452481b...`;
- router и source-admission hashes совпадают с registry.

Дополнительно frontmatter description фактического `knowledge-admission` содержит узкую служебную фразу `Fix Profile Selection registry markdown fence.`, не соответствующую широкому содержимому skill. Это metadata-quality/drift issue источника, а не модель для копирования.

### Phase Python runtime

| Файл | SHA-256 |
|---|---|
| `/home/node/.openclaw/workspace/.runtime/phase-python/bin/phase-python` | `a30dc5b0acf1771c4519bcef8989cfe018000b4b33f234d48f7e3bd4ea52a5e1` |
| `/home/node/.openclaw/workspace/.runtime/phase-python/runtime_manifest.json` | `43f083f478034f5bb5fc66051d390504310d180335efcdb6218499f8aaa29ff3` |
| `.../crab-control-plane/operations/harness-phase2/requirements.txt` | `3503f1deb095e9a802192990765ec4dc267270b03330ac80fb4b0b619fbf4d8f` |

Runtime manifest: Python `3.11.2`, `jsonschema 4.23.0`, `PyYAML 6.0.2`; wrapper smoke tests recorded `pass`.

### Canonical checkout в live workspace

- URL: `https://github.com/Emint76/crab-control-plane.git`
- Branch: `main`
- HEAD: `edcbf0d6ffe82e42b8c59fd2e6d80bcfeb786c74`
- Commit date: `2026-06-26T12:42:43+03:00`
- Status at inspection: tracked branch matched `origin/main`, but working tree contained untracked paths (`operations/admission/lib/`, Phase3 `__pycache__`, `skills/source-admission/scripts/`). Source files in the first and third paths не обнаружены; присутствие каталогов обусловлено untracked runtime residue.

Этот checkout не был принят как актуальная GitHub-версия, потому что remote `main` новее.

## 2. Актуальный публичный crab-control-plane

- Repository URL: `https://github.com/Emint76/crab-control-plane`
- Branch: `main`
- Изученный commit: `f6c19d50fe1351e3a501be317f1a3424e5e4883f`
- Commit date: `2026-07-01T22:25:02+03:00`
- Commit subject: `Add operational Graphify KB skill (#104)`
- `git ls-remote refs/heads/main` на дату исследования: тот же SHA.
- Локальный read-only source cache: `_sources/crab-control-plane`.

### Ключевые файлы и hashes

| Путь в repository | SHA-256 |
|---|---|
| `operations/harness-phase3/PHASE3_EXECUTION_CONTRACT.md` | `5aa3a53cc3e205ce839ebf6f3f6f788a510de4e66a8e5464e89703f833b12fdf` |
| `operations/harness-phase3/bin/run_phase3_bundle.sh` | `792e17adb349df9fa757ebb9609dd7deedd02be2738b386eb4659f26a8cbbbf4` |
| `operations/harness-phase3/bin/kb_admission_lib.py` | `5e6cb1318a0246b63d6d01583a9a0d440e634397dddda09e33f83f7d8951bd01` |
| `operations/harness-phase3/contracts/kb_admission_manifest.schema.json` | `a1800d9e55d4bc409e008ebc7d50a448f5b9031b0e86a6959004a50f5e2802c2` |
| `operations/harness-phase4/PHASE4_WRAPPER_CONTRACT.md` | `770d270650dc2427367c66a8e6c6038e65c9e0de6cbe52187a6f1a83c0e912ea` |
| `operations/harness-phase4/bin/run_phase4_wrapper.sh` | `6eb3b6b31d2fa4360337bb4944a8b7f179fcf9b986d2c62824e839786bbba525` |
| `docs/ADMISSION_STAGE2_CONTRACT.md` | `84712915e246927dee6237cab68e12fb82e910eabed7a3dc0dd432887ad4bcac` |
| `operations/admission/schemas/admission_handoff.v1.schema.json` | `edbfaababb7101365e42e7302840537ff558ec8b4f7333eed6e86b8a54428b8c` |
| `docs/CONTROLLED_DISPOSABLE_APPLY_CONTRACT.md` | `e9b6a0e4139387e8b734ae928947ae46edb460f6c543fa7991b982678f07c5f5` |
| `operations/harness-openclaw-disposable-apply/bin/run_controlled_disposable_apply.sh` | `09fb60abdc34e7e669340bcc730d233bcfe4d3c73a63dff3d94f70cb0fcae34c` |
| `docs/ROLLBACK_MODEL.md` | `d40abf99f60671c9997b41b8ac3befb6a5d256797f7cc7dbe4aec786bb34c85c` |
| `docs/EVIDENCE_RETENTION_POLICY.md` | `2dc62177e5cfa79d5471ab9fffd3c0fe38ad1e178c43feeedb94f8c506a4c278` |
| `operations/harness-orchestration/ORCHESTRATION_CONTRACT.md` | `cfc3de31de8905eceefe4746acd4c24b998a258cfcf2b3fbc299dcf737402f96` |

Также изучены Phase3 runbook, execution-target schema, admission policy/contracts, evidence schemas, controlled apply schemas/tests, logging и CI workflow inventory.

Независимый script-level review дополнительно проверил `check_admission_policy.py`, `freeze_phase2_input.py`, `hash_frozen_input.py`, `reverify_runtime_ready.py`, `materialize_phase3_staging.py`, `execute_apply.py`, `repo_admission_lib.py`, `validate_post_apply.py`, report emitters и disposable-apply rollback plans. Он подтвердил TOCTOU между reverify/materialization, отсутствие общего transactional rollback и то, что aggregate reports не имеют отдельной schema-validation boundary.

## 3. Hermes

### Версия и checkout

- CLI version: `Hermes Agent v0.19.0 (2026.7.20)`
- Reported upstream marker: `07e97d2f`
- Install method: Git
- Install directory: `C:\Users\Gennady\AppData\Local\hermes\hermes-agent`
- Local branch: `main`
- Local HEAD: `7cbdcf1ba6f79b2e509963e142b4a77915eea523`
- Commit date: `2026-07-23T00:16:20-05:00`
- Remote: `https://github.com/NousResearch/hermes-agent.git`
- Local status: `ahead 10128, behind 1`; поэтому локальный checkout фиксируется как фактическая установленная сборка, но не объявляется чистым upstream snapshot.
- CLI entry point: `C:\Users\Gennady\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe`
- Entry-point SHA-256: `07164a7cbbfdc7234fffb16e1f068a0ddd3eb038a47db758e2c6ec0ec6126bf5`
- Entry-point size/mtime: `46080` bytes; `2026-07-23 07:21:36 +02:00`.
- Import binding: active venv resolves `hermes_cli.main` to `C:\Users\Gennady\AppData\Local\hermes\hermes-agent\hermes_cli\main.py`; это связывает фактически вызванный CLI с install checkout, но не является supply-chain attestation.

### Ключевые локальные файлы

| Файл | SHA-256 |
|---|---|
| `agent/skill_utils.py` | `c8c0928d3ff00b47b3be04126393c5b7a67c86bab262eba1df4bf4c8fad00c95` |
| `tools/delegate_tool.py` | `4908509b68d6ca826daa5208eb60cfa1459b1463262881382430bdc4b0cd6828` |
| `tools/session_search_tool.py` | `0185a1f941c483b3a0d4af1560c559a9d3010980bedc8704cdf69326e4fa2381` |
| `tools/cronjob_tools.py` | `a7e889c710c28ba97ffe9562ce74c3feb415bba9e1d5ddfe05c1c76516920d58` |
| `hermes_state.py` | `306ee552906202c9628785ad22d85f239e0470279ae3bc6360b9e604a3eee686` |
| `toolsets.py` | `fbedd2b6c70fe298ff3d3f4dea0a396d08dbd27b617d355e0181e48701c4c3eb` |
| `hermes_cli/main.py` | `6ea6b13c7e26bebab4abe68bffa547a73ae89813b8b0ecddf1c01d2c1acbc4e8` |

### Официальная документация

Authoritative base: `https://hermes-agent.nousresearch.com/docs`.

| Final URL | Local snapshot | Retrieval UTC | HTTP | Bytes | SHA-256 |
|---|---|---|---:|---:|---|
| `https://hermes-agent.nousresearch.com/docs` | `_sources/hermes-docs/docs.html` | `2026-07-25T18:02:48Z` | `200 text/html; charset=utf-8` | 33757 | `6ad181dc9b6767c5db4eeb5d6a0dc0ec8ff7ecd7d65044b8f68c421ca768fc37` |
| `https://hermes-agent.nousresearch.com/docs/user-guide/features/skills` | `_sources/hermes-docs/skills.html` | `2026-07-25T18:02:48Z` | `200 text/html; charset=utf-8` | 179570 | `003fa0a5b539396c557f2a01dfd9335d541e04ac222723c6f3b666120b3811fe` |
| `https://hermes-agent.nousresearch.com/docs/reference/cli-commands` | `_sources/hermes-docs/cli-commands.html` | `2026-07-25T18:02:49Z` | `200 text/html; charset=utf-8` | 268129 | `d2884c234b3d077d3db0df83ae39b586594cbdfb7e57994a47df9380579e56fd` |
| `https://hermes-agent.nousresearch.com/docs/user-guide/features/cron` | `_sources/hermes-docs/cron.html` | `2026-07-25T18:02:50Z` | `200 text/html; charset=utf-8` | 166111 | `6172c3c8943fcfcfd5191c54b31b4410e13c9d833cdcd3b168ed38ce97f05414` |

HTTP metadata was rechecked after snapshot retrieval and matched the same final URLs/status/content type; it is not a signed server attestation.

Подтверждено:

- skills используют `SKILL.md` с YAML frontmatter и progressive disclosure;
- support files размещаются в `references/`, `templates/`, `scripts/`, `examples/`, `assets/`;
- `--skills`, `--pass-session-id`, profiles и worktree доступны в CLI;
- sessions имеют локальное хранилище и export, но не должны быть canonical task journal;
- subagents изолированы и недолговечны относительно процесса;
- cron запускает fresh sessions и не нужен для core v0.1;
- Hermes skill может быть адаптером, но CLI обязан работать независимо от Hermes.

### Фактически доступные инструменты для разработки

Использованы/подтверждены: `terminal`, `process`, file read/search/write/patch tools, `delegate_task`, `todo`, Git, Docker, Codex CLI. Доступна knowledge-graph MCP toolset, но отдельный graph build для Итерации 0 признан нецелесообразным.

## 4. Codex CLI

- Version: `codex-cli 0.140.0`
- Подтверждены `codex exec`, `--sandbox read-only|workspace-write|danger-full-access`, `--ephemeral`, `--cd`, `--output-schema`, `--json`, `--ignore-user-config`, `--ignore-rules`.
- В Итерации 0 использован read-only ephemeral analysis pass; код продукта не создавался.

## 5. Локальные discovery caches

Внутри рабочей директории созданы source caches:

- `_sources/crab-control-plane/` — отдельный nested Git clone;
- `_sources/hermes-docs/` — HTML snapshots и sitemap.

Они являются воспроизводимыми входами discovery, не частью предлагаемого устанавливаемого пакета v0.1 и не должны попадать в будущую публикацию без отдельного решения.
