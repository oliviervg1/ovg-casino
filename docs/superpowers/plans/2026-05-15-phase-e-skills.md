# Phase E: Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the dropped-in `cxas-agent-foundry` and `cxas-sim-eval` skill bundles as canonical workflow surfaces, anchor them to our single-project layout via a root-level `gecx-config.json`, wire the bundle's hooks into Claude Code and Gemini CLI, and consolidate `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` into a single canonical `AGENTS.md` (with `CLAUDE.md` and `GEMINI.md` as symlinks). One PR.

**Architecture:** Skills under `.agents/skills/` are frozen — no edits inside. All adaptation happens in surrounding configuration: `gecx-config.json` (new), `.claude/settings.json` + `.gemini/settings.json` (kept verbatim from the drop except for one `skills.disabled` removal in Gemini), `.githooks/pre-push` (path bump only), `cxaslint.yaml` (three small additions copied from the pristine template), `.gitignore` (three additions). The dropped-in `AGENTS.md` and `GEMINI.md` get fully overwritten/replaced.

**Tech Stack:** cxas-scrapi 1.2.0 (in `.venv/`), gcloud / `gcloud storage` for GCS bucket creation, bash + jq for hook wiring, plain markdown + relative symlinks (`ln -sfr`).

**Reference spec:** [`docs/superpowers/specs/2026-05-15-phase-e-skills-design.md`](../specs/2026-05-15-phase-e-skills-design.md). The risk analysis in §9 (especially R1 — drift hook may be a deny-all gate) is load-bearing for Task 9.

---

## File Structure

**Files created:**
- `gecx-config.json` (repo root) — anchor for the bundle's hook resolver. ~10 lines JSON.
- `AGENTS.md` (repo root) — canonical project doc consolidating CLAUDE.md, the dropped-in AGENTS.md, and GEMINI.md. Built from current CLAUDE.md + three new sections (§9 Skills available in this repo, §10 Hooks & settings, §11 `gecx-config.json` reference).

**Files modified:**
- `.gitignore` — three new lines (`.claude/settings.local.json`, `.gemini/settings.local.json`, `.active-project`).
- `.githooks/pre-push` — `venv/bin/activate` → `.venv/bin/activate` (two occurrences in the script).
- `cxaslint.yaml` — add `evals_dir: evals/`, an `ignore:` block, and a `--list-rules` pointer comment.
- `.gemini/settings.json` — remove the entire top-level `skills` key.
- `FUTURE_ENHANCEMENTS.md` §4.6 — mark Phase E as shipped.

**Files replaced:**
- `CLAUDE.md` — symlink → `AGENTS.md` (loses its content; new AGENTS.md absorbs it).
- `GEMINI.md` — symlink → `AGENTS.md` (loses the dropped-in mandate content; the zero-warnings policy is preserved in the new AGENTS.md §"Linting").

**Files newly tracked (currently untracked from the bundle drop):**
- `.agents/` (the entire dropped-in skill bundle; ~100 files).
- `.claude/settings.json` (kept verbatim from the drop).
- `.gemini/settings.json` (kept from the drop with the `skills` key removed).

**Files deleted:**
- `examples/` directory (redundant with our tuned `cxaslint.yaml`).
- `venv/` directory (replaced by `.venv/` — recreated from scratch).
- `.agents/skills/**/__pycache__/` and `*.pyc` files (~42 items; would be gitignored anyway, but should not sit in the working tree).
- The dropped-in `AGENTS.md` and dropped-in `GEMINI.md` get **overwritten** by step 6 (new AGENTS.md) and step 7 (symlink), not separately deleted.

**Files outside the repo (modified):**
- `/home/admin_/.claude/projects/-home-admin--ovg-casino-concierge/memory/project_cxas_retrofit_roadmap.md` — mark Phase E as shipped.

---

## Constants used throughout

- `REPO_ROOT` = `/home/admin_/ovg-casino-concierge`
- `PROD_APP_RES` = `projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8`
- `PROD_APP_ID` = `c4242f9c-3b93-4c92-a69c-a035daabc0c8` (the bare UUID for `gecx-config.json`)
- `PROJECT_ID` = `bigquery-demo-396708`
- `LOCATION` = `us`
- `BUCKET` = `gs://bigquery-demo-396708-cxas-audio-evals`
- `BRANCH` = `feat/phase-e-skills`

---

## Task 1: Pre-flight + branch creation

**Files:** none (read-only verification + branch creation).

- [ ] **Step 1: Confirm clean main + sync with origin**

```bash
cd /home/admin_/ovg-casino-concierge
git status
git fetch origin
git log --oneline origin/main -3
```

Expected: clean tree (apart from the untracked bundle drop), on `main`, local matches `origin/main` (last commit should be the Phase E spec commit `377956c docs: add Phase E implementation design (skills)`). If behind, `git pull origin main`.

- [ ] **Step 2: Activate the existing venv + confirm cxas works**

```bash
source venv/bin/activate
cxas --version
which cxas
```

Expected: cxas version (e.g., `1.2.0`); `which cxas` returns a path under `venv/`. We will throw this venv away in Task 4 — confirming it works now is just a baseline.

- [ ] **Step 3: Confirm `gcloud` is authenticated for the right project**

```bash
gcloud auth list
gcloud config get-value project
```

Expected: account active, project = `bigquery-demo-396708`. If wrong project: `gcloud config set project bigquery-demo-396708`.

- [ ] **Step 4: Create the feature branch**

```bash
git checkout -b feat/phase-e-skills
git status
```

Expected: switched to new branch; `git status` still shows the untracked `.agents/`, `.claude/`, `.gemini/`, `AGENTS.md`, `GEMINI.md`, `examples/` from the drop.

---

## Task 2: Provision the GCS bucket for audio eval recordings

**Files:** none (creates a GCS bucket; no repo changes).

This is a one-shot infrastructure step. The bucket is referenced by the new `gecx-config.json` (Task 5) and is required by the bundle's audio-recording-based eval flow. Our existing `cxas run --modality audio` does not need it, but creating it now means the bundle's flows work out of the box.

- [ ] **Step 1: Check whether the bucket already exists**

```bash
gcloud storage buckets describe gs://bigquery-demo-396708-cxas-audio-evals 2>&1 | head -5
```

Expected: either bucket info (skip Step 2) or `ERROR: ... does not exist`.

- [ ] **Step 2: Create the bucket (skip if Step 1 found it)**

```bash
gcloud storage buckets create gs://bigquery-demo-396708-cxas-audio-evals \
  --project=bigquery-demo-396708 \
  --location=us \
  --uniform-bucket-level-access
```

Expected: `Creating gs://bigquery-demo-396708-cxas-audio-evals/...` then no error.

- [ ] **Step 3: Confirm the bucket exists and is in the right project + location**

```bash
gcloud storage buckets describe gs://bigquery-demo-396708-cxas-audio-evals \
  --format='value(project_number,location,uniformBucketLevelAccess.enabled)'
```

Expected: project number for `bigquery-demo-396708`, location `US`, uniform access `True`.

- [ ] **Step 4: No commit (infrastructure only)**

---

## Task 3: Clean working tree of unwanted artifacts

**Files:**
- Delete: `.agents/skills/**/__pycache__/` (3 directories, ~21 `.pyc` files inside)
- Delete: `examples/cxaslint.yaml` and `examples/` directory

The dropped-in `AGENTS.md` and `GEMINI.md` files stay in place for now — Task 6 overwrites `AGENTS.md` and Task 7 replaces `GEMINI.md` with a symlink.

- [ ] **Step 1: Inventory before deletion**

```bash
find .agents -name __pycache__ -type d
find .agents -name "*.pyc"
ls examples/
```

Expected: 3 `__pycache__` directories, ~21 `.pyc` files, and `examples/cxaslint.yaml` in the listing.

- [ ] **Step 2: Delete `__pycache__` directories under `.agents/`**

```bash
find .agents -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
```

The `2>/dev/null || true` suppresses `find: '...': No such file or directory` complaints from `find` after it removes a directory it was about to recurse into. The directories are gone either way.

- [ ] **Step 3: Delete any remaining `.pyc` files (defensive — should be empty)**

```bash
find .agents -type f -name "*.pyc" -delete
```

- [ ] **Step 4: Delete `examples/`**

```bash
rm -rf examples/
```

- [ ] **Step 5: Verify cleanup**

```bash
find .agents -name __pycache__ -o -name "*.pyc"
[ ! -d examples ] && echo "examples/ is gone"
```

Expected: first command produces no output; second prints `examples/ is gone`.

- [ ] **Step 6: No commit (the deleted items were untracked; nothing to commit)**

---

## Task 4: Stage and commit the skills bundle as-is

**Files:**
- Add to git: `.agents/` (the entire tree, with the cleanups from Task 3 already applied).

The bundle is committed as a single atomic change. The contents are frozen — we do not edit anything inside `.agents/skills/`.

- [ ] **Step 1: Verify the working tree state before staging**

```bash
git status --short | head -20
```

Expected: `.agents/`, `.claude/`, `.gemini/`, `AGENTS.md`, `GEMINI.md` all listed as `??` (untracked). `examples/` should be gone.

- [ ] **Step 2: Stage just the `.agents/` directory**

```bash
git add .agents/
```

- [ ] **Step 3: Verify what was staged**

```bash
git status --short | head -10
git diff --cached --stat | tail -5
```

Expected: ~100 files staged under `.agents/`. `git diff --cached --stat` shows the file count and total insertion count (should be in the thousands).

- [ ] **Step 4: Confirm no `__pycache__` or `.pyc` slipped in**

```bash
git diff --cached --stat | grep -E "__pycache__|\.pyc" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: adopt cxas-agent-foundry + cxas-sim-eval skill bundles (Phase E)

Snapshot of upstream cxas-scrapi's skill bundles, dropped into the working
tree by a previous `cxas init`-style run. Skills frozen here as-is — no
edits inside .agents/skills/. Bundle includes:

- cxas-agent-foundry: Build/Run/Debug lifecycle skill with six sub-agents,
  ~40 scripts, project template, three hook scripts.
- cxas-sim-eval: golden→simulation converter.

Adaptation to our single-project layout (gecx-config.json, hook wiring,
doc consolidation) ships in subsequent commits.

See docs/superpowers/specs/2026-05-15-phase-e-skills-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds (will trigger the existing `.githooks/pre-push` only on `git push`, not on `git commit`; `cxas lint` is unaffected by adding `.agents/`).

---

## Task 5: Recreate venv at `.venv/`, update infrastructure (hook + gitignore + cxaslint.yaml)

**Files:**
- Delete: `venv/` (the existing virtualenv)
- Create: `.venv/` (fresh virtualenv)
- Modify: `.githooks/pre-push` (two `venv/` → `.venv/` substitutions; one error message)
- Modify: `.gitignore` (three additions)
- Modify: `cxaslint.yaml` (three additions per spec §7)

This is the "infrastructure" commit — everything that has to change together so the toolchain stays consistent. The venv rename and `.githooks/pre-push` edit must land together: pushing with one without the other would break the git push hook.

- [ ] **Step 1: Delete the old venv and create a fresh one at `.venv/`**

```bash
deactivate 2>/dev/null || true
rm -rf venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install cxas-scrapi --quiet
```

Expected: each command succeeds without error. `pip install` may take ~30s.

- [ ] **Step 2: Verify cxas works in `.venv/`**

```bash
cxas --version
which cxas
```

Expected: cxas version printed (matching what Task 1 saw); `which cxas` returns a path under `.venv/`.

- [ ] **Step 3: Update `.githooks/pre-push` to source `.venv/`**

The current file checks for `venv/bin/activate` and sources it. Two substitutions are needed: the existence check and the source line. The error message also references `venv` and a stale `python3 -m venv venv` instruction — update both.

```bash
# Read it first to see exact current content
cat .githooks/pre-push
```

Make these three exact edits to `.githooks/pre-push`:

1. Replace `if [ ! -f venv/bin/activate ]; then` with `if [ ! -f .venv/bin/activate ]; then`.
2. Replace the error message line `  echo "pre-push: no venv/ found — run 'python3 -m venv venv && pip install cxas-scrapi' (see README)." >&2` with `  echo "pre-push: no .venv/ found — run 'python3 -m venv .venv && source .venv/bin/activate && pip install cxas-scrapi' (see AGENTS.md)." >&2`.
3. Replace `source venv/bin/activate` with `source .venv/bin/activate`.

- [ ] **Step 4: Verify the hook edits**

```bash
grep -n "venv\|\.venv" .githooks/pre-push
```

Expected output (line numbers may differ slightly):
```
13:if [ ! -f .venv/bin/activate ]; then
14:  echo "pre-push: no .venv/ found — run 'python3 -m venv .venv && source .venv/bin/activate && pip install cxas-scrapi' (see AGENTS.md)." >&2
19:source .venv/bin/activate
```

No bare `venv/` references should remain.

- [ ] **Step 5: Smoke-test the hook by sourcing the venv and running `cxas lint`**

```bash
source .venv/bin/activate
cxas lint
echo "Exit: $?"
```

Expected: lint passes clean (exit 0). Some `info`-severity output is OK (we deliberately downgrade I004 to info).

- [ ] **Step 6: Add three entries to `.gitignore`**

Append to the existing `.gitignore` (do NOT replace — preserve everything that's already there). The additions should go in a logical place; recommended position is after the existing `# Project Specific` section.

The three lines to add (with a comment explaining each):

```
# Per-user Claude Code / Gemini CLI permission files (.local.json variants)
.claude/settings.local.json
.gemini/settings.local.json

# cxas-agent-foundry's optional pointer file for multi-project workspaces.
# We're a single project (gecx-config.json lives at repo root) and don't
# use this; gitignored so a stray creation by `setup.sh` doesn't litter.
.active-project
```

- [ ] **Step 7: Verify `.gitignore` works for the new entries**

```bash
git check-ignore -v .claude/settings.local.json .gemini/settings.local.json .active-project 2>&1
```

Expected: each path is reported as ignored, with the matching `.gitignore` rule shown.

```bash
git status --short | grep settings.local.json
```

Expected: empty output (`.claude/settings.local.json` is no longer reported as untracked because it's now ignored).

- [ ] **Step 8: Update `cxaslint.yaml` per spec §7**

Three additions to the existing `cxaslint.yaml`. Do NOT touch the existing rule overrides — just add the new lines.

After the existing `app_dir: cxas_app/Casino_Concierge` line (around line 9), add:

```yaml

# Path to the evals directory (default; stated explicitly to lock the contract).
evals_dir: evals/
```

After the closing of the `rules:` block (i.e., at the end of the file), add:

```yaml

# Run `cxas lint --list-rules` to see all available rules and their default
# severities. The full catalog is intentionally NOT mirrored here (decay risk).

# Files the linter should not scan.
ignore:
  - "**/__pycache__/**"
  - "**/test_*.py"
```

- [ ] **Step 9: Verify the cxaslint additions parse and lint still passes**

```bash
python3 -c "import yaml; yaml.safe_load(open('cxaslint.yaml'))"
cxas lint
echo "Exit: $?"
```

Expected: YAML parses (no error); `cxas lint` exits 0 (clean).

- [ ] **Step 10: Commit infrastructure**

```bash
git add .gitignore .githooks/pre-push cxaslint.yaml
git status --short
git commit -m "$(cat <<'EOF'
chore: rename venv → .venv/ and align lint + ignore for skills bundle (Phase E)

Aligns with the cxas-agent-foundry bundle's expectations:
- venv/ → .venv/ (matches the bundle's setup.sh and modern Python tooling).
  The git pre-push hook is updated to source the new path; the README/AGENTS
  doc updates land in a later commit.
- cxaslint.yaml gains an explicit evals_dir, an ignore block (defensive
  against the .agents/ tree's __pycache__ if it ever returns), and a pointer
  to `cxas lint --list-rules` as the canonical rule catalog.
- .gitignore excludes per-user .claude/settings.local.json and
  .gemini/settings.local.json, plus .active-project (unused — we're a
  single project, the bundle's pointer file is for multi-project workspaces).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds; git push hook will fire on the eventual push and verify itself.

---

## Task 6: Anchor and wire — write `gecx-config.json` + adopt settings.json files

**Files:**
- Create: `gecx-config.json` (repo root)
- Add to git: `.claude/settings.json` (kept verbatim from the drop)
- Modify: `.gemini/settings.json` (remove top-level `skills` key)

This is the "wiring" commit. Once it lands, the cxas-agent-foundry hooks become live: they will fire on every Bash command, no-op unless the command matches `cxas push` / `update_agent`, and (for the matching cases) they have a `gecx-config.json` to consult.

- [ ] **Step 1: Write `gecx-config.json` at repo root**

Create `gecx-config.json` with exactly this content:

```json
{
  "gcp_project_id": "bigquery-demo-396708",
  "location": "us",
  "app_name": "Casino_Concierge",
  "deployed_app_id": "c4242f9c-3b93-4c92-a69c-a035daabc0c8",
  "app_dir": "cxas_app/",
  "model": "gemini-3.1-flash-live",
  "modality": "audio",
  "default_channel": "audio",
  "gcs_bucket": "gs://bigquery-demo-396708-cxas-audio-evals"
}
```

Field-level rationale (do NOT include in the file; this is for the implementer):
- `app_dir: "cxas_app/"` (with trailing slash, no `Casino_Concierge/`) matches `cxas pull`'s output shape so the drift hook can `diff -rq tmp_dir app_dir` against directory contents that both contain `Casino_Concierge/`.
- `deployed_app_id` is the bare UUID, not the full resource path — per the bundle's CRITICAL FORMATTING note in `.agents/skills/cxas-agent-foundry/assets/project-template/gecx-config.json`. The SDK constructs the full path automatically.

- [ ] **Step 2: Verify `gecx-config.json` parses**

```bash
jq . gecx-config.json
echo "Exit: $?"
```

Expected: pretty-printed JSON identical to what was written; exit 0.

- [ ] **Step 3: Verify the resolver finds the config**

```bash
bash -c 'source .agents/skills/cxas-agent-foundry/scripts/resolve-project.sh && resolve_project_dir'
```

Expected: outputs `/home/admin_/ovg-casino-concierge` (the CWD; matches the resolver's "CWD has gecx-config.json" path).

- [ ] **Step 4: Edit `.gemini/settings.json` to remove the `skills` key**

Read the current file:

```bash
cat .gemini/settings.json
```

The current shape includes a top-level `"skills": { "disabled": ["cxas-sim-eval"] }`. Remove the entire `skills` key (not just the `disabled` sub-key — leaving `"skills": {}` would be an empty orphan).

After the edit, the file should contain `tools` and `hooks` top-level keys only — no `skills` key.

- [ ] **Step 5: Verify the `skills` key is gone and the rest is intact**

```bash
jq . .gemini/settings.json
jq 'keys' .gemini/settings.json
jq '.skills' .gemini/settings.json
```

Expected: file pretty-prints; top-level keys are `["hooks", "tools"]` (alphabetical order); `.skills` returns `null`.

- [ ] **Step 6: Stage and commit**

```bash
git add gecx-config.json .claude/settings.json .gemini/settings.json
git status --short
git commit -m "$(cat <<'EOF'
feat: add gecx-config.json + wire cxas-agent-foundry hooks (Phase E)

gecx-config.json at the repo root anchors the bundle's hook resolver
via its CWD-backwards-compat path. Single-project repo, so .active-project
and per-subdir gecx-config.json (the bundle's multi-project patterns)
do not apply.

.claude/settings.json adopted verbatim from the drop. .gemini/settings.json
adopted with one change: top-level `skills` key removed (was disabling
cxas-sim-eval; we want all skills available).

The hooks (pre-agent-push.sh drift detection, pre-agent-push-lint.sh,
post-agent-update.sh) now fire on every Bash command and no-op unless the
command matches `cxas push` / `update_agent`. R1 in the design spec
(drift hook may be a deny-all gate) is smoke-tested in a later commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds.

---

## Task 7: Write the new canonical `AGENTS.md`

**Files:**
- Modify (overwrite): `AGENTS.md` — replaces the dropped-in workspace-flavored content with our consolidated doc.

This is the largest single edit. The new `AGENTS.md` is built from the current `CLAUDE.md` content (which is the richest of the three), with three new sections (§ "Skills available in this repo", § "Hooks & settings", § "`gecx-config.json` reference") and small edits throughout for the venv rename and the new lint policy framing.

- [ ] **Step 1: Read the current `CLAUDE.md` for reference**

```bash
cat CLAUDE.md
```

Use the output as the source-of-truth for the unchanged sections in the new `AGENTS.md`.

- [ ] **Step 2: Overwrite `AGENTS.md` with the new canonical content**

Write `AGENTS.md` with exactly this content:

````markdown
# AGENTS.md

This file provides guidance to coding-agent CLIs (Claude Code, Gemini CLI, Codex) when working with code in this repository. `CLAUDE.md` and `GEMINI.md` are symlinks to this file — edit only `AGENTS.md`; the other two always reflect it.

## What this repo is

Configuration and supporting assets for the **OVG Casino Concierge**, a virtual assistant deployed on **Google Cloud Customer Engagement Suite (CX Agent Studio)**. There is no application server here — the agent runtime lives in CX Agent Studio. This repo holds the agent's full configuration (instructions, tools, guardrails, evaluations) under `cxas_app/`, the data pipeline that feeds its game search, and the frontend snippet that renders rich UI cards in the embedded `ces-messenger` widget.

## cxas-scrapi tooling

The canonical CLI for managing the agent is [`cxas-scrapi`](https://googlecloudplatform.github.io/cxas-scrapi/stable/). It pulls/pushes the entire CES app as files on disk under `cxas_app/Casino_Concierge/`, replacing the older MCP-driven `update_agent` workflow. See **Deployment workflow** below for the full loop. The retrofit roadmap (lint, evals, CI/CD, Claude Code skills) is tracked in `docs/superpowers/specs/2026-05-15-cxas-scrapi-retrofit-design.md`; **Phases A (foundation), B (lint), C (evals), and E (skills) have shipped — D (CI/CD) remains.**

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

**Lint policy: zero errors, zero warnings.** Any rule downgrade in `cxaslint.yaml` requires a rationale comment plus a follow-up TODO. New violations introduced by an edit must be either fixed at the source or downgraded with a documented rationale (the I004 downgrade with its TODO in `FUTURE_ENHANCEMENTS.md` §4.7 is the pattern); silent downgrades are not acceptable.

Two enforcement layers gate this:
- `.githooks/pre-push` runs `cxas lint` on every `git push` (bypassable with `--no-verify` for emergencies).
- `.claude/settings.json` and `.gemini/settings.json` wire the cxas-agent-foundry's `pre-agent-push-lint.sh` hook, which runs `cxas lint --json` on every `cxas push` from inside Claude Code or Gemini CLI (so an LLM agent issuing the push gets gated too). See § "Hooks & settings" below.

Phase D will add a non-bypassable CI gate.

Re-enable any rule by removing its line from `cxaslint.yaml`. The hook uses cxas's exit code (non-zero = errors found), so any new rule violations introduced by an edit will block the push.

### Evals

Eval YAML lives at `evals/` (project root), with `evals/goldens/*.yaml` for Platform Goldens and `evals/simulations/*.yaml` for Simulations. The cxas-scrapi linter rules `E001`-`E011` only fire on files under those subdirectories.

Schema gotchas the lint won't always catch:

- **Goldens `agent:` field** must be a plain string or list-of-strings (rule `E007` enforces). To assert a tool fires without pinning the agent's text, set `agent: "# silent — <reason>"`. The runtime parser (`cxas_scrapi/utils/eval_utils.py:_process_dataset_turn`) skips the `agentResponse` expectation step whenever the agent string contains the substring `# silent`, so the eval doesn't false-fail on any text the agent actually produces. Without this marker, dropping `agent:` triggers `E008` and the runtime auto-FAILs the turn for "unexpected response".
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

Avoid `--filter-auto-metrics` for Phase C-style YAMLs. The flag turns off the auto-LLM-judge AND only checks top-level `expectations:` lists; we don't author those, so `--filter-auto-metrics` always reports PASS regardless of underlying outcomes (verified in `filter_metrics_and_assess` at `cli/main.py:175-266`). Bare `cxas run --wait` uses the auto-judge correctly. **Caveat:** as of cxas-scrapi 1.2.0 the `cxas run` command prints `FINAL RESULT: FAIL` but still returns exit code 0 in some configurations — until that's fixed upstream, scrape stdout for `FINAL RESULT:` instead of relying on the exit code (Phase D's CI gate will).

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

**Coexistence with superpowers skills:** the cxas skills are domain-specific (CES agent lifecycle); the superpowers skills (brainstorming, writing-plans, debugging, TDD) are workflow. They complement.

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

**Drift hook caveat (R1 from the design spec).** The drift hook compares platform state to local state bidirectionally — any difference in either direction blocks the push, including the difference we deliberately created by editing local files in order to push them. If smoke-testing during Phase E rollout confirmed R1, the hook is unwired in `.claude/settings.json` and `.gemini/settings.json` (the script stays in `.agents/skills/...` because skills are frozen). Check whether `pre-agent-push.sh` is still referenced in the settings files; if not, R1 was confirmed and that's the documented state.

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

The `mcp_customer-experience-agent-studio_update_agent` MCP tool was the previous deploy mechanism (pre-Phase A) and is technically still available. **Do not use it for new changes** — it bypasses the cxas source of truth and produces drift between local files and prod. Reserve it only as a worst-case rollback path if `cxas push` itself becomes unusable.

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
````

- [ ] **Step 3: Verify the new file**

```bash
wc -l AGENTS.md
grep -c "^## \|^### " AGENTS.md
head -3 AGENTS.md
grep -c "venv/" AGENTS.md
grep -c "\.venv/" AGENTS.md
```

Expected: roughly 100+ lines. Section count >= 14 (10 ## + 4-5 ###). Header line is `# AGENTS.md`. Bare `venv/` count = 0 (all venv references should be `.venv/`). `.venv/` count >= 3.

- [ ] **Step 4: Verify both new sections are present and the policy reframing is in §"Linting"**

```bash
grep -n "Skills available in this repo\|Hooks & settings\|gecx-config.json\` reference\|Lint policy: zero errors" AGENTS.md
```

Expected: 4 matches, one per item.

- [ ] **Step 5: No commit yet — Task 8 (symlinks) lands in the same commit**

---

## Task 8: Replace `CLAUDE.md` and `GEMINI.md` with relative symlinks

**Files:**
- Delete: `CLAUDE.md` (current real file with the old standalone content)
- Delete: dropped-in `GEMINI.md` (current real file with the workspace mandates)
- Create: `CLAUDE.md` as relative symlink → `AGENTS.md`
- Create: `GEMINI.md` as relative symlink → `AGENTS.md`

`ln -sfr` overwrites the existing file with a relative symlink in one step. No need to delete first.

- [ ] **Step 1: Confirm `AGENTS.md` exists and is a regular file (not yet a symlink)**

```bash
ls -la AGENTS.md
file AGENTS.md
```

Expected: regular file, ~100+ lines per Task 7.

- [ ] **Step 2: Replace `CLAUDE.md` with a relative symlink**

```bash
ln -sfr AGENTS.md CLAUDE.md
ls -la CLAUDE.md
```

Expected: `CLAUDE.md -> AGENTS.md` in the `ls -la` output.

- [ ] **Step 3: Replace `GEMINI.md` with a relative symlink**

```bash
ln -sfr AGENTS.md GEMINI.md
ls -la GEMINI.md
```

Expected: `GEMINI.md -> AGENTS.md` in the `ls -la` output.

- [ ] **Step 4: Verify both symlinks resolve to the same content as `AGENTS.md`**

```bash
diff AGENTS.md CLAUDE.md && echo "CLAUDE.md == AGENTS.md"
diff AGENTS.md GEMINI.md && echo "GEMINI.md == AGENTS.md"
head -3 CLAUDE.md
```

Expected: both `diff` outputs are empty (followed by the `echo`); `head` returns the AGENTS.md header.

- [ ] **Step 5: Stage and commit the doc consolidation**

```bash
git add AGENTS.md CLAUDE.md GEMINI.md
git status --short
git diff --cached --stat
git commit -m "$(cat <<'EOF'
docs: consolidate CLAUDE.md/AGENTS.md/GEMINI.md into one canonical AGENTS.md (Phase E)

- AGENTS.md is the canonical project doc, built from the prior CLAUDE.md
  with three new sections (§ Skills available in this repo, § Hooks &
  settings, § gecx-config.json reference) and minor edits for the venv
  rename + new lint-policy framing.
- CLAUDE.md and GEMINI.md become relative symlinks → AGENTS.md so all
  three CLI tools (Claude Code, Gemini CLI, Codex) find the same content.
- The dropped-in workspace-flavored AGENTS.md and the GEMINI.md mandates
  are discarded:
  * Workspace description was wrong for this repo (we're a single project).
  * Three of the four GEMINI.md mandates conflicted with the existing
    superpowers workflow or with our actual scripts; the fourth (zero
    warnings) is preserved and reframed in § Linting with a downgrade-
    needs-rationale corollary that matches our existing practice.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds. `git diff --cached --stat` would have shown AGENTS.md as a large insertion, CLAUDE.md as deletion+insertion (because git treats symlink replacement as such), GEMINI.md the same.

---

## Task 9: Smoke-test the drift hook (R1 gate)

**Files (potentially):**
- Possibly modify: `.claude/settings.json` and `.gemini/settings.json` to unwire `pre-agent-push.sh` if R1 is confirmed.

The drift-detection hook's `diff -rq` is bidirectional — any local-vs-platform difference blocks. We need to verify whether normal pushes work or whether the hook is a deny-all gate. The cleanest test is to invoke the hook script directly with a mock JSON input shaped like Claude Code's hook payload, after we've made a local edit that the platform doesn't yet see.

- [ ] **Step 1: Make a trivial local edit to `instruction.txt`**

```bash
echo "" >> cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt
git diff --stat cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt
```

Expected: 1 file changed, 1 insertion (the trailing blank line). This is a no-op behaviorally for the agent (CES strips trailing whitespace), but it creates a real local-vs-platform difference for the hook to detect.

- [ ] **Step 2: Run the drift hook directly with a mock Claude Code stdin**

```bash
source .venv/bin/activate
echo '{"tool_input": {"command": "cxas push --app-dir cxas_app/Casino_Concierge --to projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 --project-id bigquery-demo-396708 --location us"}}' \
  | bash .agents/skills/cxas-agent-foundry/scripts/hooks/pre-agent-push.sh
```

This invokes the hook the same way Claude Code does: stdin = a JSON tool-call payload; output = a JSON decision. The hook will internally `cxas pull` to a temp dir and diff against `cxas_app/`.

Expected outcomes (one of):
- **(a) Hook outputs `{}` (allow):** the drift hook is permissive in our setup. R1 is NOT confirmed — keep the hook wired.
- **(b) Hook outputs JSON containing `"blockToolExecution":true`:** R1 confirmed — every legitimate push will be blocked. Continue with Step 3.

Document the outcome (paste the hook output verbatim into the PR description when it's time to open the PR).

- [ ] **Step 3a (only if outcome was (a) — hook is permissive): revert the cosmetic edit and skip to Task 10**

```bash
git checkout cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt
git status
```

Expected: working tree clean (apart from the as-yet-uncommitted state from Tasks 1-8 that's already committed). Task 9 does not produce a commit if R1 was not confirmed.

- [ ] **Step 3b (only if outcome was (b) — R1 confirmed): unwire the drift hook**

Edit `.claude/settings.json`: remove the entry whose `command` field references `pre-agent-push.sh`. The remaining `PreToolUse` entry for `pre-agent-push-lint.sh` stays, as does the `PostToolUse` block.

Edit `.gemini/settings.json`: remove the entry whose `command` field references `pre-agent-push.sh` (under `hooks.BeforeTool`).

Verify both files still parse and contain the OTHER hooks:

```bash
jq '.hooks' .claude/settings.json
jq '.hooks' .gemini/settings.json
```

Expected: both show the `pre-agent-push-lint.sh` entry; neither shows `pre-agent-push.sh`.

Then revert the cosmetic edit and commit the hook unwiring:

```bash
git checkout cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt
git add .claude/settings.json .gemini/settings.json
git commit -m "$(cat <<'EOF'
fix: unwire pre-agent-push.sh drift hook (Phase E R1)

Smoke-test confirmed R1 from the design spec: the bundle's
pre-agent-push.sh does a bidirectional diff -rq between platform state
and local state, so any normal push (which by definition has local
changes the platform doesn't yet see) gets blocked. Functionally a
deny-all gate.

Removing it from .claude/settings.json and .gemini/settings.json. The
hook script remains in .agents/skills/cxas-agent-foundry/scripts/hooks/
because the skill bundle is frozen as-is; we just don't invoke it.

pre-agent-push-lint.sh and post-agent-update.sh remain wired.

Follow-up: file an upstream cxas-scrapi issue requesting a one-directional
diff (platform-newer-than-local-only) so this hook is usable.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds.

---

## Task 10: Update `FUTURE_ENHANCEMENTS.md` §4.6 to mark Phase E shipped

**Files:**
- Modify: `FUTURE_ENHANCEMENTS.md` (§4.6 Partial Infrastructure as Code — update the cxas retrofit phase status)

- [ ] **Step 1: Read the current §4.6 to find the phase-status sentence**

```bash
grep -n "Phases B (lint), C (evals), D (CI/CD), and E (Claude Code skills)" FUTURE_ENHANCEMENTS.md
```

Expected: matches around line 126 (file is 131 lines). The exact line is in §4.6 "Remaining work" sub-bullet.

- [ ] **Step 2: Edit the matching line to reflect Phase E shipped**

The current line reads:

```
    *   Phases B (lint), C (evals), D (CI/CD with AppVersion pinning), and E (Claude Code skills) of the cxas retrofit. See the spec for details.
```

Replace it with:

```
    *   Phase D (CI/CD with AppVersion pinning) of the cxas retrofit. Phases B, C, and E have shipped. See the spec for details.
```

- [ ] **Step 3: Verify the edit**

```bash
grep -n "Phase D (CI/CD" FUTURE_ENHANCEMENTS.md
grep -n "Phases B (lint)\|and E (Claude Code skills)" FUTURE_ENHANCEMENTS.md
```

Expected: first grep finds the new line; second grep finds nothing (the old phrasing is gone).

- [ ] **Step 4: Commit**

```bash
git add FUTURE_ENHANCEMENTS.md
git diff --cached
git commit -m "$(cat <<'EOF'
docs: mark Phase E (skills) shipped in FUTURE_ENHANCEMENTS.md §4.6

Only Phase D (CI/CD with AppVersion pinning) remains in the cxas-scrapi
retrofit. A, B, C, and E have shipped.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds.

---

## Task 11: Update the project-cxas-retrofit-roadmap memory entry

**Files:**
- Modify: `/home/admin_/.claude/projects/-home-admin--ovg-casino-concierge/memory/project_cxas_retrofit_roadmap.md` (NOT in the repo; auto-memory file).

This is outside the repo — no commit needed. The memory file is loaded into future Claude Code sessions so subsequent conversations correctly reflect the retrofit state.

- [ ] **Step 1: Read the current memory entry**

```bash
cat /home/admin_/.claude/projects/-home-admin--ovg-casino-concierge/memory/project_cxas_retrofit_roadmap.md
```

- [ ] **Step 2: Edit the description, the "shipped" list, and the "remaining" list**

Three edits:

1. **Frontmatter `description`:** change `Phases A + B + C shipped 2026-05-15; D/E remain.` → `Phases A + B + C + E shipped 2026-05-15; D remains.`

2. **Body — "Three phases have shipped" intro:** change to **"Four phases have shipped"** and add a fourth bullet for Phase E:

   ```
   - **Phase E — skills** (commit `<sha>`, PR `#<num>`, 2026-05-15). Adopted cxas-agent-foundry + cxas-sim-eval skill bundles, anchored via root-level `gecx-config.json`, wired hooks, consolidated CLAUDE.md/AGENTS.md/GEMINI.md into a single AGENTS.md with the others as symlinks. Spec: `docs/superpowers/specs/2026-05-15-phase-e-skills-design.md`. Plan: `docs/superpowers/plans/2026-05-15-phase-e-skills.md`. R1 (drift hook deny-all) outcome documented in PR description.
   ```

   Use the actual commit SHA and PR number from Task 12 once known. (If implementing this task before the PR is opened, add a TODO comment and update after.)

3. **Body — "Remaining phases":** remove the `- **E — Skills:**` bullet entirely. The list becomes a single-item list with just `**D — CI/CD:**`.

- [ ] **Step 3: Verify the edits**

```bash
grep -E "Phases.*shipped|Three phases|Four phases|^- \*\*Phase E\*\*|^- \*\*E — Skills:" /home/admin_/.claude/projects/-home-admin--ovg-casino-concierge/memory/project_cxas_retrofit_roadmap.md
```

Expected: hits for `Four phases have shipped`, `Phase E — skills`, and `Phases A + B + C + E shipped`. No hit for the old `Three phases` or `**E — Skills:` lines.

- [ ] **Step 4: No commit (memory files are outside the repo)**

---

## Task 12: Push the branch and open the PR

**Files:** none (only git operations + PR creation).

- [ ] **Step 1: Verify the working tree is clean before pushing**

```bash
git status
git log --oneline main.. -10
```

Expected: clean tree; ~5-6 commits on the branch since main (skills bundle, infra, wiring, doc consolidation, optional R1 unwire, FUTURE_ENHANCEMENTS).

- [ ] **Step 2: Push the branch (the `.githooks/pre-push` hook will fire)**

```bash
git push -u origin feat/phase-e-skills
```

Expected: pre-push hook activates `.venv/`, runs `cxas lint`, exits 0, push proceeds. If lint fails, fix and retry — never use `--no-verify` here.

- [ ] **Step 3: Open the PR**

```bash
gh pr create --title "feat: adopt cxas-agent-foundry skill bundle (Phase E)" --body "$(cat <<'EOF'
## Summary
- Adopts the dropped-in cxas-agent-foundry + cxas-sim-eval skill bundles as canonical workflow surfaces. Skills frozen as-is under `.agents/skills/`.
- Anchors the bundle's hooks to our single-project layout via a new root-level `gecx-config.json`. Hooks (drift detection, cxas-push lint, post-update reminder) wired in `.claude/settings.json` + `.gemini/settings.json`.
- Consolidates CLAUDE.md / AGENTS.md / GEMINI.md into a single canonical `AGENTS.md`, with `CLAUDE.md` and `GEMINI.md` as relative symlinks. Three new sections: § Skills available in this repo, § Hooks & settings, § `gecx-config.json` reference. Zero-warnings policy preserved (reframed in § Linting).
- Renames `venv/` → `.venv/` to match the bundle convention. `.githooks/pre-push` updated. Defense-in-depth: `.githooks/pre-push` gates `git push`; the bundle's `pre-agent-push-lint.sh` gates `cxas push`.
- Provisions GCS bucket `gs://bigquery-demo-396708-cxas-audio-evals` for audio eval recordings.
- Marks Phase E shipped in FUTURE_ENHANCEMENTS.md §4.6.

## R1 smoke-test outcome (drift hook)
<paste the verbatim output of Task 9 Step 2 here, plus a one-line conclusion: "Hook permissive — kept wired" OR "R1 confirmed — hook unwired in commit <sha>">

## Spec & plan
- Design spec: `docs/superpowers/specs/2026-05-15-phase-e-skills-design.md`
- Implementation plan: `docs/superpowers/plans/2026-05-15-phase-e-skills.md`

## Test plan
- [x] `cxas lint` exits 0 from repo root after every commit (verified by .githooks/pre-push)
- [x] `gecx-config.json` parses; `resolve-project.sh` returns the repo root
- [x] `.venv/bin/activate && cxas --version` works
- [x] `cat CLAUDE.md` and `cat GEMINI.md` both return the AGENTS.md content
- [x] `.gemini/settings.json` no longer contains a `skills` key
- [ ] Drift hook smoke test (Task 9) outcome documented above
- [ ] Manual smoke test on https://casino.oliviervg.com — basic conversation still works (the agent itself wasn't touched, but verify end-to-end)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed. Replace the `<paste ...>` placeholder in the body with the actual smoke-test result before clicking through.

- [ ] **Step 4: Update the memory entry's PR/SHA placeholders (if Task 11 was done before the PR)**

If you hit Task 11 before the PR was opened, the memory entry has TODO placeholders for the SHA and PR number. Update them now.

```bash
git log --oneline main..HEAD | head -5
gh pr view --json number --jq .number
```

Then edit the memory entry to replace `<sha>` with the SHA of the `feat: adopt cxas-agent-foundry...` commit (the first commit in the branch — the bundle adoption) and `<num>` with the PR number.

---

## Self-review notes

### Spec coverage check

Walking each section of the spec:

- §1 Goal — covered by the entire plan.
- §2 Why this came up now — context only; no plan task needed.
- §3 Frozen vs adapted vs removed vs renamed surface — covered:
  - Frozen `.agents/skills/`: Task 4 stages it untouched.
  - `gecx-config.json`: Task 6 step 1.
  - `.claude/settings.json` verbatim: Task 6 step 6 (added unmodified).
  - `.gemini/settings.json` minus `skills` key: Task 6 steps 4-5.
  - `.githooks/pre-push` venv path: Task 5 steps 3-4.
  - `.gitignore` additions: Task 5 steps 6-7.
  - `cxaslint.yaml` three additions: Task 5 steps 8-9.
  - `AGENTS.md` rewrite: Task 7.
  - `CLAUDE.md` + `GEMINI.md` symlinks: Task 8.
  - `examples/` removed: Task 3 step 4.
  - `__pycache__` removed: Task 3 steps 2-3.
  - `venv/` → `.venv/`: Task 5 step 1.
- §4 `gecx-config.json` contents: Task 6 step 1 (verbatim copy).
- §5 Hook flow: Task 6 covers the wiring; Task 9 verifies the drift behavior.
- §6 Doc consolidation: Tasks 7 + 8 cover all 14 sections + symlinks. Old GEMINI.md drops handled by symlink overwrite.
- §7 cxaslint.yaml additions: Task 5 step 8.
- §8 Migration sequence: matches the task order here (with Tasks 4 and 5 collapsed because they share infrastructure-commit semantics).
- §9 Risks: R1 covered by Task 9; R2 + R3 documented in AGENTS.md (Task 7).
- §10 Out of scope: documented in plan via what we DON'T touch.
- §11 Acceptance criteria — verified across tasks. Specifically:
  1. `gecx-config.json` exists, parses ✓ (Task 6 steps 1-2)
  2. `.venv/` exists ✓ (Task 5 steps 1-2)
  3. `cxas lint` exits 0 ✓ (Task 5 step 9, Task 12 step 2 hook gate)
  4. `git push` triggers `.githooks/pre-push` ✓ (Task 12 step 2)
  5. `AGENTS.md` exists with all 14 sections; symlinks resolve ✓ (Task 7 step 4, Task 8 step 4)
  6. `.gitignore` excludes the three new entries ✓ (Task 5 step 7)
  7. No `__pycache__` / `.pyc` under `.agents/` ✓ (Task 3 step 5)
  8. `examples/` gone ✓ (Task 3 step 5)
  9. R1 smoke test documented in PR ✓ (Task 9, Task 12 step 3)
  10. `FUTURE_ENHANCEMENTS.md` §4.6 reflects shipped ✓ (Task 10)
  11. Memory entry reflects D as only remaining ✓ (Task 11)

### Placeholder scan

No `TBD` / `TODO` / "implement later" / "similar to Task N" patterns in this plan. The only `TODO` mentions are intentional references to existing documented TODOs (the I004 downgrade follow-up referenced from FUTURE_ENHANCEMENTS.md §4.7) or to a single conditional placeholder in Task 11 step 2 (commit SHA + PR number, which can only be filled in after Task 12 runs).

### Type / name consistency

- Branch name `feat/phase-e-skills` used consistently in Tasks 1, 12.
- Bucket name `gs://bigquery-demo-396708-cxas-audio-evals` used consistently in Task 2 and Task 6 (gecx-config.json).
- `.venv/` (with leading dot) used consistently from Task 5 onward.
- File path `.agents/skills/cxas-agent-foundry/scripts/hooks/pre-agent-push.sh` used consistently in Task 9 + AGENTS.md.

---

## Out of scope (deferred to follow-up PRs)

Repeated from spec §10 for clarity:

- Phase D (CI/CD with GitHub Actions, AppVersion pinning, ephemeral PR apps).
- The five surfaced findings from Phase C (silent `end_session`, fallback themes, underage as distress, distress non-determinism, multilingual override).
- Fixing the I004 downgrade per `FUTURE_ENHANCEMENTS.md` §4.7.
- Refreshing `FUTURE_ENHANCEMENTS.md` §1.2 / §4.5 (already-shipped items mismatched with the doc).
- Wiring the new GCS bucket into `app.json`'s `evaluationAudioRecordingConfig`.
- Filing an upstream cxas-scrapi issue for R1.
