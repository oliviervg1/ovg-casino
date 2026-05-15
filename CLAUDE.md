# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Configuration and supporting assets for the **OVG Casino Concierge**, a virtual assistant deployed on **Google Cloud Customer Engagement Suite (CX Agent Studio)**. There is no application server here — the agent runtime lives in CX Agent Studio. This repo holds the agent's full configuration (instructions, tools, guardrails, evaluations) under `cxas_app/`, the data pipeline that feeds its game search, and the frontend snippet that renders rich UI cards in the embedded `ces-messenger` widget.

## cxas-scrapi tooling

The canonical CLI for managing the agent is [`cxas-scrapi`](https://googlecloudplatform.github.io/cxas-scrapi/stable/). It pulls/pushes the entire CES app as files on disk under `cxas_app/Casino_Concierge/`, replacing the older MCP-driven `update_agent` workflow. See **Deployment workflow** below for the full loop. The retrofit roadmap (lint, evals, CI/CD, Claude Code skills) is tracked in `docs/superpowers/specs/2026-05-15-cxas-scrapi-retrofit-design.md`; only Phase A (foundation) has shipped so far.

## Architecture (the parts that span multiple files)

The agent has three tightly coupled surfaces. Changes to one usually require coordinated changes to the others:

1. **Agent definition** — `cxas_app/Casino_Concierge/` is the source of truth, pulled from CES via `cxas pull` and pushed back via `cxas push`. Key files inside it:
   - `agents/Casino_Concierge/instruction.txt` — the system prompt itself. XML-tagged sections (`<role>`, `<persona>`, `<constraints>`, `<taskflow>`, `<examples>`). All persona/tool-usage/tone changes start here.
   - `app.json` — app-level config: voice, multilingual locales, model, guardrails attached, logging settings.
   - `environment.json` — env-specific values that the tool definitions reference via `$env_var` placeholders (e.g., the Vertex AI Search engine + datastore resource paths).
   - `tools/{search_available_games,display_game_widget}/<name>.json` — tool definitions.
   - `guardrails/{Prompt,Safety}_Guardrail_*/<name>.json` — CES native guardrails attached to the app (already configured in prod).
   - `evaluations/<name>/<name>.json` — CES native evaluations (one starter eval exists; full eval suite comes in Phase C of the retrofit).
2. **Game catalog data pipeline** — game data is scraped from the casino frontend JS bundle, written to `data/processed/games_catalog.csv` (matches `data/processed/schema.json`, includes a `url` column), loaded into BigQuery (`ovg_casino.games_inventory`), then indexed by a Vertex AI Search Data Store (`ovg_casino_games_catalog`) + Engine (`ovg_casino_games_engine`). The agent calls a Datastore Tool named `search_available_games` against this index. A human-readable mirror lives at `data/raw/games.md` (regenerated from the CSV; includes direct game URLs).
3. **Frontend rich-UI rendering** — `scripts/frontend_widget.html` is a snippet embedded on `casino.oliviervg.com`. It registers a Handlebars template named `game_carousel` with `ces-messenger`, and the agent's `display_game_widget` Client Function Tool emits `{template_id: "game_carousel", context: {games: [...]}}` which `ces-messenger` intercepts and renders. The same snippet also passes `user_first_name` from Firebase auth into the agent via `setQueryParameters`, and listens for `ces-end-session` to close/clear the chat when the agent calls `end_session`.

Two built-in tools the agent uses without a tool definition: `end_session` (with `reason="customer_query_ended"` or `reason="gambling_concerns"`).

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
- **`end_session` positioning:** When the user says goodbye or expresses gambling distress, the agent must execute `end_session` immediately in the same turn — do not ask follow-up questions first. Examples in `<examples>` enforce this pattern.

## Deployment workflow

1. Activate the venv: `source venv/bin/activate`. cxas-scrapi is installed there (`pip show cxas-scrapi`).
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
5. Smoke-test on `https://casino.oliviervg.com`. Until Phase D's CI ships, this is the only behavioral safety net — UI/agent changes are not "done" until exercised in a browser.
6. If game data changes: re-run the scraper, reload BigQuery (`ovg_casino.games_inventory`), trigger Vertex AI Search re-import. (Unchanged from prior workflow.)
7. Commit and push to a feature branch and open a PR. Phase A established the PR-based workflow; once Phase D's CI is in place, PRs will create ephemeral CES apps and run the full eval matrix automatically.

Project is on `main`; commit author is `Olivier Van Goethem <ovg@google.com>`.

### CLI gotchas worth knowing

- `cxas pull` uses `--target-dir`, not `--output-dir`.
- `cxas push` uses `--app-dir` (hyphen, not underscore) and has no `--dry-run` flag — use `cxas ci-test` to verify safely.
- `cxas push --to <resource>` targets an existing app; `--app-name` is a different v1beta API path.
- `cxas apps` is a parent command; use `cxas apps list` or `cxas apps get`.
- `cxas delete` uses `--app-name <full-resource>`, not a positional argument.
- `cxas push` and `cxas ci-test` both accept `--env-file` to inject `environment.json` (which holds the per-environment Vertex AI Search engine/datastore paths via `$env_var` resolution). Always pass it.
- `cxas lint` reads `cxaslint.yaml` from the value of `--app-dir` (treats it as project root). Our `cxaslint.yaml` lives at repo root and sets `app_dir: cxas_app/Casino_Concierge`, so the canonical invocation is plain `cxas lint` from the repo root (NOT `cxas lint --app-dir cxas_app/Casino_Concierge`, which would look for cxaslint.yaml inside the app dir and miss it).

### Linting

`cxas lint` (run from repo root, no flags needed) checks the agent against the cxas-scrapi linter ruleset. Configuration lives in `cxaslint.yaml` at repo root — severity overrides only, with inline rationale comments for each suppression.

The pre-push git hook in `.githooks/pre-push` enforces this on every `git push`; bypassable with `--no-verify` for emergencies. Phase D will add a non-bypassable CI gate.

Re-enable any rule by removing its line from `cxaslint.yaml`. The hook uses cxas's exit code (non-zero = errors found), so any new rule violations introduced by an edit will block the push.

### MCP `update_agent` — deprecated

The `mcp_customer-experience-agent-studio_update_agent` MCP tool was the previous deploy mechanism (pre-Phase A) and is technically still available. **Do not use it for new changes** — it bypasses the cxas source of truth and produces drift between local files and prod. Reserve it only as a worst-case rollback path if `cxas push` itself becomes unusable.

## Data pipeline commands

The Python scripts have no test/build system — they're one-shot ETL. Run from repo root with the venv active:

```bash
source venv/bin/activate
python scripts/parse_games_to_csv.py   # scrapes casino.oliviervg.com JS bundle → data/processed/games_catalog.csv
python scripts/update_games_md.py      # regenerates data/raw/games.md from the CSV (human-readable catalog)
```

The scraper depends on the minified JS variable names `eU` and `fU` in the casino's bundle — if the upstream build changes those identifiers, the regex extraction breaks. Re-derive from the new bundle.

## Environment

`.env` holds `GOOGLE_CLOUD_PROJECT="bigquery-demo-396708"` and `GOOGLE_CLOUD_LOCATION="global"` (used for BigQuery / Vertex AI Search). The `.env` file is gitignored.

The CES app itself lives in a different location: `projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8` (display name `Casino Concierge`). All `cxas` commands targeting the agent require `--location us`. The Vertex AI Search datastore stays at `global` and is referenced via `$env_var` resolution from `cxas_app/Casino_Concierge/environment.json` — never hard-coded into tool definitions.
