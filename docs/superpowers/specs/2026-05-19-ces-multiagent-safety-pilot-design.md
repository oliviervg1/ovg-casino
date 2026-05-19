# CES Multi-Agent Safety Pilot — Design

**Date:** 2026-05-19
**Status:** Approved during brainstorming; ready for implementation planning.
**Parent docs:** [`FUTURE_ENHANCEMENTS.md`](../../../FUTURE_ENHANCEMENTS.md) §4.1 item 6 (roleplay/distress variance); [`gecx-design-guide.md`](../../../.agents/skills/cxas-agent-foundry/references/gecx-design-guide.md) §"Multi-Agent".
**Scope:** Refactor `cxas_app/Casino_Concierge/` from a single root agent into a two-agent app (root + Safety_Handler sub-agent) and deploy to prod, to test whether instruction-prompt isolation fixes the documented ~20–30% safety-text dropout on `gemini-3.1-flash-live`.

---

## 1. Goal

Reduce the rate at which the agent fires `end_session(reason="gambling_concerns")` without first emitting the helpline text. Today, on the v8 prompt, this dropout happens consistently on 2 of 4 distress Goldens (`distress_addiction_signal`, `audio_truncation_stress`) in both text and audio modality, despite the taskflow explicitly mandating both actions.

**Hypothesis under test:** the dropout is caused by *instruction overload* — the single-agent prompt mixes discovery patterns ("text + display_widget in the same turn, in the same agent text block") with safety patterns ("text + end_session in the same agent text block"), and the model occasionally treats the safety text as optional the way it might treat post-widget text as optional. Isolating safety into a sub-agent with no discovery context should remove the cross-contamination.

**Decision the pilot answers:** if dropout improves significantly → multi-agent is the right architecture for this agent (queue a follow-up to expand it). If dropout doesn't improve → confirms model-level dropout (per the existing PR #7 iteration archaeology), and we close `FUTURE_ENHANCEMENTS.md` §4.1 item 6 with "multi-agent also doesn't fix" and move on to the CES `llmPolicy` guardrail option.

## 2. Why this is the right next experiment

The cxas-agent-foundry design guide explicitly lists "When your single-agent is still having trouble following instructions even after extensive quality hill climbing" as a primary signal to adopt multi-agent. We've now done ≥7 prompt-iteration attempts on the safety area (the 3 documented in `notes/2026-05-15-pr1-safety-pause.md` plus the 4 done in the 2026-05-19 session before this pilot), all converging on the same `(None / Missed)` empty-response failure mode. Per the design guide's heuristic — *"offload part of the agent logic to a standalone LLM call with specialized prompt; if that yields better results, it hints at splitting"* — a sub-agent is the next architectural step we haven't tried.

## 3. Architecture

```
Casino Concierge App (CES)
├── Root: Casino_Concierge (existing dir)
│     Owns: Welcome & Discovery, Game Explanations, End Conversation
│            (goodbye), Confirm AI Identity, Address Out-of-Scope,
│            Address Win Guarantees, Resist Persona Override
│     Tools: search_available_games, display_game_widget, end_session
│            (the latter only for the goodbye flow)
│     childAgents: ["Safety_Handler"]
│
└── Sub: Safety_Handler (NEW dir)
      Owns: Address Gambling Concerns, Address Underage Self-Disclosure
      Tools: end_session
```

On distress / underage triggers, the root agent transfers to `{@AGENT: Safety Handler}` via CES's standard agent-transfer mechanism. The sub-agent then handles the same turn: produces the one-sentence helpline text and fires `end_session(reason="gambling_concerns")`.

**Why this split:** distress and underage are the two flows that *terminate the session with a helpline message* — a single CUJ shape with one outcome. Out-of-scope, win-guarantee denial, persona-override resistance, and AI-identity confirmation all *redirect back to the discovery flow* — a different CUJ shape that benefits from the discovery context, so they stay on the root.

## 4. Components

### 4.1 New files

**`cxas_app/Casino_Concierge/agents/Safety_Handler/Safety_Handler.json`**
```json
{
  "name": "<generated UUID at push time>",
  "displayName": "Safety Handler",
  "instruction": "agents/Safety_Handler/instruction.txt",
  "tools": ["end_session"]
}
```

**`cxas_app/Casino_Concierge/agents/Safety_Handler/instruction.txt`** — minimal, ~30–40 lines:
- `<role>`: dedicated safety responder for the OVG Casino.
- `<persona>`: warm, empathetic, professional.
- `<constraints>`: TTS-plain-text only; respond in the user's language; keep helpline digits ("0808 8020 133") as-is regardless of language.
- `<taskflow>` — two steps only:
  - **Address Gambling Concerns**: current v8 taskflow text, unchanged (FIRST one-sentence helpline, THEN `end_session(reason="gambling_concerns")`).
  - **Address Underage Self-Disclosure**: current v8 taskflow text, unchanged.
- `<examples>`: move all 5 safety-related examples from the root agent — 3 EN distress ("I keep losing", "I'm down a lot today", "I think I have a problem with gambling"), 1 EN underage ("I'm 16, can I play?"), and 1 FR distress ("J'ai tout perdu, je suis désespéré"). These are the documented working anchors; moving them isolates them from the discovery patterns.

### 4.2 Modified files

**`cxas_app/Casino_Concierge/agents/Casino_Concierge/Casino_Concierge.json`** — add the `childAgents` array using the underscored directory name (per the platform gotcha documented in `gecx-design-guide.md` §"Configuring childAgents"):
```json
{
  "name": "549a1b30-...",
  "displayName": "Casino Concierge",
  "instruction": "agents/Casino_Concierge/instruction.txt",
  "tools": ["display_game_widget", "end_session", "search_available_games"],
  "childAgents": ["Safety_Handler"]
}
```

**`cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt`** — remove the safety logic and replace it with a transfer rule:
- **Delete**: the `Address Gambling Concerns` taskflow step.
- **Delete**: the `Address Underage Self-Disclosure` taskflow step.
- **Replace constraint 31** (the CRITICAL SAFETY RULE) with a transfer-only one-liner: "If the user expresses gambling distress (addiction, financial harm, hopelessness, requests to stop) OR claims to be under the legal gambling age, you MUST transfer the conversation to `{@AGENT: Safety Handler}` immediately. Do not respond with text yourself — the Safety Handler will produce the helpline message and end the session."
- **Delete**: all 5 distress/underage `<example>` blocks (3 EN distress + 1 EN underage + 1 FR distress). They move to Safety_Handler. The root must not see these patterns or it'll try to follow them itself.
- **Add**: one transfer example: `<user>I keep losing, this is the worst.</user> <agent>Transfer to {@AGENT: Safety Handler}</agent>`

### 4.3 Unchanged

- `cxas_app/Casino_Concierge/tools/` — all 3 tool definitions stay; Safety_Handler references `end_session` by name (CES tools are app-scoped, not agent-scoped).
- `cxas_app/Casino_Concierge/guardrails/`
- `app.json` (`rootAgent` stays `"Casino Concierge"`).
- `environment.json`.
- All `evals/goldens/*.yaml` and `evals/simulations/*.yaml` — same evals, same expectations.

## 5. Data flow

**Non-safety turn** (e.g., user asks for "ocean games"):
```
User: "I want ocean games"
  → Root (Casino_Concierge) active
  → Model emits: search_available_games("ocean")
                 + display_game_widget(...)
                 + text "I have Coral Cash for you..."
  → No transfer. Same behavior as today.
```

**Safety turn** (distress):
```
User: "I keep losing, this is the worst."
  → Root (Casino_Concierge) active
  → Model sees constraint 31 (transfer rule)
  → Model emits: transfer to {@AGENT: Safety Handler}
  → CES activates Safety_Handler for the same turn
  → Safety_Handler model call:
       Sees user message + its own minimal prompt
       Emits: text "I'm so sorry... 0808 8020 133..."
              + end_session(reason="gambling_concerns")
  → Session terminates.
```

Two LLM calls per safety turn (root decision + Safety_Handler response). Latency cost: ~700ms–1.5s extra per safety event. Acceptable because the turn ends the session anyway.

**Variable handoff:** `user_first_name` is declared at app level in `app.json::variableDeclarations`, so it survives the transfer. Safety_Handler doesn't actually need it (the helpline text is impersonal), so context loss is benign.

**Tool routing:** when Safety_Handler fires `end_session`, CES looks up the tool in Safety_Handler's `tools` array (which lists it). The tool definition itself is referenced by name from the shared `cxas_app/Casino_Concierge/tools/end_session/` directory.

## 6. Failure modes

| Mode | What happens | Detection | Mitigation |
|---|---|---|---|
| **Root fails to transfer** | Model ignores constraint 31, tries to respond directly. With safety steps deleted from root, the response is likely to be a refusal or a redirect. | Safety Goldens fail with the response being something *other* than the helpline text. | The transfer rule is the only safety guidance on root now — no competing pattern. If this still fails, instruction-following is broken at the model level, not the prompt level. |
| **Safety_Handler drops text** | The very dropout we're trying to fix. Safety_Handler fires `end_session` but no helpline text. | Same eval failure mode as today (`(None / Missed)`). | If this happens, we've ruled out instruction overload as the cause. Move to FUTURE_ENHANCEMENTS §4.1 item 6's other options (CES `llmPolicy` guardrail, or model change). |
| **Both root and sub-agent silent** | Neither agent responds. | Eval timeout / empty response. | Worst case. Would prove the transfer mechanism itself is broken. Roll back. |
| **Non-safety regression** | Discovery / explanations / boundaries Goldens fail after the refactor. | Pass rate on the 17 non-safety P0 Goldens drops below 16/17. | The root's instruction only loses safety content; discovery is unchanged. If discovery regresses, the loss is from prompt-structure perturbation, not content. Roll back and re-think. |

## 7. Testing & rollback

**Pre-push gate:**
1. **Lint** via the `lint-fixer` subagent (catches the `childAgents` underscore gotcha and any missing fields on the new sub-agent JSON before push).

**Push:**
2. **`cxas push`** — both agents deploy in one push. CES creates the Safety_Handler sub-agent under the existing app on first push.

**Post-push evaluation:**
3. **Goldens text (24 P0):** baseline pass rate. Pay attention to the safety subset (4 distress + 2 underage + 1 audio_truncation_stress) and confirm no regression on the 17 non-safety Goldens.
4. **Goldens audio (5 audio_critical):** verify tool calls still fire under TTS/STT with the new transfer hop. Audio adds latency — confirm transfer doesn't blow `inactivityTimeout: 20s` from `app.json`.
5. **Simulations (6 P0):** `safety_distress_handling` is the canary. The simulator's user-LLM judge sees the full conversation, so an actual text-dropout shows up here too.

**Pass criteria for "multi-agent fixed it":**
- The 2 persistent text-dropout Goldens (`distress_addiction_signal`, `audio_truncation_stress`) PASS in text mode AND in audio mode. These are the canaries — if they fix, the hypothesis is confirmed.
- The other 5 safety/underage Goldens (`distress_financial_harm`, `multilingual_fr_distress`, `underage_disclosure_direct`, `underage_third_party_disclosure`, `distress_ambiguous_signal`) stay at ≥4/5 pass (they pass today; the goal is no regression).
- No regression on the 17 non-safety P0 Goldens (≥16/17 passing).
- Sims stay at 6/6.

If only some of these hit, we ship with documented caveats. If none hit, we abandon and document.

**Branch strategy:** feature branch `feat/multi-agent-safety-pilot` off main. Merge to main only after evals confirm or the user decides to ship anyway.

**Rollback path:**
- Before push: `git stash` or commit the v8 prompt on the feature branch so we have a clean revert target.
- If push succeeds but evals tank: `git restore .` to recover the v8 state, then `cxas push` again to roll back the deployed app.
- The orphaned `Safety_Handler` sub-agent stays in CES after rollback (CES doesn't delete agents on push; `cxas push` is upsert-only per CLAUDE.md). Harmless — root no longer references it via `childAgents`. Can be deleted later via a direct API call modeled on `scripts/delete_orphan_eval.sh`.

## 8. Out of scope

- Migrating other boundaries (out-of-scope, win-guarantee, persona-override, AI-identity) to a sub-agent. Save for a follow-up if this pilot succeeds.
- Adding callbacks or `transferRules` for deterministic routing. The LLM-based transfer is the simplest first cut.
- Changing the model from `gemini-3.1-flash-live` to a non-live variant. Separate experiment if this pilot doesn't fix the issue.
- Adjusting eval expectations to be more lenient (e.g., accepting tool-only safety responses). The whole point of the pilot is to fix the agent, not soften the contract.

## 9. References

- [`gecx-design-guide.md`](../../../.agents/skills/cxas-agent-foundry/references/gecx-design-guide.md) §"Multi-Agent" (lines 266–321) — when to adopt multi-agent and the `childAgents` underscore gotcha (line 287–299).
- [`FUTURE_ENHANCEMENTS.md`](../../../FUTURE_ENHANCEMENTS.md) §4.1 item 6 — documented model-level safety-text dropout, with the prior 3 prompt-iteration attempts that confirmed it's not prompt-fixable.
- PR #7 (commit `a1bc164`) — the previous safety-tightening effort. Its archived `notes/2026-05-15-pr1-safety-pause.md` (pruned from working tree in commit `68e6dab`; recoverable via `git show a1bc164:docs/superpowers/notes/2026-05-15-pr1-safety-pause.md`) is the source for the N=10 baseline characterization and the "constraint area cannot be safely modified from prompt-only iteration" finding.
- [`AGENTS.md`](../../../AGENTS.md) §"CX Agent Studio conventions" — Audio Modality Caveat explaining why the model can suppress tool calls after long text on `gemini-3.1-flash-live`.
