# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Configuration and supporting assets for the **OVG Casino Concierge**, a virtual assistant deployed on **Google Cloud Customer Engagement Suite (CX Agent Studio)**. There is no application server here — the agent runtime lives in CX Agent Studio. This repo holds the agent's prompt, the data pipeline that feeds its game search, and the frontend snippet that renders rich UI cards in the embedded `ces-messenger` widget.

## Architecture (the parts that span multiple files)

The agent has three tightly coupled surfaces. Changes to one usually require coordinated changes to the others:

1. **Prompt** — `prompts/system_instructions.md` is the source of truth for agent behavior. XML-tagged sections (`<role>`, `<persona>`, `<constraints>`, `<taskflow>`, `<examples>`). All persona/tool-usage/tone changes start here.
2. **Game catalog data pipeline** — game data is scraped from the casino frontend JS bundle, written to `data/processed/games_catalog.csv` (matches `schema.json`, includes a `url` column), loaded into BigQuery (`ovg_casino.games_inventory`), then indexed by a Vertex AI Search Data Store (`ovg_casino_games_catalog`) + Engine (`ovg_casino_games_engine`). The agent calls a Datastore Tool named `search_available_games` against this index. A human-readable mirror lives at `data/raw/games.md` (regenerated from the CSV; includes direct game URLs).
3. **Frontend rich-UI rendering** — `scripts/frontend_widget.html` is a snippet embedded on `casino.oliviervg.com`. It registers a Handlebars template named `game_carousel` with `ces-messenger`, and the agent's `display_game_widget` Client Function Tool emits `{template_id: "game_carousel", context: {games: [...]}}` which `ces-messenger` intercepts and renders. The same snippet also passes `user_first_name` from Firebase auth into the agent via `setQueryParameters`, and listens for `ces-end-session` to close/clear the chat when the agent calls `end_session`.

Two built-in tools the agent uses without a tool definition: `end_session` (with `reason="customer_query_ended"` or `reason="gambling_concerns"`).

## CX Agent Studio conventions (non-obvious)

- **Tool execution syntax in prompts:** Do **not** use Dialogflow CX `${TOOL:tool_name}` syntax. In `<action>` blocks use natural language: `execute the tool_name tool with arguments key="value".` In `<examples>`, represent calls as `<agent>Execute tool \`tool_name\` with arguments: \`{"key": "value"}\`</agent>` followed by a `<tool_response>` block, then a final `<agent>` natural-language response based on the data.
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

1. Edit `prompts/system_instructions.md` locally first.
2. Push to CX Agent Studio via the `mcp_customer-experience-agent-studio_update_agent` MCP tool. Fetch the latest agent `etag` first.
3. If game data changes: re-run the scraper, reload BigQuery (`ovg_casino.games_inventory`), trigger Vertex AI Search re-import.
4. Commit and push to GitHub (`git push origin main`). Project is on `main`; commit author is `Olivier Van Goethem <ovg@google.com>`.

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

The CES app itself lives in a different location: `projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8` (display name `Casino Concierge`). When calling CES MCP tools, use `locations/us` — not `global`.
