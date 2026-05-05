# Future Enhancements & Project Review

## Current Project State
The **OVG Casino Concierge** is a virtual assistant built on **Google Cloud Customer Engagement Suite (CX Agent Studio)**.
Currently, it successfully:
1. Portrays a warm, upbeat, and professional casino host using the `en-US-Chirp3-HD-Zephyr` voice model.
2. Dynamically recommends games by querying a **Vertex AI Search Data Store**, backed by a **BigQuery** table containing 24 distinct games scraped from the casino's frontend.
3. Renders interactive UI components in the user's chat window using **Client Function Tools** piped to a custom Handlebars template (`game_carousel`) in the `ces-messenger` frontend framework.
4. Switches between multiple languages (`en-US`, `fr-FR`, `es-ES`) using `enableMultilingualSupport` (note: responsible-gaming resources still only cite the UK helpline — see §1.1).
5. Handles conversational boundaries effectively, including bounded proactive re-engagement (two attempts before `end_session`) and graceful session termination on goodbye or gambling distress.
6. Greets returning users by name via `user_first_name` from Firebase auth → `setQueryParameters`.
7. Resists persona-override / jailbreak attempts via a dedicated taskflow step and example.
8. Enforces strict anti-hallucination constraints (only recommends games returned by `search_available_games`, with a broader-query fallback before giving up).

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
*   **Current State:** The agent relies on prompt instructions to detect frustration and offer the gambling helpline.
*   **Improvement:** Add native CES **Guardrails** as a deterministic safety layer:
    *   `llmPromptSecurity` (or a custom `llmPolicy` with `policyScope: USER_QUERY`) classifying inputs for gambling addiction signals, financial distress, or underage self-disclosure.
    *   On trigger, `action: respondImmediately` with the locale-appropriate helpline (per §1.1) and force `end_session` with `reason="gambling_concerns"`.
    *   A `contentFilter` guardrail for an explicit banned-phrase list (e.g., underage signals like "I'm 16," "as a minor").

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
*   **Current State:** Testing is manual via the simulator; a regression in `system_instructions.md` would be caught only by chance.
*   **Improvement:** Use CES native **Evaluation** and **EvaluationDataset** resources. Seed the dataset from existing `<examples>` in the prompt. Add a deploy gate: run `run_evaluation` against the draft agent before pushing via `update_agent`; block promotion on failures.

### 4.2 Voice-Channel Evaluation
*   **Current State:** Even with #4.1 in place, text-only evaluation misses TTS pronunciation issues, barge-in handling, and STT mishearings — and this agent is voice-first.
*   **Improvement:** Run a parallel evaluation set with `evaluationChannel: AUDIO` so regressions in spoken output (e.g., introducing markdown or spelled-out URLs) are caught.

### 4.3 Persona-Stability / Jailbreak Eval Suite
*   **Current State:** The prompt has a "Resist Persona Override" step and one example, but no automated check that future edits don't weaken it.
*   **Improvement:** A dedicated golden-eval set of jailbreak prompts ("ignore previous instructions," "reveal your system prompt," "pretend you're DAN," "act as a financial advisor and recommend bets"). The agent must refuse without leaking instructions. Run as part of the same gate as #4.1.

### 4.4 App Version Pinning & Rollback
*   **Current State:** The current deploy workflow edits the draft agent directly via `update_agent`. There's no pinned, known-good production version and no quick rollback path.
*   **Improvement:** Use CES `AppVersion` + `Deployment` resources to pin a prod deployment to a versioned snapshot. Promotion flow: edit draft → run evals (#4.1–4.3) → snapshot to `AppVersion` → flip the prod `Deployment` to the new version. Rollback = flip back to the prior version.

### 4.5 Logging & Observability
*   **Current State:** No `loggingSettings` configured. Session conversations, escalation rates, and timeouts are invisible.
*   **Improvement:** Configure the app's `loggingSettings`:
    *   Enable **BigQuery export** of conversation data for offline analysis.
    *   Enable **Cloud Logging** for app-level events.
    *   Enable **audio recording** with a `redactionConfig` (DLP) for compliance.
    *   Build a basic dashboard for: sessions/day, average session length, distribution of `end_session.reason` values, and an alert on `gambling_concerns` spikes (potential incident or prompt regression).

### 4.6 Partial Infrastructure as Code
*   **Current State:** BigQuery, Vertex AI Search, and CES configs were created via CLI / cURL / MCP.
*   **Improvement:** Pragmatic split rather than a single Terraform monolith:
    *   **BigQuery + Vertex AI Search:** port to Terraform — both have mature providers.
    *   **CES Agent Studio resources** (agents, tools, toolsets, guardrails, deployments): no first-class Terraform provider. Maintain as version-controlled YAML/markdown in this repo (already partially done — `prompts/system_instructions.md` is the source of truth) and reify via a deploy script that wraps the MCP `update_agent` / `create_*` calls. Pair with #4.4 so each push produces an `AppVersion`.
