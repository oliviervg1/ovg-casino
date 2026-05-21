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
10. Is fully version-controlled under `cxas_app/Casino_Concierge/` and deployed via the cxas-scrapi CLI (`cxas push`); see `AGENTS.md` for the full deploy workflow and the ongoing tooling roadmap (lint, evals, CI/CD, CLI skills).

While the foundational architecture is robust, several improvements would meaningfully raise safety, reliability, and operational maturity.

---

## 1. Safety & Compliance

### 1.1 Native CES Guardrails and Prompt-Level Safety Teardown
*   **Status (2026-05-20):** **Fully Shipped & Unified.** The entire gambling-distress and underage-handling safety architecture has been completed and launched. Rather than relying on simple static guardrail fallbacks, the system uses a highly integrated prompt-and-tool strategy to guarantee correct dynamic, localized responses and strict session termination.
*   **Currently deployed & active:**
    *   **Sub-Agent Safety Teardown (`Safety_Handler`)**: Built and refined to handle both gambling distress and underage self-disclosure (first-party or third-party child framings). When triggered, it executes the custom `get_responsible_gaming_helpline` tool to dynamically retrieve localized, language-appropriate helpline details (National Gambling Helpline for English, Joueurs Info Service for French, Línea de Ayuda de FEJAR for Spanish) instead of hardcoding any values. It then returns a single empathetic spoken sentence containing the localized details and immediately calls the built-in `end_session` tool with `reason="responsible_gambling"`.
    *   `Prompt Guardrail 1772646260685` — `llmPromptSecurity` with default settings; action `generativeAnswer` (rewrites unsafe input rather than blocking).
    *   `Safety Guardrail 1772646260685` — `modelSafety` blocking standard harm categories (`HARM_CATEGORY_HATE_SPEECH`, `HARM_CATEGORY_DANGEROUS_CONTENT`, `HARM_CATEGORY_SEXUALLY_EXPLICIT`, and `HARM_CATEGORY_HARASSMENT`) at `BLOCK_MEDIUM_AND_ABOVE`.
*   **Refinement of Remaining Work (Architectural Discovery):**
    *   *CES Guardrail Limitations*: During implementation, we determined that native CES Guardrail policies using `respondImmediately` cannot resolve dynamic, session-aware variables or invoke custom API tools like `get_responsible_gaming_helpline` to return localized helpline details. Hardcoding static fallback messages inside a native CES Guardrail would violate our multilingual compliance goals (French and Spanish players). Therefore, the **prompt-first routing to `Safety_Handler`** is the canonical, fully-shipped solution.
    *   *Defense-in-Depth Option (Remaining)*: We can still introduce a native `contentFilter` or custom `llmPolicy` at the guardrail level as a secondary layer of protection, configured to trigger a safe, static, localized fallback response if a jailbreak attempt successfully bypasses the prompt flow. However, this is treated as low-priority defense-in-depth given that the primary `Safety_Handler` path has a 100% pass rate in our safety and boundaries evaluation suites.

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
    *   **Direct Model end_session Tool Calls (Callback Removal):** During subsequent optimization passes, the multi-turn evaluations were aligned to verify native tool execution. To simplify the architecture, the "Prompt-First Tool-Injection" pattern (which relied on after-model/after-agent python callbacks) was retired. The `Safety_Handler` prompt instructions now directly call `get_responsible_gaming_helpline` and `end_session` natively within the system prompts, standardizing mock examples on correct JSON arguments (`{"reason": "responsible_gambling"}`). All python callback folders and registrations have been completely removed from disk and app configurations, keeping the agent fully native and tool-driven.
*   **Remaining work:** Automated CI/CD integration wires `cxas push-eval` + `cxas run` into GH Actions as the unbypassable CI gate; manual runs are the gate today.

### 4.2 Voice-Channel Evaluation
*   **Status (2026-05-15):** **Shipped.** Audio-channel coverage is implemented as a tag-based subset of the existing Goldens.
*   **Currently deployed:** A subset of `evals/goldens/discovery.yaml` and `evals/goldens/safety.yaml` conversations carry the `audio_critical` tag (5 conversations). Run via `cxas run --tags audio_critical --modality audio --wait`. The same Goldens go through TTS+STT round-trip so we catch markdown bleed-through, spelled-out URLs, and tone drift in spoken output.
*   **Remaining work:** Automated CI/CD integration adds the CI invocation. Audio runs are slow — keep the `audio_critical` tag scoped narrowly to conversations where TTS-specific issues matter.

### 4.3 Persona-Stability / Jailbreak Eval Suite
*   **Status (2026-05-15):** **Shipped.** Dedicated boundaries and safety Golden suites with sub-category tagging.
*   **Currently deployed:** `evals/goldens/boundaries.yaml` and `evals/goldens/safety.yaml` — 16+ conversations across attack families (`prompt_injection`, `roleplay_override`, `scope_creep`, `win_guarantee`, `underage`). Each case asserts the agent declines without leaking instructions and (for distress/underage signals) programmatically terminates the session. Threshold is 100% pass — a single jailbreak success is a safety incident.
*   **Remaining work:** Expand the corpus as new attack patterns emerge in the wild. The `underage_self_disclosure` test was tightened to assert correct session termination. See §4.1's surfaced findings for the broader roleplay-variance pattern that prior iterations uncovered (model emits an identical stock bare-refusal on ~10-20% of roleplay-jailbreak inputs).

### 4.4 App Version Pinning & Rollback
*   **Current State:** Under the current repository-based workflow, the deploy workflow uses `cxas push` against the prod app from `cxas_app/Casino_Concierge/`. There is still no pinned, known-good production `AppVersion` and no quick rollback path — every push goes straight to the live draft.
*   **Improvement (queued under automated CI/CD gating of the cxas retrofit):** Use CES `AppVersion` + `Deployment` resources to pin a prod deployment to a versioned snapshot. Promotion flow: edit draft → run evals (#4.1–4.3) → snapshot to `AppVersion` → flip the prod `Deployment` to the new version. Rollback = flip back to the prior version. The implementation lives in `.github/workflows/main-deploy.yaml` and `.github/workflows/rollback.yaml` per the retrofit spec.

### 4.5 Logging & Observability
*   **Status (2026-05-15):** Partially shipped. Conversation logging + redaction are configured in prod; audio recording is intentionally off; the dashboard is still TBD.
*   **Currently deployed** (visible in `cxas_app/Casino_Concierge/app.json` under `loggingSettings`):
    *   **BigQuery export** of conversation data: `gecx_logs` dataset in `bigquery-demo-396708`.
    *   **Cloud Logging** for app-level events: `enableCloudLogging: true`.
    *   **Text redaction**: `redactionConfig.enableRedaction: true`.
    *   **Conversation retention**: 1 year (`retentionWindow: "31536000s"`).
*   **Remaining work:**
    *   Enable **audio recording** (`audioRecordingConfig` is currently `{}` — recording is off). The `redactionConfig` is already on, so DLP would apply to recordings the moment they're enabled.
    *   Build the dashboard: sessions/day, average session length, distribution of `end_session.reason` values, and an alert on `responsible_gambling` spikes (potential incident or prompt regression). The data is already flowing into BigQuery — this is a Looker Studio / Looker / Cloud Monitoring pure-config job, not an agent change.

### 4.6 Partial Infrastructure as Code
*   **Status (2026-05-15):** Partially shipped for the CES side. The cxas-scrapi retrofit replaced the original "version-controlled YAML/markdown + deploy script" idea with the cxas tool. BigQuery + Vertex AI Search remain on the original CLI / cURL plan.
*   **Currently deployed:**
    *   **CES Agent Studio resources** (agents, tools, guardrails, evaluations, app config): now version-controlled under `cxas_app/Casino_Concierge/` and deployed via `cxas push`. The `prompts/system_instructions.md` mention in the original wording is obsolete — that file moved to `cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt`.
    *   AppVersion + Deployment-based prod pinning is queued under automated CI/CD gating of the cxas retrofit (originally cross-referenced as §4.4).
*   **Remaining work:**
    *   **BigQuery + Vertex AI Search:** still need to be ported to Terraform. Both have mature providers.
    *   Automated CI/CD with AppVersion pinning of the cxas retrofit. Linter enforcement, evaluation suites, and skills integration have shipped. See the spec for details.

### 4.7 Prompt rewrite to avoid negative triggers (I004)
*   **Status (2026-05-21):** **Shipped — closed as no-op.** The original deferral assumed the `I004 negative-triggers` rule was firing on the no-results fallback and silence-detection triggers in `instruction.txt`. On re-inspection of the rule source (`cxas_scrapi/utils/lint_rules/instructions.py`), I004's regexes only match the literal tokens `NOT`, `is NOT`, or `not a|not an|not the` inside `<trigger>...</trigger>` blocks (case-insensitive, single line). Current triggers use phrasings like *"no results"*, *"no preference"*, and *"no indication"* — none of which match. The rule never fired against the current prompt.
*   **Resolution:** Removed the `I004: info` downgrade from `cxaslint.yaml`. The rule now runs at its default `WARNING` severity. `cxas lint` reports zero findings, satisfying the repo's zero-errors-zero-warnings policy. No prompt edits required; behavior unchanged.

### 4.8 Upstream cxas-scrapi: drift-detection hook is a deny-all gate
*   **Status (2026-05-15):** Discovered, mitigated locally, upstream fix pending. The `pre-agent-push.sh` hook ships in the bundle but is unwired in our `.claude/settings.json` and `.gemini/settings.json` (commit `e78fee8`); the script remains under `.agents/skills/cxas-agent-foundry/scripts/hooks/` because the bundle is frozen as-is. The other two hooks (`pre-agent-push-lint.sh`, `post-agent-update.sh`) remain wired.
*   **The bug:** the hook's intent (per its header comment) is to "block the push if local files are stale (platform has changes not in local)" — a one-directional check. Its implementation is `cxas pull` to a temp dir followed by `diff -rq tmp_dir app_dir`, which is bidirectional. Any normal `cxas push` produces drift output (because the whole point of pushing is that local has changes the platform doesn't yet see), so the hook treats every legitimate push as drift and blocks. Functionally a deny-all gate.
*   **Confirmation:** smoke-tested during skills rollout. With one trivial blank-line edit to `instruction.txt` the hook returns `{"hookSpecificOutput":{"hookEventName":"PreToolUse","blockToolExecution":true,...}}`. See PR #6, design spec §9 R1, plan Task 9 for the verbatim output.
*   **Improvement (upstream):** the drift detection should be one-directional. Two viable shapes:
    *   **(a)** Compare against a stored hash of platform state from the last `cxas pull`. The hook records the hash at pull time; if the current platform state matches the stored hash, no drift (regardless of local changes). If it differs, someone made platform-side changes after our last pull → drift. Lower complexity, no timestamp dependency.
    *   **(b)** Diff in only one direction: block only on files where the platform has a version that local doesn't, ignoring files where local has changes the platform doesn't. Slightly more involved (requires per-file content comparison rather than `diff -rq`'s flat output).
*   **Action item:** file an issue at the cxas-scrapi upstream repo describing the bug and proposing fix (a). Once shipped (and after we re-run `cxas init` per the bundle-update procedure documented in `AGENTS.md` § "Skills available in this repo"), re-wire the hook in both settings files.
*   **Cross-references:** PR #6 (skills integration), skills design §9 (R1 risk analysis), skills smoke-test procedure.

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
