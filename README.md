# OVG Casino Concierge - CX Agent Studio Setup

This repository contains the configuration and planning documentation for the **Casino Concierge** virtual assistant, built using Google Cloud's Customer Engagement Suite (CX Agent Studio).

## Agent Overview
The Casino Concierge is designed to act as a highly knowledgeable, vibrant, and welcoming virtual host for the OVG Casino. Its primary goal is to provide exceptional customer service, guide beginners, explain game mechanics (Slots, Roulette, Bingo), and help players discover games based on their personal taste.

### Key Characteristics
*   **Role:** Vibrant, welcoming, and knowledgeable Casino Concierge.
*   **Voice:** `en-US-Chirp3-HD-Zephyr` (A warm, highly expressive, conversational American female voice utilizing Google's latest Chirp 3 HD conversational AI model).
*   **Tone:** Warm, Upbeat, Approachable, Professional, and Responsible.
*   **Guardrails:** Focuses on entertainment, never guarantees a win, and provides the UK National Gambling Helpline (`0808 8020 133`) for users expressing frustration or gambling concerns.

## Project Structure
```text
ovg-casino-concierge/
├── README.md                       # Project overview, architecture, and setup instructions
├── CLAUDE.md                       # Working instructions for Claude Code (and any other coding agent)
├── cxas_app/                       # Source of truth for the CES agent (cxas-scrapi layout)
│   └── Casino_Concierge/
│       ├── app.json                # App config: voice, locales, model, guardrails, logging
│       ├── environment.json        # Per-env values resolved into tool $env_var placeholders
│       ├── agents/Casino_Concierge/
│       │   ├── Casino_Concierge.json   # Agent metadata
│       │   └── instruction.txt         # XML-tagged system prompt (canonical)
│       ├── tools/
│       │   ├── search_available_games/ # Datastore tool → Vertex AI Search
│       │   └── display_game_widget/    # Client function tool → Handlebars carousel
│       ├── guardrails/                 # Native CES guardrails (Prompt + Safety)
│       └── evaluations/                # Native CES evaluations (eval suite expanded in Phase C)
├── data/
│   ├── raw/games.md                # Human-readable catalog of all 24 games
│   └── processed/
│       ├── games_catalog.csv       # Structured catalog for BigQuery / Vertex AI Search
│       └── schema.json             # BigQuery schema for games_inventory
├── scripts/
│   ├── parse_games_to_csv.py       # Scrapes casino frontend bundle → games_catalog.csv
│   ├── update_games_md.py          # Regenerates games.md from the CSV
│   └── frontend_widget.html        # Embedded snippet for casino.oliviervg.com (Handlebars carousel)
├── docs/superpowers/               # Specs and implementation plans (cxas retrofit roadmap)
├── .env                            # Google Cloud env vars (gitignored)
└── .venv/                          # Python virtual environment (gitignored)
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

- `evals/goldens/happy_path.yaml` — 10 single-turn conversions of the prompt's example dialogue (P0, happy_path, audio_critical tags).
- `evals/goldens/tool_usage.yaml` — 5 conversations asserting tool-call contracts (search → widget, end_session reasons).
- `evals/goldens/jailbreak.yaml` — 18 conversations across 5 attack families (prompt_injection, roleplay_override, scope_creep, win_guarantee, underage). Threshold: 100% pass.
- `evals/simulations/multi_turn.yaml` — 5 multi-turn LLM-driven scripted user journeys.

Quick reference (run from repo root with the venv active):

```bash
PROD_APP=projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8

# Push Goldens after editing (idempotent on display_name)
cxas push-eval --app-name $PROD_APP --file evals/goldens/happy_path.yaml
cxas push-eval --app-name $PROD_APP --file evals/goldens/tool_usage.yaml
cxas push-eval --app-name $PROD_APP --file evals/goldens/jailbreak.yaml

# Run a tagged Goldens subset against prod
cxas run --app-name $PROD_APP --tags happy_path --wait
cxas run --app-name $PROD_APP --tags tool_usage --wait
cxas run --app-name $PROD_APP --tags jailbreak  --wait

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

### 3. Responsible Gaming & Session Management
*   The agent detects frustration or mentions of gambling problems.
*   It is instructed to provide an empathetic response and offer the UK National Gambling Helpline (`0808 8020 133`).
*   After offering support, or when a user indicates the conversation is over, the agent utilizes the built-in `end_session` tool (with `reason="gambling_concerns"` or `reason="customer_query_ended"`) to gracefully close the interaction.

---

## Technical Learnings & Troubleshooting
*   **Vertex AI Search - BigQuery Structured Import:** When importing custom structured data from BigQuery into a Vertex AI Search Data Store, the system defaults to looking for a column named `_id`. If your unique identifier column is named something else (e.g., `id`), you must explicitly define `"idField": "id"` in the API request payload, otherwise the ingestion will fail.
*   **CX Agent Studio - Tool Execution Syntax:** To instruct an agent to execute a tool in CX Agent Studio, you do not use the raw `${TOOL:}` syntax in the instruction prompt. Instead, provide clear natural language directions in the `<taskflow>`'s `<action>` block (e.g., *"...execute the `end_session` tool with arguments reason='customer_query_ended'."*).
*   **Voice Model Selection:** For virtual agents requiring a warm, hospitable persona, the latest `Chirp3-HD` models (`en-US-Chirp3-HD-...`) provide significantly better conversational intonation and lower latency compared to older `Standard` or `News` models.