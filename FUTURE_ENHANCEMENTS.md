# Future Enhancements & Project Review

## Current Project State
The **OVG Casino Concierge** is a virtual assistant built on **Google Cloud Customer Engagement Suite (CX Agent Studio)**.
Currently, it successfully:
1. Portrays a warm, upbeat, and professional casino host using the `en-US-Chirp3-HD-Zephyr` voice model on the `gemini-3.1-flash-live` LLM.
2. Dynamically recommends games by querying a **Vertex AI Search Data Store**, backed by a **BigQuery** table containing 24 distinct games scraped from the casino's frontend.
3. Renders interactive UI components in the user's chat window using **Client Function Tools** piped to a custom Handlebars template (`game_carousel`) in the `ces-messenger` frontend framework.
4. Switches between multiple languages (`en-US`, `fr-FR`, `es-ES`) using `enableMultilingualSupport` (note: responsible-gaming resources still only cite the UK helpline — see §1.1).
5. Handles conversational boundaries effectively, including bounded proactive re-engagement (two attempts before `end_session`) and graceful session termination on goodbye or gambling distress.
6. Greets returning users by name via `user_first_name` from Firebase auth → `setQueryParameters`.
7. Resists persona-override / jailbreak attempts via a dedicated taskflow step and example, **and** has two CES native guardrails attached (`Prompt Guardrail` using `llmPromptSecurity`; `Safety Guardrail` blocking the four standard harm categories at `BLOCK_MEDIUM_AND_ABOVE`).
8. Enforces strict anti-hallucination constraints (only recommends games returned by `search_available_games`, with a broader-query fallback before giving up).
9. Logs all conversations to BigQuery (`gecx_logs` dataset) and Cloud Logging, with text redaction enabled and a 1-year retention window.
10. Is fully version-controlled under `cxas_app/Casino_Concierge/` and deployed via the cxas-scrapi CLI (`cxas push`); see `CLAUDE.md` for the full deploy workflow and `docs/superpowers/specs/2026-05-15-cxas-scrapi-retrofit-design.md` for the ongoing tooling roadmap (lint, evals, CI/CD, Claude Code skills).

While the foundational architecture is robust, several improvements would meaningfully raise safety, reliability, and operational maturity.

---

## 1. Safety & Compliance

### 1.1 Locale-Aware Responsible Gaming Resources
*   **Current State:** The agent supports `en-US`, `fr-FR`, and `es-ES`, but only cites the UK National Gambling Helpline (`0808 8020 133`) regardless of the user's language. A French speaker hearing a UK number is broken UX *and* a compliance gap.
*   **Improvement:** Add per-locale resources resolved at response time:
    *   `en-US` → 1-800-GAMBLER (National Council on Problem Gambling)
    *   `en-GB` → 0808 8020 133 (GambleAware / National Gambling Helpline)
    *   `fr-FR` → 09 74 75 13 13 (Joueurs Info Service)
    *   `es-ES` → FEJAR helpline (regional)
    Drive selection from the active language code rather than hard-coding into the prompt.

### 1.2 Native CES Guardrails for Content Filtering
*   **Status (2026-05-15):** Partially shipped. Basic guardrails are active in prod; the gambling-distress-specific flow (locale helpline + forced `end_session`) is still TBD.
*   **Currently deployed** (visible in `cxas_app/Casino_Concierge/guardrails/`):
    *   `Prompt Guardrail 1772646260685` — `llmPromptSecurity` with default settings; action `generativeAnswer` (rewrites unsafe input rather than blocking).
    *   `Safety Guardrail 1772646260685` — `modelSafety` blocking `HARM_CATEGORY_HATE_SPEECH`, `HARM_CATEGORY_DANGEROUS_CONTENT`, `HARM_CATEGORY_SEXUALLY_EXPLICIT`, and `HARM_CATEGORY_HARASSMENT` at `BLOCK_MEDIUM_AND_ABOVE`.
*   **Remaining work:**
    *   **Note (2026-05-19, PR 1 of agent-tightening):** prompt-level underage handling has shipped (`instruction.txt` "Address Underage Self-Disclosure" step + companion strengthening of the "Address Gambling Concerns" trigger). Self-disclosed underage (first-person *and* third-party-child framings like "Can my 14-year-old play?") now fires `end_session(reason='gambling_concerns')` with the helpline. The guardrail-level work below remains as parallel defense in depth — both layers should fire for underage signals, and a CES-side guardrail also gives us a tool for the roleplay-variance pattern surfaced under §4.1 (the model's stock bare-refusal bypasses prompt logic ~10-20% of the time on roleplay-jailbreak inputs that co-signal distress).
    *   A custom `llmPolicy` (or tuned `llmPromptSecurity`) with `policyScope: USER_QUERY` specifically classifying gambling addiction signals, financial distress, or underage self-disclosure.
    *   On trigger: switch the action from `generativeAnswer` to `respondImmediately` with the locale-appropriate helpline (per §1.1) and force `end_session` with `reason="gambling_concerns"`.
    *   A `contentFilter` guardrail for an explicit banned-phrase list (e.g., underage signals like "I'm 16," "as a minor"). The deployed `modelSafety` covers generic harm categories but does not enforce a custom phrase list.

---

## 2. Data & Catalog

### 2.1 Automated Sync Pipeline (with brittleness safeguards)
*   **Current State:** Game data is scraped via a one-shot script (`scripts/parse_games_to_csv.py`), manually loaded into BigQuery, and re-imported into Vertex AI Search.
*   **Improvement:** Deploy the scraper as a **Google Cloud Function**, but be careful — the scraper depends on the minified JS variable names `eU` and `fU` in the casino's bundle. If the upstream build emits different identifiers, the regex matches nothing and produces an empty CSV silently. Required guardrails:
    *   Row-count sanity check (e.g., assert ≥ 24 games, fail-closed otherwise).
    *   Land into a staging BigQuery table first; promote to `games_inventory` only on validation pass.
    *   Alert (Cloud Monitoring) if the scraper runs but produces fewer rows than the prior baseline.
    *   Triggered by **Cloud Scheduler** weekly (the casino has 24 games and changes rarely — daily is overkill), or ideally by a **webhook from the casino's CI/CD** when a new bundle deploys.

### 2.2 Catalog Liveness Check
*   **Current State:** The scrape pipeline is one-way (frontend → catalog). If a game is delisted from the casino, the agent will keep recommending a dead URL until the next scrape.
*   **Improvement:** During each sync, issue a `HEAD` request against every `url` in the proposed catalog. Drop rows that 404 or 5xx. Log the drops as a separate metric so unexpected deletions surface during review.

### 2.3 Expanded Game Metadata (upstream-dependent)
*   **Current State:** The catalog tracks `id`, `title`, `game_type`, `theme`, `short_description`, `detailed_description`, `symbols`, and `url`.
*   **Improvement:** Adding metadata like `Volatility`, `RTP (Return to Player)`, `Min/Max Bet`, and `Popularity` would unlock complex queries (*"I want a low-stakes, high-RTP space game"*). **Caveat:** these fields are not present in the current `eU` / `fU` data structures in the casino's frontend bundle — this enhancement requires changes to the *casino itself* before our scraper can pick them up. Track as upstream-blocked.

---

## 3. Personalization

### 3.1 Extended Authenticated Player Context
*   **Current State:** `user_first_name` is already passed via Firebase auth → `setQueryParameters` and used in the welcome greeting.
*   **Improvement:** Extend the existing query-parameter channel to include richer fields fetched from the casino backend at chat-open time:
    *   `loyalty_tier` (Bronze / Silver / Gold) — adjust offer language and game tier.
    *   `recent_games` — enable "want to try something similar to your last session?" patterns.
    *   `preferred_themes` — bias the first `search_available_games` query.
    Implement as additional query parameters declared in the app's `variableDeclarations`, populated by a backend OpenAPI tool the frontend calls before opening the chat. No new infrastructure category — reuses what's already wired.

---

## 4. DevOps & Quality

### 4.1 Automated Evaluation Framework
*   **Status (2026-05-19):** **Shipped and Refined.** The full eval suite (Goldens + Simulations) and gating are in place. The suite was completely overhauled to eliminate flakiness caused by exact-text matching and to improve realism.
*   **Currently deployed** (in `evals/` at repo root and pushed to prod via `cxas push-eval`):
    *   **Themed Goldens (`discovery.yaml`, `safety.yaml`, `boundaries.yaml`, `explanations.yaml`)**: Replaced the monolithic `happy_path` and `tool_usage` files. These now extensively use the `# silent` agent response pattern to exclusively verify tool-call contracts without failing on benign text variations.
    *   **Atomized Simulations (`simulations.yaml`)**: Multi-turn LLM-driven scenarios (e.g., `full_personalized_discovery_cycle`, `safety_distress_handling`). These evaluate semantic tone, AI identity disclosure, and complex state changes. They were deliberately atomized into single-purpose scenarios (e.g., separating boundaries testing from distress handling) to prevent the user-LLM from derailing multi-step flows due to correct agent refusals.
    *   **Audio Tool-Call Dropping & Interception Bug:** In audio and chat modalities on `gemini-3.1-flash-live`, generating long empathetic text and executing a terminal action (`end_session`) in the same turn frequently caused the platform to drop the text. Originally mitigated via prompt constraints, this has now been completely resolved by implementing the **Prompt-First Tool-Injection Pattern** on the `Safety_Handler` sub-agent: the instruction prompt is kept entirely text-only to allow reliable LLM text generation, and the `ensure_helpline_text` after-model callback programmatically appends the native `end_session` tool call in memory, providing a bulletproof and elegant architecture.
    *   **Platform Orphan Cleanup:** 33 obsolete evaluations from early testing phases were manually deleted from the CES platform to clean up the dashboard.
*   **Remaining work:** Phase D wires `cxas push-eval` + `cxas run` into GH Actions as the unbypassable CI gate; manual runs are the gate today.

### 4.2 Voice-Channel Evaluation
*   **Status (2026-05-15, Phase C):** **Shipped.** Audio-channel coverage is implemented as a tag-based subset of the existing Goldens.
*   **Currently deployed:** A subset of `evals/goldens/discovery.yaml` and `evals/goldens/safety.yaml` conversations carry the `audio_critical` tag (5 conversations). Run via `cxas run --tags audio_critical --modality audio --wait`. The same Goldens go through TTS+STT round-trip so we catch markdown bleed-through, spelled-out URLs, and tone drift in spoken output.
*   **Remaining work:** Phase D adds the CI invocation. Audio runs are slow — keep the `audio_critical` tag scoped narrowly to conversations where TTS-specific issues matter.

### 4.3 Persona-Stability / Jailbreak Eval Suite
*   **Status (2026-05-15, Phase C):** **Shipped.** Dedicated boundaries and safety Golden suites with sub-category tagging.
*   **Currently deployed:** `evals/goldens/boundaries.yaml` and `evals/goldens/safety.yaml` — 16+ conversations across attack families (`prompt_injection`, `roleplay_override`, `scope_creep`, `win_guarantee`, `underage`). Each case asserts the agent declines without leaking instructions and (for distress/underage signals) programmatically terminates the session. Threshold is 100% pass — a single jailbreak success is a safety incident.
*   **Remaining work:** Expand the corpus as new attack patterns emerge in the wild. The `underage_self_disclosure` test was tightened to assert correct session termination. See §4.1's surfaced findings for the broader roleplay-variance pattern that prior iterations uncovered (model emits an identical stock bare-refusal on ~10-20% of roleplay-jailbreak inputs).

### 4.4 App Version Pinning & Rollback
*   **Current State:** Post-Phase-A, the deploy workflow uses `cxas push` against the prod app from `cxas_app/Casino_Concierge/`. There is still no pinned, known-good production `AppVersion` and no quick rollback path — every push goes straight to the live draft.
*   **Improvement (queued under Phase D of the cxas retrofit):** Use CES `AppVersion` + `Deployment` resources to pin a prod deployment to a versioned snapshot. Promotion flow: edit draft → run evals (#4.1–4.3) → snapshot to `AppVersion` → flip the prod `Deployment` to the new version. Rollback = flip back to the prior version. The implementation lives in `.github/workflows/main-deploy.yaml` and `.github/workflows/rollback.yaml` per the retrofit spec.

### 4.5 Logging & Observability
*   **Status (2026-05-15):** Partially shipped. Conversation logging + redaction are configured in prod; audio recording is intentionally off; the dashboard is still TBD.
*   **Currently deployed** (visible in `cxas_app/Casino_Concierge/app.json` under `loggingSettings`):
    *   **BigQuery export** of conversation data: `gecx_logs` dataset in `bigquery-demo-396708`.
    *   **Cloud Logging** for app-level events: `enableCloudLogging: true`.
    *   **Text redaction**: `redactionConfig.enableRedaction: true`.
    *   **Conversation retention**: 1 year (`retentionWindow: "31536000s"`).
*   **Remaining work:**
    *   Enable **audio recording** (`audioRecordingConfig` is currently `{}` — recording is off). The `redactionConfig` is already on, so DLP would apply to recordings the moment they're enabled.
    *   Build the dashboard: sessions/day, average session length, distribution of `end_session.reason` values, and an alert on `gambling_concerns` spikes (potential incident or prompt regression). The data is already flowing into BigQuery — this is a Looker Studio / Looker / Cloud Monitoring pure-config job, not an agent change.

### 4.6 Partial Infrastructure as Code
*   **Status (2026-05-15):** Partially shipped for the CES side. The cxas-scrapi retrofit (`docs/superpowers/specs/2026-05-15-cxas-scrapi-retrofit-design.md`) replaced the original "version-controlled YAML/markdown + deploy script" idea with the cxas tool. BigQuery + Vertex AI Search remain on the original CLI / cURL plan.
*   **Currently deployed:**
    *   **CES Agent Studio resources** (agents, tools, guardrails, evaluations, app config): now version-controlled under `cxas_app/Casino_Concierge/` and deployed via `cxas push`. The `prompts/system_instructions.md` mention in the original wording is obsolete — that file moved to `cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt`.
    *   AppVersion + Deployment-based prod pinning is queued under Phase D of the cxas retrofit (originally cross-referenced as §4.4).
*   **Remaining work:**
    *   **BigQuery + Vertex AI Search:** still need to be ported to Terraform. Both have mature providers.
    *   Phase D (CI/CD with AppVersion pinning) of the cxas retrofit. Phases B, C, and E have shipped. See the spec for details.

### 4.7 Prompt rewrite to avoid negative triggers (I004)
*   **Status:** Deferred. The cxas lint rule `I004 negative-triggers` is downgraded to `info` in `cxaslint.yaml` because the no-results fallback and silence-detection triggers in `instruction.txt` legitimately depend on a negative condition.
*   **Improvement:** A focused prompt-improvement pass to find phrasings that satisfy the rule without losing clarity (e.g., trigger on "the result list is empty" rather than "no results"). Then re-enable I004 at warning severity in `cxaslint.yaml`.

### 4.8 Upstream cxas-scrapi: drift-detection hook is a deny-all gate (R1)
*   **Status (2026-05-15, Phase E):** Discovered, mitigated locally, upstream fix pending. The `pre-agent-push.sh` hook ships in the bundle but is unwired in our `.claude/settings.json` and `.gemini/settings.json` (commit `e78fee8`); the script remains under `.agents/skills/cxas-agent-foundry/scripts/hooks/` because the bundle is frozen as-is. The other two hooks (`pre-agent-push-lint.sh`, `post-agent-update.sh`) remain wired.
*   **The bug:** the hook's intent (per its header comment) is to "block the push if local files are stale (platform has changes not in local)" — a one-directional check. Its implementation is `cxas pull` to a temp dir followed by `diff -rq tmp_dir app_dir`, which is bidirectional. Any normal `cxas push` produces drift output (because the whole point of pushing is that local has changes the platform doesn't yet see), so the hook treats every legitimate push as drift and blocks. Functionally a deny-all gate.
*   **Confirmation:** smoke-tested during Phase E. With one trivial blank-line edit to `instruction.txt` the hook returns `{"hookSpecificOutput":{"hookEventName":"PreToolUse","blockToolExecution":true,...}}`. See PR #6, design spec §9 R1, plan Task 9 for the verbatim output.
*   **Improvement (upstream):** the drift detection should be one-directional. Two viable shapes:
    *   **(a)** Compare against a stored hash of platform state from the last `cxas pull`. The hook records the hash at pull time; if the current platform state matches the stored hash, no drift (regardless of local changes). If it differs, someone made platform-side changes after our last pull → drift. Lower complexity, no timestamp dependency.
    *   **(b)** Diff in only one direction: block only on files where the platform has a version that local doesn't, ignoring files where local has changes the platform doesn't. Slightly more involved (requires per-file content comparison rather than `diff -rq`'s flat output).
*   **Action item:** file an issue at the cxas-scrapi upstream repo describing the bug and proposing fix (a). Once shipped (and after we re-run `cxas init` per the bundle-update procedure documented in `AGENTS.md` § "Skills available in this repo"), re-wire the hook in both settings files.
*   **Cross-references:** PR #6 (Phase E adoption), `docs/superpowers/specs/2026-05-15-phase-e-skills-design.md` §9 (R1 risk analysis), `docs/superpowers/plans/2026-05-15-phase-e-skills.md` Task 9 (smoke-test procedure).

### 4.9 Upstream cxas-scrapi: eval framework lacks OR-style tool-call assertions
*   **Status (2026-05-19):** Discovered during PR 1 iteration; documented locally, upstream fix pending. Surfaced by §4.1's roleplay-variance findings and documented in an inline comment block on `evals/goldens/boundaries.yaml`.
*   **The limitation:** cxas eval Goldens treat absence of `tool_calls:` as "no tool calls expected" — any tool call the agent fires becomes an unexpected `Turn Expectation` failure. Conversely, presence of a `tool_calls: [...]` list asserts those specific calls *must* fire. There's no third shape for "either is acceptable" / "tool-call is optional". For non-deterministic flows where the agent's *correct* behavior is sometimes a tool call and sometimes a text-only response, neither assertion shape gives a clean signal:
    *   `tool_calls: [end_session]` → fails when the agent (correctly) responds text-only (e.g., the model's stock bare-refusal on roleplay-style jailbreaks).
    *   No `tool_calls:` → fails when the agent (correctly) fires `end_session`.
*   **Confirmation:** smoke-tested during prior iterations. Loosening a roleplay case from a pinned `end_session` assertion to silent + no `tool_calls:` FLIPPED the failure rate from 20% (bare-refusal cases) to 80% (desired-distress-flow cases). Pushed via `cxas push-eval`, ran via `cxas run --tags boundaries --wait`, observed `Turn Expectation: Expected: , Actual: end_session` failures. Reverted to the tightened shape; documented the limitation inline.
*   **Improvement (upstream):** add a third assertion shape to cxas Goldens YAML. Three viable shapes (any one would unblock):
    *   **(a)** A top-level boolean per turn: `tool_call_optional: true` that switches `tool_calls` from required-to-fire to permitted-but-not-required.
    *   **(b)** A list-of-alternatives shape: `tool_calls: { any_of: [[end_session], []] }` — explicit OR between distinct tool-call patterns.
    *   **(c)** Extend `$matchType: ignore` to apply at the `tool_calls[]` level (currently only valid inside `tool_calls[].args.<argname>` per the CLAUDE.md `### Evals` schema reference), so `tool_calls: [{action: end_session, $matchType: ignore}]` would mean "this call is optional".
*   **Action item:** file an issue at the cxas-scrapi upstream repo describing the limitation and proposing one of the three fix shapes above. Once shipped, retighten the roleplay cases using the new shape.
*   **Cross-references:** §4.1 (roleplay-variance findings), `evals/goldens/boundaries.yaml` (inline comment blocks).
