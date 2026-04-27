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
ces/
├── README.md                  # Project overview, architecture, and setup instructions
├── prompts/                   
│   └── system_instructions.md # The core XML-based prompt instructions that govern the agent's persona, constraints, taskflows, and few-shot examples.
├── data/                      
│   ├── raw/                   
│   │   └── games.md           # A detailed, human-readable catalog of all 24 unique games (3 game types x 8 themes) offered by OVG Casino, parsed from the casino's frontend codebase.
│   └── processed/             
│       └── games_catalog.csv  # The structured data representation of games.md, formatted for ingestion into BigQuery and Vertex AI Search.
├── scripts/                   
│   └── (Optional) Scripts used to fetch/parse the website data or deploy the datastore.
├── tools/                     
│   └── schemas/               # (For future use) OpenAPI JSON/YAML schemas for new tools.
├── .env                       # Environment variables (e.g., Google Cloud Project IDs)
└── venv/                      # Python virtual environment
```

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