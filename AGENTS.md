# AGENTS.md

This file provides guidance to coding-agent CLIs (Claude Code, Gemini CLI, Codex) when working with code in this repository. `CLAUDE.md` and `GEMINI.md` are symlinks to this file — edit only `AGENTS.md`; the other two always reflect it.

## What this repo is

Configuration and supporting assets for the **OVG Casino Concierge**, a virtual assistant deployed on **Google Cloud Customer Engagement Suite (CX Agent Studio)**. There is no application server here — the agent runtime lives in CX Agent Studio. This repo holds the agent's full configuration (instructions, tools, guardrails, evaluations) under `cxas_app/`, the data pipeline that feeds its game search, and the frontend snippet that renders rich UI cards in the embedded `ces-messenger` widget.

## cxas-scrapi tooling

The canonical CLI for managing the agent is [`cxas-scrapi`](https://googlecloudplatform.github.io/cxas-scrapi/stable/). It pulls/pushes the entire CES app as files on disk under `cxas_app/Casino_Concierge/`, replacing the older MCP-driven `update_agent` workflow. See **Deployment workflow** below for the full loop. The retrofit roadmap (lint, evals, CI/CD, Claude Code skills) has been implemented and shipped (foundation, linter enforcement, evaluation suites, and skills integration are live; automated CI/CD gating remains).

## Architecture (the parts that span multiple files)

The agent has three tightly coupled surfaces. Changes to one usually require coordinated changes to the others:

1. **Agent definition** — `cxas_app/Casino_Concierge/` is the source of truth, pulled from CES via `cxas pull` and pushed back via `cxas push`. Key files inside it:
   - **Root Agent (`Casino_Concierge`)**:
     - `agents/Casino_Concierge/instruction.txt` — system prompt for the primary VIP host. XML-tagged sections (`<role>`, `<persona>`, `<constraints>`, `<taskflow>`, `<examples>`). Handles discovery, game explanations, and transfer decisions.
     - `agents/Casino_Concierge/Casino_Concierge.json` — Root agent declaration with `childAgents` mapping.
   - **Sub-Agent (`Safety_Handler`)**:
     - `agents/Safety_Handler/instruction.txt` — system prompt for safety. Handles gambling distress and underage signals.
     - `agents/Safety_Handler/Safety_Handler.json` — sub-agent declaration.
   - **App Configuration**:
     - `app.json` — app-level config: voice, multilingual locales, model, guardrails attached, logging settings.
     - `environment.json` — env-specific values referenced via `$env_var` placeholders (e.g., Vertex AI Search paths).
     - `tools/{search_available_games,display_game_widget}/<name>.json` — tool definitions.
     - `guardrails/{Prompt,Safety}_Guardrail_*/<name>.json` — CES native guardrails attached to the app.
     - `evaluations/<name>/<name>.json` — CES native evaluations (synced from `evals/goldens/*.yaml`).
2. **Game catalog data pipeline** — game data is scraped from the casino frontend JS bundle, written to `data/processed/games_catalog.csv` (matches `data/processed/schema.json`, includes a `url` column), loaded into BigQuery (`ovg_casino.games_inventory`), then indexed by a Vertex AI Search Data Store (`ovg_casino_games_catalog`) + Engine (`ovg_casino_games_engine`). The agent calls a Datastore Tool named `search_available_games` against this index. A human-readable mirror lives at `data/raw/games.md` (regenerated from the CSV; includes direct game URLs).

3. **Frontend rich-UI rendering** — `scripts/frontend_widget.html` is a snippet embedded on `casino.oliviervg.com`. It registers a Handlebars template named `game_carousel` with `ces-messenger`, and the agent's `display_game_widget` Client Function Tool emits `{template_id: "game_carousel", context: {games: [...]}}` which `ces-messenger` intercepts and renders. The same snippet also passes `user_first_name` from Firebase auth into the agent via `setQueryParameters`, and listens for `ces-end-session` to close/clear the chat when the agent calls `end_session`.

Two built-in tools the agent uses without a tool definition: `end_session` (with `reason="customer_query_ended"` or `reason="responsible_gambling"`).

## CX Agent Studio conventions (non-obvious)

- **Tool/agent reference syntax in `instruction.txt`:** Use the canonical CES forms `{@TOOL: tool_name}` and `{@AGENT: Agent Name}` for tool/agent references that the LLM should resolve (the cxas linter rule `I011` enforces this; `I012` flags references the linter can't see). Do not use the older Dialogflow CX form `${TOOL:tool_name}`. Inside `<examples>` blocks, the literal `<agent>Execute tool \`tool_name\` with arguments: \`{"key": "value"}\`</agent>` pattern (followed by a `<tool_response>` block, then a final natural-language `<agent>` response) is the conventional way to *show* a tool call in simulated dialogue and stays as-is.
- **Variable interpolation:** Use `{user_first_name}` (single braces) in prompts — this is the format CX Agent Studio expects for query parameters passed via `setQueryParameters`. See recent commits for prior fixes around this.
- **Widget rendering:** `ces-messenger` does NOT support CX Agent Studio's native `WidgetTool` components (e.g. `PRODUCT_CAROUSEL`). Rich UI must go through the Client Function + Handlebars template pattern:
  1. **Backend tool:** `display_game_widget` is configured as a **Client Function** tool.
  2. **LLM execution:** the LLM calls it with `template_id: "game_carousel"` and an array of objects under `context.games`.
  3. **Frontend render:** the embedded `scripts/frontend_widget.html` snippet intercepts the client function call and renders via the custom `game_carousel` Handlebars template.
- **Vertex AI Search BigQuery import:** When importing structured data from BigQuery, the system defaults to looking for an `_id` column. Our schema uses `id`, so the import payload must include `"idField": "id"` or ingestion fails silently.
- **Anti-hallucination:** Constraints in the prompt forbid recommending any game not returned by `search_available_games`. Don't loosen this without considering the regulatory framing (responsible gaming).
- **Tone budget:** Voice is `en-US-Chirp3-HD-Zephyr`. Persona is **warm, upbeat, approachable, professional, and responsible**. Keep agent responses to 2–3 short sentences so TTS doesn't monologue.
- **`end_session` positioning (Direct Native Invocation):** When a user expresses gambling distress or underage signals, the root agent transfers immediately to `Safety_Handler`. The sub-agent is instructed to natively call the custom python function `get_responsible_gaming_helpline` to dynamically retrieve the correct, locale-aware helpline details, and then directly issue the built-in `end_session` tool call (with `reason="responsible_gambling"`) within its prompt instructions.

## Deployment workflow

1. Activate the venv: `source .venv/bin/activate`. cxas-scrapi is installed there (`pip show cxas-scrapi`).
2. Edit `cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt` (or whichever file under `cxas_app/` you need to change). XML-tagged sections in `instruction.txt` remain the structure.
3. Verify locally before pushing. Two options:
   - **Strongest:** `cxas ci-test --app-dir cxas_app/Casino_Concierge --display-name "[CI] Verify" --env-file cxas_app/Casino_Concierge/environment.json --project-id bigquery-demo-396708 --location us` — pushes to a temp app, exercises the CI lifecycle. Clean up with `cxas delete --app-name <returned-resource> --project-id bigquery-demo-396708 --location us` afterwards.
   - **Lighter:** re-pull a fresh copy to a temp dir and `diff -r` against your edited `cxas_app/` to confirm only your intended changes show up.
4. Push to prod:
   ```
   cxas push \
     --app-dir cxas_app/Casino_Concierge \
     --to projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 \
     --env-file cxas_app/Casino_Concierge/environment.json \
     --project-id bigquery-demo-396708 \
     --location us
   ```
5. Smoke-test on `https://casino.oliviervg.com`. Until automated CI/CD integration is complete, this is the only behavioral safety net — UI/agent changes are not "done" until exercised in a browser.
6. If game data changes: re-run the scraper, reload BigQuery (`ovg_casino.games_inventory`), trigger Vertex AI Search re-import. (Unchanged from prior workflow.)
7. Commit and push to a feature branch and open a PR. The PR-based workflow is established; once automated CI/CD is in place, PRs will create ephemeral CES apps and run the full eval matrix automatically.

Project is on `main`; commit author is `Olivier Van Goethem <ovg@google.com>`.

### CLI gotchas worth knowing

- `cxas pull` uses `--target-dir`, not `--output-dir`.
- `cxas push` uses `--app-dir` (hyphen, not underscore) and has no `--dry-run` flag — use `cxas ci-test` to verify safely.
- `cxas push --to <resource>` targets an existing app; `--app-name` is a different v1beta API path.
- `cxas apps` is a parent command; use `cxas apps list` or `cxas apps get`.
- `cxas delete` uses `--app-name <full-resource>`, not a positional argument.
- `cxas push` and `cxas ci-test` both accept `--env-file` to inject `environment.json` (which holds the per-environment Vertex AI Search engine/datastore paths via `$env_var` resolution). Always pass it.
- `cxas lint` reads `cxaslint.yaml` from the value of `--app-dir` (treats it as project root). Our `cxaslint.yaml` lives at repo root and sets `app_dir: cxas_app/Casino_Concierge`, so the canonical invocation is plain `cxas lint` from the repo root (NOT `cxas lint --app-dir cxas_app/Casino_Concierge`, which would look for cxaslint.yaml inside the app dir and miss it).
- **Temporary Files:** Do NOT commit evaluation reports (`eval-reports/`), experiment logs (`experiment_log.md`), results TSVs (`results.tsv`), or intermediate JSON summaries to Git. These are transient artifacts generated by the eval runner. Ensure `.gitignore` is respected and double-check `git status` before committing.

### Linting

`cxas lint` (run from repo root, no flags needed) checks the agent against the cxas-scrapi linter ruleset. Configuration lives in `cxaslint.yaml` at repo root — severity overrides only, with inline rationale comments for each suppression.

**Lint policy: zero errors, zero warnings.** Any rule downgrade in `cxaslint.yaml` requires a rationale comment plus a follow-up TODO. New violations introduced by an edit must be either fixed at the source or downgraded with a documented rationale (the I004 downgrade with its TODO in `FUTURE_ENHANCEMENTS.md` §4.7 is the pattern); silent downgrades are not acceptable.

Two enforcement layers gate this:
- `.githooks/pre-push` runs `cxas lint` on every `git push` (bypassable with `--no-verify` for emergencies).
- `.claude/settings.json` and `.gemini/settings.json` wire the cxas-agent-foundry's `pre-agent-push-lint.sh` hook, which runs `cxas lint --json` on every `cxas push` from inside Claude Code or Gemini CLI (so an LLM agent issuing the push gets gated too). See § "Hooks & settings" below.

Automated CI/CD will add a non-bypassable CI gate.

Re-enable any rule by removing its line from `cxaslint.yaml`. The hook uses cxas's exit code (non-zero = errors found), so any new rule violations introduced by an edit will block the push.

### Evals

Eval YAML lives at `evals/` (project root), with `evals/goldens/*.yaml` for Platform Goldens and `evals/simulations/*.yaml` for Simulations. The cxas-scrapi linter rules `E001`-`E011` only fire on files under those subdirectories.

Schema gotchas the lint won't always catch:

- **Goldens `agent:` field** must be a plain string or list-of-strings (rule `E007` enforces). To assert a tool fires without pinning the agent's text, set `agent: "# silent — <reason>"`. The runtime parser (`cxas_scrapi/utils/eval_utils.py:_process_dataset_turn`) skips the `agentResponse` expectation step whenever the agent string contains the substring `# silent`, so the eval doesn't false-fail on any text the agent actually produces. Without this marker, dropping `agent:` triggers `E008` and the runtime auto-FAILs the turn for "unexpected response". This `# silent` pattern is used extensively in our themed Goldens (`discovery.yaml`, `safety.yaml`, `boundaries.yaml`, `explanations.yaml`) to prevent text-matching flakiness.
- **`$matchType`** is valid only inside `tool_calls[].args.<argname>`, never on the `agent:` field. Valid values: `ignore`, `semantic`, `contains`, `regexp` (rule `E011`).
- **Per-conversation session-param overrides** use the field `session_parameters:` (Pydantic `Conversation.session_parameters`). The top-level `common_session_parameters:` is a different field and only valid at the document root (Pydantic `Conversations.common_session_parameters`).
- **Simulations YAML is a top-level *list*** (no `evals:` wrapper, no `scenario:` sub-key). Each entry: `name:`, `tags:`, `steps:` (list of `{goal, success_criteria, response_guide, max_turns, static_utterance, inject_variables}`), optional `session_parameters:` and `expectations:`. Verified against `cxas_scrapi/utils/reporting.py:1597-1607` and `evals/simulations/multi_turn.yaml`'s in-file schema reference comment.

Push Goldens to prod (idempotent on `display_name` — the `cxas push-eval` source proves this in `cxas_scrapi/cli/main.py:push_eval`):

```
cxas push-eval --app-name <PROD_APP> --file evals/goldens/<file>.yaml
```

Run a Goldens suite by tag against prod, gating strictly on the underlying eval status:

```
cxas run --app-name <PROD_APP> --tags <tag> --wait
```

Avoid `--filter-auto-metrics` for standard Golden evaluation YAMLs. The flag turns off the auto-LLM-judge AND only checks top-level `expectations:` lists; we don't author those, so `--filter-auto-metrics` always reports PASS regardless of underlying outcomes (verified in `filter_metrics_and_assess` at `cli/main.py:175-266`). Bare `cxas run --wait` uses the auto-judge correctly. **Caveat:** as of cxas-scrapi 1.2.0 the `cxas run` command prints `FINAL RESULT: FAIL` but still returns exit code 0 in some configurations — until that's fixed upstream, scrape stdout for `FINAL RESULT:` instead of relying on the exit code (the automated CI/CD gate will).

Audio modality re-runs the same Goldens with TTS+STT round-trip. Tag relevant Goldens with `audio_critical` and run with `--modality audio --tags audio_critical`. Audio runs are slow (multiple seconds per turn) — only tag conversations where TTS-specific issues matter.

Run local Simulations + combined report:

```
mkdir -p /tmp/sim_report
cxas evals report --app-name <PROD_APP> --simulation-dir evals/simulations/ --output-dir /tmp/sim_report --include sims --run
```

`--run` actually runs the sims (without it, the command only builds a report from existing data). `--include sims` skips re-running goldens/scenarios. The simulator's user-LLM is non-deterministic and has two known limitations baked into our YAML design: (1) when the agent fires `end_session`, the simulator loop breaks BEFORE the user-LLM can observe the agent's final response, so any goal phrased as "agent ends the session" stays In Progress forever; (2) the simulator's transcript sometimes shows agent messages that look like an echo of the user's prior turn (text-extraction artifact). Workaround pattern (used in `evals/simulations/multi_turn.yaml`): keep step `success_criteria` framed as user-observable actions (something the user knows they said or did) and use `expectations:` for safety / behavioral assertions — those are post-hoc LLM-judged against the full `detailed_trace` (which DOES include the agent's tool calls and actual text), bypassing both bugs.

`cxas push-eval` is **Goldens-only** (uses `update_evaluation`); Simulations stay local. `cxas push` is **upsert-only** for everything; deletions need direct CES API calls — see `scripts/delete_orphan_eval.sh` for the recipe (hostname is `ces.googleapis.com`, regardless of app location, per `cxas_scrapi/core/common.py:_get_client_options`).

`cxas pull` mirrors prod evals into `cxas_app/Casino_Concierge/evaluations/` as JSON-per-conversation. That directory is in `.gitignore` because `evals/goldens/*.yaml` is the single source of truth — committing the pulled JSON would create two parallel copies of every Golden.

### Skills available in this repo

Two skill bundles live under `.agents/skills/`, frozen as snapshots of upstream cxas-scrapi:

**`cxas-agent-foundry`** — End-to-end GECX agent lifecycle (Build / Run / Debug routes). Sub-skills are loaded by Claude Code or Gemini CLI on demand via the bundle's `SKILL.md` routing table.

**Routing override for the Casino Concierge:** the bundle's `SKILL.md` routes "edit instructions / tweak a tool / fix the greeting" → Build flow (full PRD-to-agent ceremony). For *this* agent (which already exists), routine prompt edits stay in the **Deployment workflow** above (pull → edit → lint → push → smoke-test). The Build skill is for greenfield agents only. The Run + Debug routes are useful as-is.

Six sub-agents available, dispatched via the Agent tool with the contents of `.agents/skills/cxas-agent-foundry/agents/<name>.md` as the prompt:

| Sub-agent | When to reach for |
|---|---|
| `lint-fixer.md` | Mechanical lint cleanup. Never run `cxas lint` on the main thread; dispatch this. |
| `eval-writer.md` | Generate evals for one entire eval type at once (all goldens, all sims). |
| `triage-failure.md` | Diagnose ONE failing eval. Fan out for the top-N failures in parallel. |
| `tdd-writer.md` | Reverse-engineer a TDD from an existing agent OR draft from PRD. |
| `scaffolder.md` | Bulk-generate all agent code from an APPROVED TDD. Greenfield only. |
| `coverage-analyst.md` | Generate a full eval coverage report against an agent's architecture. |

**`cxas-sim-eval`** — Converts CXAS golden evaluations to SCRAPI SimulationEvals test cases. We currently hand-author Simulations from Goldens; this skill could automate that pass.

**Coexistence with general workflow skills:** the cxas skills are domain-specific (CES agent lifecycle), whereas general agent workflow skills (brainstorming, writing plans, debugging, TDD) are workflow-focused. They complement each other.

**Greenfield setup script (`setup.sh`) is not for this repo.** The bundle's `scripts/setup.sh` looks for cxas-scrapi source in a parent directory and installs it editable. We install cxas-scrapi from PyPI and already have a virtualenv at `.venv/`. Don't run `setup.sh` here.

**Updating the bundle later:** run `cxas init` in a throwaway worktree, `diff -r` against the current repo, cherry-pick changes inside `.agents/skills/`, and ignore changes to `gecx-config.json` / `AGENTS.md` / `.gitignore` / settings.json files unless the change is genuinely wanted.

### Hooks & settings

Three hooks from the cxas-agent-foundry bundle, wired into both Claude Code (`.claude/settings.json`, `PreToolUse`/`PostToolUse` matcher: `Bash`) and Gemini CLI (`.gemini/settings.json`, `BeforeTool`/`AfterTool` matcher: `run_shell_command`):

| Hook | Triggers on | What it does | Bypass |
|---|---|---|---|
| `pre-agent-push.sh` | command containing `cxas push` | `cxas pull` to a temp dir, `diff -rq` against `cxas_app/`, blocks on drift | Edit settings.json to remove the entry, OR run the push outside the agent CLI |
| `pre-agent-push-lint.sh` | command containing `cxas push` | `cxas lint --json --app-dir .`, blocks on errors | Fix the lint errors (default), or temporarily edit settings.json |
| `post-agent-update.sh` | command containing `update_agent` | Auto-pull + sync-callbacks + reminder | No-op for us (MCP `update_agent` is deprecated) |

The git-layer `.githooks/pre-push` runs `cxas lint` before any `git push`; bypassable with `--no-verify`. Different layer from the cxas-push hooks; both fire as defense in depth.

`gecx-config.json` at repo root anchors all three cxas hooks. Without it, the bundle's `resolve-project.sh` returns empty and the hooks silently no-op.

`.claude/settings.local.json` and `.gemini/settings.local.json` are per-user permission allowlists; gitignored. The team-wide `.claude/settings.json` and `.gemini/settings.json` are committed.

**Drift hook caveat (R1 from the design spec).** The drift hook compares platform state to local state bidirectionally — any difference in either direction blocks the push, including the difference we deliberately created by editing local files in order to push them. If smoke-testing during skills rollout confirmed R1, the hook is unwired in `.claude/settings.json` and `.gemini/settings.json` (the script stays in `.agents/skills/...` because skills are frozen). Check whether `pre-agent-push.sh` is still referenced in the settings files; if not, R1 was confirmed and that's the documented state.

**`cxas pull` overwrites local files.** If the drift hook fires and suggests "Run `cxas pull ...` to merge platform changes first", that command would clobber any local edits. Instead: copy the diverging files to a temp location, run the pull, then merge by hand.

### `gecx-config.json` reference

Anchors the cxas-agent-foundry hooks to our single-project layout. Lives at the repo root.

| Field | Description | When to update |
|---|---|---|
| `gcp_project_id` | The GCP project hosting both the CES app and the GCS audio-eval bucket | Project rotation (rare) |
| `location` | CES app location (`us`); the Vertex AI Search datastore is at `global` and is configured separately via `cxas_app/Casino_Concierge/environment.json` | Region change (rare) |
| `app_name` | Display directory name under `cxas_app/` | Renaming the app |
| `deployed_app_id` | Bare UUID of the deployed app (NOT the full resource path; the SDK constructs the full path automatically) | App rotation |
| `app_dir` | `cxas_app/` (with trailing slash, no `Casino_Concierge/`). Matches `cxas pull`'s output shape so the drift hook can `diff -rq` cleanly. | Restructuring the app dir layout |
| `model` | LLM the agent uses (`gemini-3.1-flash-live` for audio) | Model upgrade |
| `modality` | `audio` or `text` | Modality switch |
| `default_channel` | Same value as `modality` | Same as modality |
| `gcs_bucket` | Bucket for audio eval recordings (`gs://bigquery-demo-396708-cxas-audio-evals`) | Bucket rotation |

We do **not** use the bundle's `.active-project` pointer file; it's for the bundle's multi-project workspace pattern, and we're a single project (gecx-config.json lives at repo root, found by the resolver via its CWD-backwards-compat path).

### MCP `update_agent` — deprecated

The `mcp_customer-experience-agent-studio_update_agent` MCP tool was the previous deploy mechanism (prior to the current workflow) and is technically still available. **Do not use it for new changes** — it bypasses the cxas source of truth and produces drift between local files and prod. Reserve it only as a worst-case rollback path if `cxas push` itself becomes unusable.

## Data pipeline commands

The Python scripts have no test/build system — they're one-shot ETL. Run from repo root with the venv active:

```bash
source .venv/bin/activate
python scripts/parse_games_to_csv.py   # scrapes casino.oliviervg.com JS bundle → data/processed/games_catalog.csv
python scripts/update_games_md.py      # regenerates data/raw/games.md from the CSV (human-readable catalog)
```

The scraper depends on the minified JS variable names `eU` and `fU` in the casino's bundle — if the upstream build changes those identifiers, the regex extraction breaks. Re-derive from the new bundle.

## Environment

`.env` holds `GOOGLE_CLOUD_PROJECT="bigquery-demo-396708"` and `GOOGLE_CLOUD_LOCATION="global"` (used for BigQuery / Vertex AI Search). The `.env` file is gitignored.

The CES app itself lives in a different location: `projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8` (display name `Casino Concierge`). All `cxas` commands targeting the agent require `--location us`. The Vertex AI Search datastore stays at `global` and is referenced via `$env_var` resolution from `cxas_app/Casino_Concierge/environment.json` — never hard-coded into tool definitions.
