# Phase E: Skills — Design

**Date:** 2026-05-15
**Status:** Approved during brainstorming session; ready for implementation planning.
**Parent spec:** [`2026-05-15-cxas-scrapi-retrofit-design.md`](2026-05-15-cxas-scrapi-retrofit-design.md) §3.5.
**Scope:** Supplementary spec for Phase E of the cxas-scrapi retrofit. Captures the adapt-and-adopt decisions made after a `cxas init`-style skill bundle was dropped into the working tree.

---

## 1. Goal

Adopt the `cxas-agent-foundry` and `cxas-sim-eval` skill bundles as canonical workflow surfaces in this repo, anchored to our single-project layout via a root-level `gecx-config.json`. Wire the bundle's hooks into Claude Code and Gemini CLI. Consolidate `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` into a single canonical `AGENTS.md` so all three CLI tools find the same content. Ship as one PR.

The bundle's contents under `.agents/skills/` are treated as **frozen** — no edits inside. All adaptation happens in surrounding configuration (`gecx-config.json`, `.claude/settings.json`, `.gemini/settings.json`, `.githooks/pre-push`, `cxaslint.yaml`, `.gitignore`) and the consolidated doc.

## 2. Why this came up now

The parent spec §3.5 anticipated this phase as "run `cxas init` once and commit the result, but in a throwaway worktree first — diff against the current repo, then decide what to keep." Someone has now run a `cxas init`-style bundle drop directly into the working tree. The dropped tree includes:

- `.agents/skills/cxas-agent-foundry/` — full Build/Run/Debug skill with six sub-agents, ~40 scripts, project template, three hook scripts.
- `.agents/skills/cxas-sim-eval/` — golden→simulation converter.
- `.claude/settings.json` and `.gemini/settings.json` — wire the three hook scripts into Pre/Post-tool events.
- `AGENTS.md` and `GEMINI.md` at repo root — workspace-flavored description and Gemini-specific mandates.
- `examples/cxaslint.yaml` — pristine cxaslint template.

This spec is the deferred "decide what to keep" pass. The high-level direction (full bundle adopt-and-adapt; keep skills as-is; consolidate docs) was set by the operator at the top of the brainstorm.

## 3. Frozen surface vs adapted surface

**Frozen — no edits inside:**
- `.agents/skills/cxas-agent-foundry/` (all sub-agents, references, scripts, hook scripts, project template assets).
- `.agents/skills/cxas-sim-eval/` (all scripts and SKILL.md).

**Adapted — we author or rewrite:**
- `gecx-config.json` (new, repo root) — the single anchor that makes the bundle's `resolve-project.sh` find "the project" via its CWD-backwards-compat path.
- `.claude/settings.json` — kept verbatim from the drop (hook wiring is correct; activates the moment `gecx-config.json` exists).
- `.gemini/settings.json` — kept from the drop with one edit: remove `skills.disabled: ["cxas-sim-eval"]` so we don't silently disable a skill we're adopting.
- `.githooks/pre-push` — single-line edit: `venv/bin/activate` → `.venv/bin/activate`.
- `.gitignore` — additions: `.claude/settings.local.json`, `.gemini/settings.local.json`, `.active-project`.
- `cxaslint.yaml` — three additions from the pristine template (see §7).
- `AGENTS.md` — fully rewritten as canonical doc (see §6).
- `CLAUDE.md` and `GEMINI.md` — replaced by relative symlinks to `AGENTS.md`.

**Removed before commit:**
- `examples/` — the pristine cxaslint template; superseded by §7's three additions to our root `cxaslint.yaml`.
- `.agents/skills/**/__pycache__/` and `*.pyc` (~42 items) — `.gitignore` would skip them, but they shouldn't sit in the working tree.

**Renamed:**
- `venv/` → `.venv/` to match the bundle's `setup.sh` and modern Python convention. We default to delete-and-recreate (rather than `mv`) to avoid hard-coded absolute paths in any compiled wheels.

## 4. `gecx-config.json` — the anchor

**File:** `gecx-config.json` at repo root.

**Why repo root:** the bundle's `resolve-project.sh` walks four lookup paths (env var → CWD → `.active-project` pointer → single auto-detected subdir). For a single-project repo, the cleanest fit is "CWD has gecx-config.json (backward compat)" — no env-var setup, no pointer file, no subdir restructuring. Hooks always run from the repo root, so CWD always matches.

**Contents:**

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

Field-level rationale:

- `app_dir: "cxas_app/"` (not `cxas_app/Casino_Concierge/`) — matches `cxas pull`'s output shape (`<target>/Casino_Concierge/...`), so the drift-detection hook can `diff -rq tmp_dir app_dir` cleanly.
- `deployed_app_id` is the bare UUID, not the full resource path — per the bundle's CRITICAL FORMATTING note (`assets/project-template/gecx-config.json`); the SDK constructs the full path.
- `model`, `modality`, `default_channel` reflect prod reality (audio agent on `gemini-3.1-flash-live`).
- `gcs_bucket` named `gs://bigquery-demo-396708-cxas-audio-evals` to keep the bucket discoverable (project-prefix + purpose suffix). Required by the bundle's audio-recording eval flow; we provision it as part of this PR (see §8 step 1).

**Why we don't use `.active-project`:** that pointer is for the bundle's multi-project workspace pattern. We're a single project; the simpler "CWD has gecx-config.json" path covers us.

## 5. Hooks & resolver flow

Three hooks from the bundle, all wired into both Claude Code (`PreToolUse` / `PostToolUse` matcher: `Bash`) and Gemini CLI (`BeforeTool` / `AfterTool` matcher: `run_shell_command`):

| Hook | Triggers on | What it does | Verdict in our context |
|---|---|---|---|
| `pre-agent-push.sh` | command containing `cxas push` | `cxas pull` to a temp dir, `diff -rq` against `app_dir`, blocks on drift | Genuinely useful; activates when `gecx-config.json` exists. **See R1 in §9 — bidirectional diff may make this a deny-all gate; smoke-test gate before committing.** |
| `pre-agent-push-lint.sh` | command containing `cxas push` | `cxas lint --json --app-dir <project_dir>`, blocks on errors | Useful; gates at the cxas-push layer (different from `.githooks/pre-push` which gates `git push`). Defense in depth. |
| `post-agent-update.sh` | command containing `update_agent` | Auto-pull + sync-callbacks + reminder | No-op for us (only matches the deprecated MCP `update_agent` tool). Wire it anyway for skill bundle internal consistency; zero cost when it doesn't match. |

**Resolver flow (after Phase E lands):**

```
Bash command issued
  → PreToolUse fires both pre-agent-* hooks
  → resolve-project.sh: $GECX_PROJECT? no. CWD/gecx-config.json? YES (repo root). Returns "."
  → pre-agent-push.sh:
      app_dir = "./cxas_app/"
      app_resource = "projects/bigquery-demo-396708/locations/us/apps/c4242f9c-..."
      cxas pull → /tmp/xxx/Casino_Concierge/...
      diff /tmp/xxx vs ./cxas_app/
      → no drift → allow; drift → block with merge instructions in the message
  → pre-agent-push-lint.sh:
      cxas lint --json --app-dir .
      → reads ./cxaslint.yaml (which sets app_dir: cxas_app/Casino_Concierge)
      → 0 errors → allow; >0 → block with first 10 errors in the message
```

**Settings files — kept verbatim from the drop, with one exception:**

- `.claude/settings.json` (committed, team-wide) — already correctly references the bundle's hook scripts via `$CLAUDE_PROJECT_DIR/...`. No edits.
- `.gemini/settings.json` (committed, team-wide) — same wiring; the `tools.truncateToolOutputThreshold: 0` setting (disables Gemini's tool output truncation, useful for verbose lint output) stays. **Edit:** remove the entire top-level `skills` key (its only sub-key is `disabled: ["cxas-sim-eval"]`; we want all skills available, and `"skills": {}` would be an empty orphan).
- `.claude/settings.local.json` and `.gemini/settings.local.json` — per-user permission allowlists; gitignored.

**Existing `.githooks/pre-push`:** kept. Different layer (git push vs cxas push); both fire and provide complementary defense. Single edit: bump `venv/bin/activate` → `.venv/bin/activate` to match the renamed virtualenv.

**One subtle thing to flag:** the `pre-agent-push-lint.sh` calls `cxas lint --json` — but `cxas` only lives on PATH when the venv is active. Hooks run in whatever shell environment the operator is in. If someone forgets `source .venv/bin/activate`, the hook silently allows (its error path is `cxas lint --json ... 2>/dev/null || echo "[]"` → 0 errors → pass). Acceptable — the operator hits `cxas: command not found` on their actual `cxas push` immediately after, so the gap doesn't survive in practice.

## 6. Doc consolidation

**Canonical file:** `AGENTS.md` at repo root. `CLAUDE.md` and `GEMINI.md` become relative symlinks → `AGENTS.md`. All three CLI tools resolve symlinks transparently.

**Source material:** current `CLAUDE.md` is the richest and most accurate of the three; new `AGENTS.md` is built on its bones. Old `AGENTS.md` (the workspace-flavored description) is discarded entirely. Old `GEMINI.md` (the four mandates) — most are dropped or reframed (see below).

### Table of contents for the new AGENTS.md

| # | Section | Source / status |
|---|---|---|
| 1 | What this repo is | CLAUDE.md, mostly unchanged |
| 2 | cxas-scrapi tooling | CLAUDE.md, unchanged |
| 3 | Architecture (the three coupled surfaces) | CLAUDE.md, unchanged |
| 4 | CX Agent Studio conventions (non-obvious) | CLAUDE.md, unchanged |
| 5 | Deployment workflow | CLAUDE.md, **updated for `.venv/`** |
| 6 | CLI gotchas worth knowing | CLAUDE.md, unchanged |
| 7 | Linting | CLAUDE.md, **add note that the cxas pre-push hook also gates this layer; restate the zero-warnings policy with the downgrade-needs-rationale corollary** |
| 8 | Evals | CLAUDE.md, unchanged |
| 9 | **Skills available in this repo** (NEW — Phase E §3.5 step 6) | new; absorbs the useful bits of old GEMINI.md |
| 10 | **Hooks & settings** (NEW) | new |
| 11 | **`gecx-config.json` reference** (NEW) | new |
| 12 | MCP `update_agent` — deprecated | CLAUDE.md, unchanged |
| 13 | Data pipeline commands | CLAUDE.md, **updated for `.venv/`** |
| 14 | Environment | CLAUDE.md, **updated for `.venv/`** |

### What's dropped from the old GEMINI.md (and why)

- **"Ban on Generalist Agent."** Too aggressive; we use the `general-purpose` superpowers agent legitimately for parallel research. The Gemini-specific `generalist` it referred to isn't even in our flow.
- **"Mandatory Plan Mode."** Overlaps with our brainstorming → writing-plans → execution discipline already enforced via the superpowers skills. Redundant rule, plus rigid enough to block trivial typo edits.
- **"No Scripted Generation."** We deliberately use scripts (`parse_games_to_csv.py`, `update_games_md.py`). The mandate would forbid the very scripts we ship.

### What's preserved from the old GEMINI.md (and reframed)

- **"Zero Warnings Policy."** Kept. Reframed in §7 ("Linting") as: zero errors, zero warnings; any rule downgrade in `cxaslint.yaml` requires a rationale comment plus a follow-up TODO. Our existing I004 downgrade already follows this pattern (rationale in `cxaslint.yaml`; TODO in `FUTURE_ENHANCEMENTS.md` §4.7).
- **"Authorized Specialized Sub-Agents" concept.** Goes under §9 ("Skills available in this repo") as guidance: when to reach for the cxas-agent-foundry sub-agents (lint-fixer, eval-writer, triage-failure) vs doing it on the main thread.

### What §9 ("Skills available in this repo") covers

- The two skills (`cxas-agent-foundry`, `cxas-sim-eval`) and what each is for.
- The cxas-agent-foundry routing trap caveat: it routes "edit instructions / tweak a tool" → Build flow, but for *this* agent (already exists) routine prompt edits stay in the existing pull→edit→lint→push loop. The Build skill is for greenfield agents; we override its routing for the Casino Concierge.
- The six sub-agents (lint-fixer, eval-writer, triage-failure, scaffolder, tdd-writer, coverage-analyst), one-line each, with "when to reach for".
- A note that `setup.sh` is greenfield-only and not needed here (we already have a venv; running it would try to install cxas-scrapi from local source, which we don't have).
- Coexistence with the existing superpowers skills: cxas skills are domain-specific; superpowers skills (brainstorming, writing-plans, debugging, TDD) are workflow. They complement.
- How to update the bundle later (re-run `cxas init` in a throwaway worktree, diff, cherry-pick changes inside `.agents/skills/`, ignore changes to `gecx-config.json` / `AGENTS.md` / `.gitignore`).

### What §10 ("Hooks & settings") covers

- The three hooks the bundle wires in `.claude/settings.json` + `.gemini/settings.json`, what each blocks, when to bypass.
- The `.githooks/pre-push` (git layer lint).
- `gecx-config.json` is the anchor for hook resolution.
- `.claude/settings.local.json` and `.gemini/settings.local.json` are per-user, gitignored.

### What §11 ("`gecx-config.json` reference") covers

- One-line description of every field.
- Why we don't use `.active-project` (single-project repo).
- When to update each field (e.g., `deployed_app_id` only on app rotation; `model` if we change the LLM).

## 7. Additions to `cxaslint.yaml`

Three small additions copied from the pristine `examples/cxaslint.yaml` (after which we delete the pristine):

1. **`evals_dir: evals/`** — explicit > implicit. The linter currently defaults to `evals/` for us so it works, but stating it explicitly makes the contract obvious and protects against upstream default changes.

2. **`ignore:` block:**
   ```yaml
   ignore:
     - "**/__pycache__/**"
     - "**/test_*.py"
   ```
   Defensive given we just adopted `.agents/` (which carries `__pycache__/` until we clean it up).

3. **`# Run \`cxas lint --list-rules\` to see all available rules.`** — pointer comment that replaces the value the pristine's full rule catalog tries to provide (which would go stale).

Skipped from the pristine (deliberately):
- Apache 2.0 license header (we license per-repo, not per-file).
- Full rule catalog (50+ commented lines, every rule + default severity) — high decay risk; the `--list-rules` pointer is the canonical replacement.
- `options:` block (`I007.max_words: 3000`, `I006.patterns: [phone, price regexes]`) — we're happy with cxas defaults; the regex doesn't catch our UK helpline format anyway.
- `per_file:` example — trivial to add when we need it.
- The `# Path to the app directory` boilerplate — ours has better, project-specific framing.

## 8. Migration sequence

| # | Step | Verifies |
|---|---|---|
| 1 | Provision GCS bucket: `gcloud storage buckets create gs://bigquery-demo-396708-cxas-audio-evals --project=bigquery-demo-396708 --location=us --uniform-bucket-level-access` | `gcloud storage buckets list` shows it |
| 2 | Clean working tree: delete `.agents/skills/**/__pycache__/`, `*.pyc`, `examples/`. The dropped-in `AGENTS.md` and `GEMINI.md` stay in place for now — step 8 overwrites `AGENTS.md` and step 9 replaces `GEMINI.md` with a symlink (`ln -sfr` overwrites). | `find .agents -name __pycache__` returns empty; `examples/` gone |
| 3 | Update `.gitignore`: add `.claude/settings.local.json`, `.gemini/settings.local.json`, `.active-project` | `git status` shows `settings.local.json` no longer listed as untracked |
| 4 | Recreate virtualenv at `.venv/`: `rm -rf venv && python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip && pip install cxas-scrapi`. Update `.githooks/pre-push` `venv/bin/activate` → `.venv/bin/activate` | `source .venv/bin/activate && cxas --version` works; `git push` → hook still fires |
| 5 | Update `cxaslint.yaml` per §7 | `cxas lint` from repo root still passes clean |
| 6 | Write `gecx-config.json` at repo root with the contents from §4 | `jq . gecx-config.json` parses; values match §4 exactly |
| 7 | Edit `.gemini/settings.json`: remove the entire top-level `skills` key (its only sub-key is `disabled`, so leaving `"skills": {}` would be an empty orphan) | `jq .skills .gemini/settings.json` returns `null` |
| 8 | Write the new `AGENTS.md` per §6 outline | renders, links work, all 14 sections present |
| 9 | Replace `CLAUDE.md` with `ln -sfr AGENTS.md CLAUDE.md`. Replace `GEMINI.md` with `ln -sfr AGENTS.md GEMINI.md` | `ls -la CLAUDE.md GEMINI.md` shows symlinks; `cat CLAUDE.md` returns AGENTS.md content |
| 10 | **Smoke-test the drift hook (R1 gate):** make a trivial cosmetic edit to `cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt` (e.g., extra blank line), attempt `cxas push`. Observe: does the drift hook block the push, or allow it? | If blocked: R1 confirmed; remove just the `pre-agent-push.sh` entry from `.claude/settings.json` and `.gemini/settings.json`. If allowed: hook works as intended; proceed. Either way, revert the cosmetic edit. |
| 11 | Update `FUTURE_ENHANCEMENTS.md` §4.6 to mark Phase E as shipped | diff shows just that section updated |
| 12 | Update memory entry `project_cxas_retrofit_roadmap.md`: mark E shipped; only D remains | memory file edited; MEMORY.md unchanged |
| 13 | Open PR titled `feat: adopt cxas-agent-foundry skill bundle (Phase E)`; link spec + plan in description | PR opened against main |

## 9. Risks

**R1 — Drift-detection hook may reject all legitimate pushes.** The hook (`pre-agent-push.sh`) does `diff -rq <fresh_pull> <local>`. The diff is bidirectional — it fires on any difference, including the difference we deliberately created by editing local files in order to push them. The bundle's own header says "Blocks the push if local files are stale (platform has changes not in local)" — that intent is one-directional, but the implementation isn't.

In practice, every normal `cxas push` produces drift output (because that's the whole point of the push). The hook may block 100% of legitimate pushes, becoming a deny-all gate the operator routinely bypasses (which would defeat the hook entirely).

Mitigation:

- (a) Step 10 of the migration sequence is the explicit smoke-test gate. Make a trivial local edit, attempt `cxas push`, observe outcome.
- (b) If R1 confirmed: drop just `pre-agent-push.sh` from the `.claude/settings.json` and `.gemini/settings.json` wiring. The hook script stays in `.agents/skills/...` (skills frozen), but we don't reference it. We retain `pre-agent-push-lint.sh` and `post-agent-update.sh`.
- (c) Long-term: file an upstream cxas-scrapi issue (the hook should diff only the platform→local direction, e.g., by checking which side is newer or by hashing platform state at last-pull time). Out of scope for this PR.

**R2 — Skill bundle is a frozen snapshot.** Today's `.agents/skills/cxas-agent-foundry/` is a moment-in-time copy from upstream cxas-scrapi. Bundle updates won't propagate automatically. When we re-run `cxas init` (or equivalent) to pick up improvements, it will overwrite our `gecx-config.json` (or worse, AGENTS.md if we're not careful).

Mitigation: AGENTS.md §9 documents the update procedure — "to update the bundle: run `cxas init` in a throwaway worktree, diff against current repo, cherry-pick changes inside `.agents/skills/`, ignore changes to `gecx-config.json` / `AGENTS.md` / `.gitignore` unless we explicitly want them."

**R3 — Build sub-skill routing trap.** The cxas-agent-foundry SKILL.md routes "edit the agent's instructions / tweak a tool / fix the greeting" → Build flow (full PRD-to-agent ceremony). For *this* agent (which already exists), routine edits stay in the existing pull→edit→lint→push loop.

Mitigation: AGENTS.md §9 explicitly overrides this routing for the Casino Concierge agent. Future Claude Code sessions reading SKILL.md need to also read AGENTS.md §9 to pick up the override. Worth a session-start reminder if Phase D's CI sees this becoming a recurring problem.

**Lesser risks (one line each, no separate mitigation):**

- Hook overhead: every Bash command fires three hook scripts that no-op unless the command matches `cxas push` / `update_agent`. Per-command cost: small jq + grep + resolve-project lookup.
- Symlink portability on Windows: if anyone clones on Windows without dev-mode enabled, `CLAUDE.md` / `GEMINI.md` will appear as plaintext containing the symlink target. We're Linux-only in practice.
- `cxas pull` overwrites `cxas_app/`: the drift-detection hook's "merge first" suggestion would clobber local edits if followed verbatim. Note in AGENTS.md §10.

## 10. Out of scope (deferred to follow-up PRs)

- Phase D (CI/CD with GitHub Actions, AppVersion pinning, ephemeral PR apps).
- The five surfaced findings from Phase C (silent `end_session`, fallback themes, underage as distress, distress non-determinism, multilingual override).
- Fixing the I004 downgrade per `FUTURE_ENHANCEMENTS.md` §4.7.
- Refreshing `FUTURE_ENHANCEMENTS.md` §1.2 / §4.5 (already-shipped items mismatched with the doc).
- Wiring the new GCS bucket into `app.json`'s `evaluationAudioRecordingConfig` (bucket exists and is in `gecx-config.json`, but the app's recording config stays empty for now).
- Filing an upstream cxas-scrapi issue for R1.

## 11. Acceptance criteria

This PR is mergeable when all of the following hold:

1. `gecx-config.json` exists at repo root, parses with `jq`, fields match §4.
2. `.venv/` exists; `source .venv/bin/activate && cxas --version` works.
3. `cxas lint` from repo root exits 0 (errors and warnings).
4. `git push` triggers `.githooks/pre-push`, which runs `cxas lint` from `.venv/`.
5. `AGENTS.md` exists with all 14 sections from §6's table of contents. `CLAUDE.md` and `GEMINI.md` are symlinks to it; `cat CLAUDE.md` returns the same content.
6. `.gitignore` excludes `.claude/settings.local.json`, `.gemini/settings.local.json`, `.active-project`.
7. No `__pycache__/` or `*.pyc` files under `.agents/`.
8. `examples/` no longer exists.
9. Step 10's smoke test has been run and the outcome documented in the PR description (either "drift hook works as intended" or "R1 confirmed; `pre-agent-push.sh` unwired from settings.json").
10. `FUTURE_ENHANCEMENTS.md` §4.6 reflects Phase E shipped.
11. Memory entry `project_cxas_retrofit_roadmap.md` reflects D as the only remaining phase.
