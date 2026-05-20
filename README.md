# OVG Casino Concierge - CX Agent Studio Setup

This repository contains the configuration and planning documentation for the **Casino Concierge** virtual assistant, built using Google Cloud's Customer Engagement Suite (CX Agent Studio).

## Agent Overview
The Casino Concierge is designed to act as a highly knowledgeable, vibrant, and welcoming virtual host for the OVG Casino. Its primary goal is to provide exceptional customer service, guide beginners, explain game mechanics (Slots, Roulette, Bingo), and help players discover games based on their personal taste.

### Key Characteristics
*   **Role:** Vibrant, welcoming, and knowledgeable Casino Concierge.
*   **Voice:** `en-US-Chirp3-HD-Zephyr` (A warm, highly expressive, conversational American female voice utilizing Google's latest Chirp 3 HD conversational AI model).
*   **Tone:** Warm, Upbeat, Approachable, Professional, and Responsible.
*   **Guardrails:** Focuses on entertainment, never guarantees a win, and dynamically provides localized national gambling helplines (e.g., `0808 8020 133` for UK, `1-800-GAMBLER` for US, `09 74 75 13 13` for France, and `900 200 225` for Spain) for users expressing frustration or gambling concerns.

## Project Structure
```text
ovg-casino-concierge/
├── README.md                       # Project overview, architecture, and setup instructions
├── AGENTS.md                       # Core orchestration and CLI setup guidelines
├── CLAUDE.md                       # Working instructions symlink pointing to AGENTS.md
├── GEMINI.md                       # Working instructions symlink pointing to AGENTS.md
├── FUTURE_ENHANCEMENTS.md         # Retrospective review and upcoming safety/platform roadmap
├── gecx-config.json                # Project anchor configuration linking GECX apps/IDs
├── cxaslint.yaml                   # Strict GECX linter policy overrides and suppressions
├── cxas_app/                       # Pull/push synchronization directory for CES apps
│   └── Casino_Concierge/
│       ├── app.json                # App-level config: voice, locales, model, guardrails, logging
│       ├── environment.json        # Dynamic env variable resolution placeholders
│       ├── agents/
│       │   ├── Casino_Concierge/   # Root agent (instruction.txt system prompt, Casino_Concierge.json)
│       │   └── Safety_Handler/     # Sub-agent (gambling distress/underage handler, Safety_Handler.json)
│       └── tools/
│           ├── search_available_games/ # Datastore tool querying Vertex AI Search index
│           ├── display_game_widget/    # Client function tool rendering Handlebars carousel
│           └── get_responsible_gaming_helpline/ # Custom Python client function tool (locale helplines)
├── evals/                          # Local platform golden tests and simulator assertions
│   ├── goldens/                    # Platform Golden YAMLs (boundaries, discovery, explanations, safety)
│   └── simulations/                # Multi-turn user-emulated simulation test scenarios
├── data/
│   ├── raw/games.md                # Human-readable games catalog (markdown mirror)
│   └── processed/
│       ├── games_catalog.csv       # Structured catalog feeding BQ and Vertex AI Search Data Store
│       └── schema.json             # BigQuery schema specification for games_inventory
├── scripts/
│   ├── parse_games_to_csv.py       # Scraper extracting games data from casino JS bundle
│   ├── update_games_md.py          # Script generating games.md mirror from catalog CSV
│   ├── frontend_widget.html        # Embedded integration snippet for casino.oliviervg.com
│   └── delete_orphan_eval.sh       # Script for cleaning up orphan evals on the platform
└── .venv/                          # Local Python virtual environment (gitignored)
```

## Local development

Prerequisites:
- Python 3.10+ (this repo is verified on 3.12).
- `gcloud` CLI authenticated against the `bigquery-demo-396708` project: `gcloud auth login` and `gcloud auth application-default login`.

Setup:

```bash
git clone <repo-url>
cd ovg-casino-concierge
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install cxas-scrapi

# Enable the pre-push lint hook (one-time per clone).
git config core.hooksPath .githooks
```

Pull the latest agent state from CES (overwrites `cxas_app/`):

```bash
cxas pull \
  projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 \
  --target-dir cxas_app/
```

Push your edits back:

```bash
cxas push \
  --app-dir cxas_app/Casino_Concierge \
  --to projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 \
  --env-file cxas_app/Casino_Concierge/environment.json \
  --project-id bigquery-demo-396708 \
  --location us
```

For the full deploy loop (verify → push → smoke test), see the **Deployment workflow** section in `CLAUDE.md`.

---

## Evaluations

Eval YAML lives at `evals/`:

- `evals/goldens/boundaries.yaml` — 5 conversations for platform-level and persona boundaries (AI identity disclosure, out-of-scope weather, persona override attempts, account access, instruction leakage).
- `evals/goldens/discovery.yaml` — 8 conversations validating game discovery, widget triggering, refined and vague search fallback, and multilingual search.
- `evals/goldens/explanations.yaml` — 3 conversations for game rules and mechanics explanations (Roulette, Slots, Bingo).
- `evals/goldens/safety.yaml` — 11 conversations validating underage disclosures, financial distress, gambling addiction triggers, and proper helpline warning / session termination.
- `evals/simulations/simulations.yaml` — 5 multi-turn LLM-driven scripted user journeys.

Quick reference (run from repo root with the venv active):

```bash
PROD_APP=projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8

# Push Goldens after editing (idempotent on display_name)
cxas push-eval --app-name $PROD_APP --file evals/goldens/boundaries.yaml
cxas push-eval --app-name $PROD_APP --file evals/goldens/discovery.yaml
cxas push-eval --app-name $PROD_APP --file evals/goldens/explanations.yaml
cxas push-eval --app-name $PROD_APP --file evals/goldens/safety.yaml

# Run a tagged Goldens subset against prod
cxas run --app-name $PROD_APP --tags boundaries --wait
cxas run --app-name $PROD_APP --tags discovery  --wait
cxas run --app-name $PROD_APP --tags explanations --wait
cxas run --app-name $PROD_APP --tags safety --wait

# Run ALL P0 evaluations on GECX
cxas run --app-name $PROD_APP --tags P0 --wait

# Audio re-run of audio_critical conversations
cxas run --app-name $PROD_APP --tags audio_critical --modality audio --wait

# Local simulations + combined report
mkdir -p /tmp/sim_report
cxas evals report --app-name $PROD_APP --simulation-dir evals/simulations/ \
                  --output-dir /tmp/sim_report --include sims --run
```

Caveat: as of cxas-scrapi 1.2.0, `cxas run` may print `FINAL RESULT: FAIL` while still returning exit code 0. Until that's fixed upstream, scrape stdout for `FINAL RESULT:` rather than relying on the exit code. See the `### Evals` sub-section in `CLAUDE.md` for the full schema gotchas (Goldens `# silent` marker, Simulations top-level-list shape, `--filter-auto-metrics` degenerate flag) and the rationale behind every choice.

`scripts/delete_orphan_eval.sh` is a one-shot CES REST DELETE recipe kept for discoverability — `cxas push-eval` is upsert-only, so this is the path for cleaning up an eval resource that's no longer in the YAML.

---

## Features & Implementation Details

### 1. Dynamic Game Recommendations & Rich Widgets
The agent is capable of asking users about their preferred themes or playstyles and dynamically searching the casino's catalog to provide a grounded recommendation. Instead of just replying with text, it renders a rich visual UI card (a carousel) for the user to interact with, complete with a direct link to play.

*   **Data Source:** Game data (including direct play URLs) was scraped from the frontend Javascript of `https://casino.oliviervg.com`.
*   **Storage:** The 24-game catalog is stored in a BigQuery table (`ovg_casino.games_inventory`).
*   **Search Engine:** A Vertex AI Search Data Store (`ovg_casino_games_catalog`) and Engine (`ovg_casino_games_engine`) index the BigQuery table as *Structured Data*.
*   **Agent Tool:** The agent uses a Datastore Tool named `search_available_games` to retrieve raw JSON matching games, and a Client Function Tool named `display_game_widget` to pipe that data to the frontend for rendering.
*   **Frontend Integration:** The UI is rendered using `ces-messenger` combined with a custom Handlebars template (`game_carousel`) injected onto the page via `scripts/frontend_widget.html`.
*   **Anti-Hallucination:** The agent's instructions contain strict constraints forcing it to *only* recommend games explicitly returned by the `search_available_games` tool.

### 2. Multi-lingual Support
*   The agent is configured with `enableMultilingualSupport` to gracefully switch context and respond in the user's preferred language.
*   Supported Locales: English (`en-US`), French (`fr-FR`), and Spanish (`es-ES`).

### 3. Locale-Aware Responsible Gaming & Session Management
*   The agent detects frustration or mentions of gambling problems.
*   It dynamically executes a custom Python Function Tool (`get_responsible_gaming_helpline`) to resolve the appropriate helpline name and phone number depending on the active locale (`en-GB`, `en-US`, `fr-FR`, or `es-ES`).
*   It responds empathetically using the correct regional organization name and contact number (e.g., *Joueurs Info Service* for French users, *Línea de Ayuda de FEJAR* for Spanish users, and *National Gambling Helpline* for US/UK users), keeping helpline configurations completely isolated from the system instructions.
*   After offering support, or when a user indicates the conversation is over, the agent utilizes the built-in `end_session` tool (with `reason="gambling_concerns"` or `reason="customer_query_ended"`) to gracefully close the interaction.

### 4. Direct Tool Invocation & Callback Retirement
To keep the architecture fully native, robust, and easily maintainable, the **Safety_Handler** agent executes all tool calls directly within its prompt instructions rather than relying on custom programmatic handlers or intermediate callbacks:
*   **Fully Native Flow:** The agent prompt handles all text generation and tool invocation natively, invoking `get_responsible_gaming_helpline` followed directly by `end_session` with appropriate JSON arguments (e.g., `{"reason": "gambling_concerns"}`).
*   **Zero Programmatic Callbacks:** The legacy "Prompt-First Tool-Injection" pattern and its associated custom Python after-agent callbacks have been completely deprecated and retired, removing custom code surfaces and standardizing on pure, native CX Agent Studio functionality.



---

## Technical Learnings & Troubleshooting
*   **Vertex AI Search - BigQuery Structured Import:** When importing custom structured data from BigQuery into a Vertex AI Search Data Store, the system defaults to looking for a column named `_id`. If your unique identifier column is named something else (e.g., `id`), you must explicitly define `"idField": "id"` in the API request payload, otherwise the ingestion will fail.
*   **CX Agent Studio - Tool & Agent References:** Use the canonical CES forms `{@TOOL: tool_name}` and `{@AGENT: Agent Name}` for tool and agent references that the LLM should resolve (enforced by linter rule `I011`). Do not use the older Dialogflow CX form `${TOOL:tool_name}`. Inside simulated dialogue examples, the literal `<agent>Execute tool \`tool_name\` with arguments ...</agent>` pattern followed by a `<tool_response>` block is used to show simulated calls.
*   **Voice Model Selection:** For virtual agents requiring a warm, hospitable persona, the latest `Chirp3-HD` models (`en-US-Chirp3-HD-...`) provide significantly better conversational intonation and lower latency compared to older `Standard` or `News` models.