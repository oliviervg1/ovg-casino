# Gemini AI Agent Instructions for OVG Casino Concierge

Welcome, AI Agent! When you are invoked in this workspace, you are assisting with the development and maintenance of the **OVG Casino Concierge**, a virtual assistant built on **Google Cloud Customer Engagement Suite (CX Agent Studio)**.

Please adhere to the following guidelines and architectural constraints when contributing to this project.

## 1. Project Structure & Responsibilities

*   **`prompts/system_instructions.md`**: This is the source of truth for the agent's behavior. It uses XML tags (`<role>`, `<persona>`, `<constraints>`, `<taskflow>`, `<examples>`). All changes to the agent's logic, tone, or tool usage must be updated here first.
*   **`data/`**: 
    *   `raw/games.md`: Human-readable game catalog scraped from the casino frontend (includes direct URLs).
    *   `processed/games_catalog.csv`: Structured CSV data used to populate the Vertex AI Search Data Store (includes the `url` column).
*   **`scripts/`**: Contains utility scripts (e.g., `parse_games_to_csv.py`) used for data extraction and transformation.

## 2. CX Agent Studio Best Practices

When modifying the agent's instructions, keep the following rules in mind:

### Tool Execution Syntax
Do **NOT** use Dialogflow CX syntax like `${TOOL:tool_name}`. CX Agent Studio uses natural language instructions to execute tools. 
When instructing the agent to call a tool, use this format in the `<action>` block:
> `execute the tool_name tool with arguments key="value".`

In `<examples>` (Few-Shot Prompting), represent a tool call like this:
```xml
<agent>Execute tool `tool_name` with arguments: `{"key": "value"}`</agent>
<tool_response>...data...</tool_response>
<agent>Natural language response based on the data.</agent>
```

### Anti-Hallucination & Constraints
Generative agents can hallucinate tool responses or skip tool calls. Always enforce tool usage with strict `<constraint>` tags:
*   *"You must use the `[tool_name]` tool to answer..."*
*   *"Only recommend items explicitly returned by the tool. Do not hallucinate."*

### Tone and Voice
The agent uses the `en-US-Chirp3-HD-Zephyr` voice model. The prompt tone should be configured as **Warm, Upbeat, Approachable, Professional, and Responsible**. Keep responses concise (2-3 sentences) so the text-to-speech output doesn't sound like a monologue.

## 3. Deployment Workflow

1.  **Local Updates**: Always make changes to the local files (e.g., `prompts/system_instructions.md`) first.
2.  **Cloud Sync**: After modifying the local instructions, you MUST push the changes to CX Agent Studio using the `mcp_customer-experience-agent-studio_update_agent` tool. Make sure to fetch the latest agent `etag` before updating.
3.  **Data Updates**: If game data changes, update the CSV, load it into the BigQuery table (`ovg_casino.games_inventory`), and trigger a re-import into the Vertex AI Search Data Store (`ovg_casino_games_catalog`).

## 4. Git Version Control

*   All confirmed changes must be committed and pushed to the GitHub repository.
*   Use the following Git configuration if not already set:
    *   **Name**: `Olivier Van Goethem`
    *   **Email**: `ovg@google.com`
*   Command to push: `git push origin main`