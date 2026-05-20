# Locale-Aware Responsible Gaming Resources (Python Tool Implementation)

**Date:** 2026-05-20
**Status:** Pending approval; ready for implementation planning.
**Scope:** Fulfill Item 1.1 from `FUTURE_ENHANCEMENTS.md` by introducing per-locale responsible gaming helpline names and numbers that are resolved dynamically at response time via a Python function tool.

---

## 1. Goal

Implement a Python function tool `get_responsible_gaming_helpline` that dynamically resolves responsible gaming resources depending on the user's active locale/language:
- `fr-FR` / French → **Joueurs Info Service** at `09 74 75 13 13`
- `es-ES` / Spanish → **Línea de Ayuda de FEJAR** at `900 200 225`
- `en-US` / US English → **National Gambling Helpline** at `1-800-GAMBLER`
- Default / UK English / Fallback → **National Gambling Helpline** at `0808 8020 133`

This design addresses the user's request to implement the locale resolution as a Python tool, ensuring that the helpline names and phone numbers can be updated in the future without modifying the agent's system prompt (`instruction.txt`).

## 2. Technical Architecture & Lifecycle

### 2.1 Tool Invocation Flow

```
User Distress Signal
      │
      ▼
Safety_Handler Agent
      │
      ▼ (resolves {active_language})
Execute Tool: get_responsible_gaming_helpline(locale="{active_language}")
      │
      ▼ (Python code executes)
Returns JSON: {"helpline_name": "...", "helpline_phone": "...", "locale": "..."}
      │
      ▼
Safety_Handler Agent translates/formats the text-only response:
"I'm sorry to hear that; please consider calling the <helpline_name> at <helpline_phone>."
      │
      ▼ (after_model_callback: ensure_helpline_text)
Appends end_session(reason="gambling_concerns") programmatically
```

### 2.2 Advantages of a Python Tool over Prompt-Only Interpolation
1. **Separation of Concerns:** Prompt handles identity, persona, and text constraints (warmth, single-sentence response limit). Python code handles raw configuration data (helpline directory mapping).
2. **Maintenance Simplicity:** Updates to phone numbers or organization names do not require modifying instructions or translation examples in the prompt, eliminating regression risks on prompt behavior.
3. **Seamless Multi-region Scaling:** Adding a new locale is a pure Python code change (adding a key-value mapping) instead of modifying multiple prompt sections.

## 3. Component Details

### 3.1 Tool Definition: `get_responsible_gaming_helpline`
We define a new Python function tool in GECX under `tools/get_responsible_gaming_helpline/`.

**File:** `cxas_app/Casino_Concierge/tools/get_responsible_gaming_helpline/get_responsible_gaming_helpline.json`
```json
{
  "name": "get_responsible_gaming_helpline",
  "pythonFunction": {
    "name": "get_responsible_gaming_helpline",
    "pythonCode": "tools/get_responsible_gaming_helpline/python_function/python_code.py"
  },
  "executionType": "SYNCHRONOUS",
  "displayName": "get_responsible_gaming_helpline"
}
```

**File:** `cxas_app/Casino_Concierge/tools/get_responsible_gaming_helpline/python_function/python_code.py`
```python
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

def get_responsible_gaming_helpline(locale: str = "") -> dict:
    """Retrieves the responsible gaming helpline name and phone number for a given locale.

    Args:
        locale: The active locale or language code (e.g., 'fr-FR', 'es-ES', 'en-US', 'en-GB').

    Returns:
        A dictionary containing 'helpline_name', 'helpline_phone', and 'locale'.
    """
    # Normalize the locale string to lowercase and strip whitespace
    loc = (locale or "").strip().lower()

    # Map locales to their respective helplines
    if "fr" in loc:
        # France / French
        return {
            "helpline_name": "Joueurs Info Service",
            "helpline_phone": "09 74 75 13 13",
            "locale": "fr-FR"
        }
    elif "es" in loc:
        # Spain / Spanish
        return {
            "helpline_name": "Línea de Ayuda de FEJAR",
            "helpline_phone": "900 200 225",
            "locale": "es-ES"
        }
    elif "us" in loc:
        # US English (Option A chosen by user)
        return {
            "helpline_name": "National Gambling Helpline",
            "helpline_phone": "1-800-GAMBLER",
            "locale": "en-US"
        }
    else:
        # UK English (en-GB) and default fallback
        return {
            "helpline_name": "National Gambling Helpline",
            "helpline_phone": "0808 8020 133",
            "locale": "en-GB"
        }
```

### 3.2 Agent Update: `Safety_Handler.json`
Register the new tool within the Safety Handler's list of supported tools.

**File:** `cxas_app/Casino_Concierge/agents/Safety_Handler/Safety_Handler.json`
```json
  "tools": ["end_session", "get_responsible_gaming_helpline"]
```

### 3.3 Prompt Update: `instruction.txt`
Revise instructions to guide the model to invoke the tool using `{active_language}` and format the result appropriately.

**File:** `cxas_app/Casino_Concierge/agents/Safety_Handler/instruction.txt`
*   **Constraints:** Remove hardcoded phone numbers. Direct the model to always fetch helpline details using the tool and format them in a single sentence.
*   **Taskflow:** Update triggers to instruct the model to:
    1. Call the `get_responsible_gaming_helpline` tool with `locale="{active_language}"`.
    2. Format the response dynamically using the returned dictionary values.
*   **Examples:** Update dialogue examples to include simulated tool calls and responses, matching GECX guidelines:
    `<agent>Execute tool \`get_responsible_gaming_helpline\` with arguments: \`{"locale": "en-GB"}\`</agent>`

### 3.4 Verification & Evaluations
The evaluations will be modified to expect the new dynamic values:
1.  **`safety.yaml` (Goldens)**:
    *   Set `active_language` session parameters (`en-GB`, `en-US`, `fr-FR`, `es-ES`).
    *   Set `agent: "# silent — ..."` on intermediate tool execution turns or assert tool calls.
    *   Update expectations to assert the correct returned helpline phone number and name in the final turn.
2.  **`simulations.yaml` (Simulations)**:
    *   Add `active_language: "en-GB"` to simulation session parameters to verify conversational flow.

## 4. Acceptance Criteria
1.  **Linter Pass:** `cxas lint` returns zero errors and zero warnings.
2.  **Successful Deploy:** `cxas push` and `cxas push-eval` succeed.
3.  **100% Eval Pass:** Running all P0 evaluations (`cxas run --tags P0 --wait`) completes with 100% success rate across all locales.
