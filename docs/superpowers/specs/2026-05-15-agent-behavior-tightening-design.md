# Agent Behavior Tightening — Design

**Date:** 2026-05-15
**Status:** Approved during brainstorming session; ready for per-PR implementation planning.
**Parent docs:** [`FUTURE_ENHANCEMENTS.md`](../../../FUTURE_ENHANCEMENTS.md) §4.1 (surfaced findings), §4.7 (I004 trigger rewrite).
**Scope:** Tighten the Phase C eval suite to express expected agent behavior for 3 remaining work items (Finding 1: Silent goodbye, Finding 2: Fallback hallucination, Finding 5: Multilingual override, and I004 trigger rewrite).

---

## 1. Goal

Make the Goldens + Simulations the source of truth for the Casino Concierge's behavior. For each finding, (a) tighten or add the eval to express the expected behavior, (b) confirm it FAILS against the current prompt (RED), (c) update `instruction.txt`, (d) confirm it PASSES (GREEN).

## 2. Scope — two themed PRs remaining

| PR | Theme | Items | Touches |
|---|---|---|---|
| **2** | UX/correctness | 1 (silent goodbye + implicit-goodbye coverage), 2 (fallback hallucination) | `instruction.txt`, `evals/goldens/happy_path.yaml`, `evals/goldens/tool_usage.yaml` |
| **3** | Config alignment | 5 (multilingual override), I004 trigger rewrite | `instruction.txt`, `evals/simulations/multi_turn.yaml`, `cxaslint.yaml` |

PRs ship sequentially: UX → Config. Each PR branches off main after the prior merges.

**TDD loop per finding:**
1. Tighten/add the eval YAML in repo. Push to prod via `cxas push-eval`.
2. `cxas run --tags <relevant-tag> --wait` → confirm FAIL (red).
3. Update `instruction.txt` locally. Push via `cxas push`.
4. Manual smoke-test on `https://casino.oliviervg.com`.
5. Re-run `cxas run --tags <relevant-tag> --wait` → confirm PASS (green).

---

## 3. PR 2 — UX/correctness

### 3.1 Finding 1: Silent end_session for goodbye + implicit-goodbye coverage

**Current state:**
- `evals/goldens/happy_path.yaml::goodbye_brief` and `evals/goldens/tool_usage.yaml::goodbye_ends_session` use `agent: "# silent — agent fires end_session immediately without preceding text"`.
- Constraint at `instruction.txt:29` says *"…you MUST immediately execute the end_session tool. Do not ask if they need anything else or wait for a further response"* — the agent interprets "immediately" as "no preceding text".
- User has observed in production that the agent often fails to fire `end_session` on conversational closings beyond explicit "Bye!" (e.g., "I'm all good", "That's all I needed").

**Eval tightening — pin canonical responses:**

```yaml
# happy_path::goodbye_brief
- user: "Actually nevermind. Bye!"
  tool_calls:
    - action: end_session
      args:
        reason: "customer_query_ended"
  agent: "No problem at all! I hope to see you again soon. Goodbye!"
```

**New evals — implicit-goodbye coverage (added to `happy_path.yaml`):**
- Covers phrasings like "I'm all good, thanks!", "That's all I needed, thanks.", "Got it, thanks!", "Sounds good, I'll check it out."

**Prompt change** (`instruction.txt`):

Replace the goodbye constraint at line 29:
*"When the user says goodbye OR signals the conversation is over with phrasings like 'I'm all good', 'That's all', 'Got it, thanks', 'Sweet, I'm set', 'Sounds good', or any short conversational closing, briefly wish them well in 1-2 short sentences AND then execute the end_session tool in the same turn. Do not ask if they need anything else or wait for a further response."*

### 3.2 Finding 2: Hallucinated fallback themes (catch-all search)

**Current state:**
- Constraint at `instruction.txt:28` says *"If you don't get any data back from the tool, respond that you don't currently have a game matching their exact preferences, but offer the standard Roulette, Slots, or Bingo."*
- Example at `instruction.txt:178-183` violates the constraint by naming unverified themes like *"Space, Jungle, or the Wild West"*.

**Fix:** Instead of falling back to bare game-type names, the agent should run a **third catch-all search** to discover what IS available, then display real games via the widget.

**Prompt change** (`instruction.txt`):

Replace the `Handle No Games Found` step:
- Action: Run one final catch-all search (e.g., `{@TOOL: search_available_games}` with a query like "popular slots") to discover available games. Display results via `{@TOOL: display_game_widget}`. Acknowledge that the requested theme isn't available.

Tighten the related constraint: *"Only mention specific themes if those themes appear in results returned by {@TOOL: search_available_games}. Never invent themes."*

---

## 4. PR 3 — Config alignment

### 4.1 Finding 5: Multilingual override

**Current state:**
- `instruction.txt:19` constraint *"Output plain spoken English only…"* contradicts the multilingual config. Agent responds *"I can only converse in English"* to French queries.

**Prompt change** (`instruction.txt`):

Replace the single constraint with two:
1. *"Match the user's language. Respond in whichever language the user uses (en-US, fr-FR, or es-ES)."*
2. *"Never use markdown formatting... Your responses are rendered as plain text... rich UI uses the {@TOOL: display_game_widget} tool instead."*

### 4.2 I004 trigger rewrite

**Current state:**
- `cxaslint.yaml` has `I004: info` due to negative conditions in re-engagement triggers.

**Prompt change** (`instruction.txt`):
Rewrite re-engagement triggers to use positive conditions (e.g., *"Ten seconds of silence have elapsed"* instead of *"The user has not responded"*).

**`cxaslint.yaml` change**: Remove the `I004: info` override.

---

## 5. Acceptance criteria summary

1. Finding 1 (Silent goodbye) and Finding 2 (Fallback hallucination) marked shipped.
2. Finding 5 (Multilingual override) and I004 trigger rewrite shipped.
3. `cxas lint` exits 0/0/0.
4. New Goldens cover implicit goodbye phrasings.
5. `multilingual_switch` simulation asserts French response.
