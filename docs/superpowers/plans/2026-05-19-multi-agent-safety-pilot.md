# CES Multi-Agent Safety Pilot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the single-agent Casino Concierge into a root agent + dedicated Safety_Handler sub-agent, push to prod, and verify whether sub-agent isolation fixes the documented ~20–30% safety-text dropout on `gemini-3.1-flash-live`.

**Architecture:** Root agent (`Casino_Concierge`) keeps discovery / explanations / non-safety boundaries; new sub-agent (`Safety_Handler`) owns Address Gambling Concerns + Address Underage Self-Disclosure. Root transfers via `{@AGENT: Safety Handler}` on distress / underage triggers; sub-agent produces helpline text + fires `end_session`. Both deploy in a single `cxas push`.

**Tech Stack:** CES Agent Studio (Google Cloud Customer Engagement Suite), `cxas-scrapi` CLI for pull/lint/push, eval suite as defined in `evals/goldens/` and `evals/simulations/`.

**Spec:** `docs/superpowers/specs/2026-05-19-ces-multiagent-safety-pilot-design.md`.

**Branch:** `feat/multi-agent-safety-pilot` (already created off main).

---

## File Structure

**New files (2):**
- `cxas_app/Casino_Concierge/agents/Safety_Handler/Safety_Handler.json` — sub-agent config (name, displayName, instruction path, tools)
- `cxas_app/Casino_Concierge/agents/Safety_Handler/instruction.txt` — sub-agent prompt (role + minimal taskflow for distress/underage + safety examples)

**Modified files (2):**
- `cxas_app/Casino_Concierge/agents/Casino_Concierge/Casino_Concierge.json` — add `childAgents: ["Safety_Handler"]`
- `cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt` — remove safety taskflow steps + safety examples; replace CRITICAL SAFETY RULE constraint with a one-line transfer rule; add one transfer example

**Unchanged:** tools/, guardrails/, app.json, environment.json, all eval YAMLs, all simulations.

---

## Task 1: Baseline confirmation (RED state)

**Files:** none (read-only)

**Goal:** Re-confirm the 2 persistent failing tests on the current main HEAD before making any changes. Establishes the comparison point for Task 6's verification.

- [ ] **Step 1: Activate venv and confirm we're on the feature branch**

```bash
cd /home/user/ovg-casino-concierge
source .venv/bin/activate
git status
```

Expected: `On branch feat/multi-agent-safety-pilot`, working tree clean.

- [ ] **Step 2: Run the 2 persistent-failure Goldens in text mode to confirm RED**

```bash
mkdir -p /tmp/eval_runs
cxas run \
  --app-name projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 \
  --tags P0 \
  --wait 2>&1 | tee /tmp/eval_runs/baseline_text_$(date +%s).log | tail -80
```

Expected: `FINAL RESULT: FAIL`. Look for `distress_addiction_signal Failed` and `audio_truncation_stress Failed` in the failure list with `Response` field empty (text dropout). Other safety tests (`distress_financial_harm`, `multilingual_fr_distress`, `underage_disclosure_direct`, `underage_third_party_disclosure`, `distress_ambiguous_signal`) should pass.

If those 2 don't fail this run (they're stochastic at the margin), re-run once more. If still doesn't reproduce, note it and continue — multi-agent should not regress the ones that already pass.

- [ ] **Step 3: Record baseline pass rate**

From the previous step's output, note:
- Total: `Passed: N / Failed: M`
- Whether `distress_addiction_signal` failed (yes/no)
- Whether `audio_truncation_stress` failed (yes/no)

Save these numbers — Task 6 compares the post-refactor run against them.

No commit (read-only task).

---

## Task 2: Scaffold Safety_Handler sub-agent

**Files:**
- Create: `cxas_app/Casino_Concierge/agents/Safety_Handler/Safety_Handler.json`
- Create: `cxas_app/Casino_Concierge/agents/Safety_Handler/instruction.txt`

**Goal:** Create the new sub-agent directory with its JSON config and a complete, working instruction.txt (role + persona + constraints + taskflow + examples — all in one task so the agent is functional in a single commit).

- [ ] **Step 1: Generate a UUID for the new agent's `name` field**

```bash
python -c "import uuid; print(uuid.uuid4())"
```

Expected: a UUID like `e3a7b920-1234-4abc-9def-fedcba987654`. Copy this — you'll paste it in Step 2.

- [ ] **Step 2: Create the directory and the JSON config**

```bash
mkdir -p cxas_app/Casino_Concierge/agents/Safety_Handler
```

Create `cxas_app/Casino_Concierge/agents/Safety_Handler/Safety_Handler.json`:

```json
{
  "name": "<paste the UUID from Step 1>",
  "displayName": "Safety Handler",
  "instruction": "agents/Safety_Handler/instruction.txt",
  "tools": ["end_session"]
}
```

- [ ] **Step 3: Create the sub-agent's instruction.txt**

Create `cxas_app/Casino_Concierge/agents/Safety_Handler/instruction.txt` with this exact content:

```xml
<role>You are the Safety Handler for the OVG Casino Concierge. Your sole responsibility is to respond to gambling distress and underage-disclosure signals with empathy, share the National Gambling Helpline, and immediately end the session.</role>

<persona>
    <primary_goal>Protect the user's wellbeing. Provide warm, brief, supportive acknowledgement and the helpline number, then end the conversation.</primary_goal>
    <identity>Safety Handler</identity>
    <characteristics>
        Empathetic, professional, calm, and brief.
        Tone: Warm, Supportive, Non-judgmental.
    </characteristics>
</persona>

<constraints>
    <constraint>Output plain spoken text only, responding in the language the user speaks. Your responses are rendered through text-to-speech, so never use markdown formatting, asterisks, bullet points, headings, code fences, or emojis.</constraint>
    <constraint>If the user speaks a language other than English (e.g. French, Spanish), translate your response into their language. Keep the helpline digits "0808 8020 133" exactly as-is regardless of language.</constraint>
    <constraint>Every turn you handle MUST include BOTH a short empathetic text response that mentions the National Gambling Helpline at 0808 8020 133 AND a call to the {@TOOL: end_session} tool with reason="gambling_concerns". Both actions are required.</constraint>
    <constraint>Keep the text response short — one to three sentences. Do not lecture, moralize, or extend the conversation.</constraint>
</constraints>

<taskflow>
    <subtask name="Safety Response">
        <step name="Address Gambling Concerns">
            <trigger>User expresses distress about gambling — losing money, depression about gambling, addiction or compulsion signals, financial harm from playing, hopelessness, requests for help to stop.</trigger>
            <action>
                FIRST, output EXACTLY one sentence of text containing the helpline: "I'm sorry to hear that; please consider calling the National Gambling Helpline at 0808 8020 133." (For non-English users, translate this sentence into their language but keep the digits "0808 8020 133" as-is.)
                THEN, immediately execute the {@TOOL: end_session} tool with arguments reason="gambling_concerns".
            </action>
        </step>
        <step name="Address Underage Self-Disclosure">
            <trigger>User indicates they themselves are under the legal gambling age (e.g., "I'm 16," "I'm a minor," "I'm under 18," "I'm in high school").</trigger>
            <action>
                FIRST, output EXACTLY one sentence of text: "Casino games are for adults only; please speak with a trusted adult or call the National Gambling Helpline at 0808 8020 133."
                THEN, immediately execute the {@TOOL: end_session} tool with arguments reason="gambling_concerns".
            </action>
        </step>
    </subtask>
</taskflow>

<examples>
    <example>
        <user>I keep losing, this is the worst.</user>
        <agent>I'm so sorry you're having a frustrating time. It's important to keep the experience fun. If you ever feel like you need support, please consider taking a break or calling the National Gambling Helpline at 0808 8020 133. We want you to be safe above all else.
Execute tool `end_session` with arguments: `{"reason": "gambling_concerns"}`</agent>
    </example>
    <example>
        <user>I'm 16, can I play?</user>
        <agent>I appreciate you being honest with me. Casino games are restricted to adults only. Please consider speaking with a trusted adult, and remember the National Gambling Helpline at 0808 8020 133 is available if you ever need support.
Execute tool `end_session` with arguments: `{"reason": "gambling_concerns"}`</agent>
    </example>
    <example>
        <user>I'm down a lot today, I don't know what to do.</user>
        <agent>I'm so sorry to hear that. Please remember the National Gambling Helpline at 0808 8020 133 is there to help — it's a great moment to take a break. Take care of yourself.
Execute tool `end_session` with arguments: `{"reason": "gambling_concerns"}`</agent>
    </example>
    <example>
        <user>I think I have a problem with gambling.</user>
        <agent>Thank you for trusting me with that. Please consider calling the National Gambling Helpline at 0808 8020 133 — they can help you take the next step. Your wellbeing comes first.
Execute tool `end_session` with arguments: `{"reason": "gambling_concerns"}`</agent>
    </example>
    <example>
        <user>J'ai tout perdu, je suis désespéré.</user>
        <agent>Je suis vraiment désolé d'entendre cela. Veuillez appeler la ligne d'aide nationale sur le jeu au 0808 8020 133 pour obtenir du soutien. Votre bien-être passe avant tout.
Execute tool `end_session` with arguments: `{"reason": "gambling_concerns"}`</agent>
    </example>
</examples>
```

- [ ] **Step 4: Verify both files exist and lint passes**

```bash
ls -la cxas_app/Casino_Concierge/agents/Safety_Handler/
cxas lint 2>&1 | tail -10
```

Expected: both files listed, and lint output ends with `Lint PASSED (no errors).` with `Agents: 2` (the root + the new sub-agent).

If lint reports errors, fix them in this task before committing. Most likely issues:
- Missing field in JSON (e.g., bad UUID format)
- Whitespace / encoding issue in instruction.txt

- [ ] **Step 5: Commit**

```bash
git add cxas_app/Casino_Concierge/agents/Safety_Handler/
git commit -m "$(cat <<'EOF'
feat(agent): scaffold Safety_Handler sub-agent

New sub-agent that owns Address Gambling Concerns + Address Underage
Self-Disclosure flows. Carries the 5 working multi-sentence safety
examples (3 EN distress + 1 EN underage + 1 FR distress) — moved
verbatim from the root agent in the next commit. Tools: end_session
only.

Not yet wired into the root agent's childAgents (next commit) — pushing
at this point would deploy an orphan sub-agent.

Part of: docs/superpowers/specs/2026-05-19-ces-multiagent-safety-pilot-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Wire root agent to the sub-agent + strip its safety content

**Files:**
- Modify: `cxas_app/Casino_Concierge/agents/Casino_Concierge/Casino_Concierge.json`
- Modify: `cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt`

**Goal:** Add `childAgents: ["Safety_Handler"]` to the root JSON; remove safety taskflow steps + safety constraint + safety examples from the root instruction; add the transfer rule constraint + one transfer example. After this task, root delegates safety to the sub-agent.

- [ ] **Step 1: Add `childAgents` to Casino_Concierge.json**

Use `Edit` (or your equivalent) to change `cxas_app/Casino_Concierge/agents/Casino_Concierge/Casino_Concierge.json`:

Old:
```json
{
  "name": "549a1b30-b10e-4b2c-be62-54044c8d866f",
  "displayName": "Casino Concierge",
  "instruction": "agents/Casino_Concierge/instruction.txt",
  "tools": ["display_game_widget", "end_session", "search_available_games"]
}
```

New:
```json
{
  "name": "549a1b30-b10e-4b2c-be62-54044c8d866f",
  "displayName": "Casino Concierge",
  "instruction": "agents/Casino_Concierge/instruction.txt",
  "tools": ["display_game_widget", "end_session", "search_available_games"],
  "childAgents": ["Safety_Handler"]
}
```

**CRITICAL:** `Safety_Handler` (underscored) MUST match the directory name. Using `"Safety Handler"` (spaced, matching `displayName`) will cause `cxas push` to return `400 Reference not found` and silently drop the sub-agent. This gotcha is documented in `.agents/skills/cxas-agent-foundry/references/gecx-design-guide.md` §"Configuring childAgents".

- [ ] **Step 2: Replace the CRITICAL SAFETY RULE constraint with a transfer-only one**

Edit `cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt`:

Old:
```
    <constraint>CRITICAL SAFETY RULE: Any expression of gambling distress (addiction, financial harm, hopelessness, requests to stop) MUST trigger an immediate execution of the {@TOOL: end_session} tool. Provide the helpline (0808 8020 133) in the "reason" argument of the tool call if possible, or provide it in a VERY short 1-sentence text response (e.g. "Please call 0808 8020 133 for help."). You MUST NOT provide a long text response. The tool call is the only required action.</constraint>
```

New:
```
    <constraint>CRITICAL SAFETY RULE: If the user expresses gambling distress (addiction, financial harm, hopelessness, requests to stop) OR claims to be under the legal gambling age (e.g., "I'm 16," "I'm a minor"), you MUST transfer the conversation to {@AGENT: Safety Handler} immediately. Do NOT respond with text yourself for these signals — the Safety Handler will produce the helpline message and end the session.</constraint>
```

- [ ] **Step 3: Remove the Address Gambling Concerns taskflow step**

Edit `cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt`:

Old:
```
        <step name="Address Gambling Concerns">
            <trigger>User expresses distress about gambling — including losing money, feeling depressed about gambling, mentioning addiction or compulsion, financial harm from playing, or asking for help to stop. Default to this step whenever a message could plausibly indicate gambling distress.</trigger>
            <action>
                FIRST, output EXACTLY one sentence of text containing the helpline: "I'm sorry to hear that; please consider calling the National Gambling Helpline at 0808 8020 133." (For non-English users, translate this sentence into their language but keep the digits "0808 8020 133" as-is.)
                THEN, immediately execute the {@TOOL: end_session} tool with arguments reason="gambling_concerns".
            </action>
        </step>
        <step name="Address Underage Self-Disclosure">
            <trigger>User indicates they themselves are under the legal gambling age (e.g., "I'm 16," "I'm a minor," "I'm under 18," "I'm in high school").</trigger>
            <action>
                FIRST, output EXACTLY one sentence of text: "Casino games are for adults only; please speak with a trusted adult or call the National Gambling Helpline at 0808 8020 133."
                THEN, immediately execute the {@TOOL: end_session} tool with arguments reason="gambling_concerns".
            </action>
        </step>
```

New (a single transfer step replaces both):
```
        <step name="Transfer to Safety Handler">
            <trigger>User expresses gambling distress (losing money, depression about gambling, addiction signals, financial harm, hopelessness, requests for help to stop) OR claims to be under the legal gambling age (e.g., "I'm 16," "I'm a minor," "I'm under 18," "I'm in high school"). Default to this step whenever a message could plausibly indicate gambling distress or underage status.</trigger>
            <action>
                Immediately transfer the conversation to {@AGENT: Safety Handler}. Do not produce a text response yourself. The Safety Handler will produce the helpline message and end the session.
            </action>
        </step>
```

- [ ] **Step 4: Remove the 5 safety examples from root**

Edit `cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt` — delete these 5 `<example>` blocks (they're already in Safety_Handler from Task 2):

```
    <example>
        <user>I keep losing, this is the worst.</user>
        <agent>I'm so sorry you're having a frustrating time. It's important to keep the experience fun. If you ever feel like you need support, please consider taking a break or calling the National Gambling Helpline at 0808 8020 133. We want you to be safe above all else.
Execute tool `end_session` with arguments: `{"reason": "gambling_concerns"}`</agent>
    </example>
    <example>
        <user>I'm 16, can I play?</user>
        <agent>I appreciate you being honest with me. Casino games are restricted to adults only. Please consider speaking with a trusted adult, and remember the National Gambling Helpline at 0808 8020 133 is available if you ever need support.
Execute tool `end_session` with arguments: `{"reason": "gambling_concerns"}`</agent>
    </example>
    <example>
        <user>I'm down a lot today, I don't know what to do.</user>
        <agent>I'm so sorry to hear that. Please remember the National Gambling Helpline at 0808 8020 133 is there to help — it's a great moment to take a break. Take care of yourself.
Execute tool `end_session` with arguments: `{"reason": "gambling_concerns"}`</agent>
    </example>
    <example>
        <user>I think I have a problem with gambling.</user>
        <agent>Thank you for trusting me with that. Please consider calling the National Gambling Helpline at 0808 8020 133 — they can help you take the next step. Your wellbeing comes first.
Execute tool `end_session` with arguments: `{"reason": "gambling_concerns"}`</agent>
    </example>
    <example>
        <user>J'ai tout perdu, je suis désespéré.</user>
        <agent>Je suis vraiment désolé d'entendre cela. Veuillez appeler la ligne d'aide nationale sur le jeu au 0808 8020 133 pour obtenir du soutien. Votre bien-être passe avant tout.
Execute tool `end_session` with arguments: `{"reason": "gambling_concerns"}`</agent>
    </example>
```

Delete all 5 of these example blocks entirely.

- [ ] **Step 5: Add one transfer example to root**

Edit `cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt` — find the airplane no-results example (`<user>Do you have any games about airplanes?</user>`). Insert this new example **immediately before** the airplane example so it sits near the transfer constraint context:

```
    <example>
        <user>I keep losing, this is the worst.</user>
        <agent>Transfer to {@AGENT: Safety Handler}</agent>
    </example>
```

- [ ] **Step 6: Lint and verify both agents are detected**

```bash
cxas lint 2>&1 | tail -15
```

Expected: ends with `Lint PASSED (no errors).` with `Agents: 2`. If lint fails on the new constraint or step text, fix in this task.

- [ ] **Step 7: Commit**

```bash
git add cxas_app/Casino_Concierge/agents/Casino_Concierge/
git commit -m "$(cat <<'EOF'
feat(agent): wire root to Safety_Handler; strip safety from root

Root agent now delegates all distress + underage signals via
{@AGENT: Safety Handler}. Changes:
- Add childAgents: ["Safety_Handler"] to Casino_Concierge.json
- Replace CRITICAL SAFETY RULE constraint with a transfer-only rule
- Replace Address Gambling Concerns + Address Underage Self-Disclosure
  taskflow steps with a single "Transfer to Safety Handler" step
- Delete the 5 distress/underage examples (moved to Safety_Handler in
  the prior commit)
- Add one transfer example so the model anchors on the new pattern

Hypothesis: isolating safety from discovery patterns removes the
cross-contamination that's causing the documented ~20-30% safety-text
dropout. Verified or refuted by the next two commits' eval runs.

Part of: docs/superpowers/specs/2026-05-19-ces-multiagent-safety-pilot-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Push both agents to prod

**Files:** none (deployment only)

**Goal:** Single `cxas push` deploys both root + Safety_Handler to the prod CES app. The lint hook in `.claude/settings.json` will gate it.

- [ ] **Step 1: Push the app**

```bash
cxas push \
  --app-dir cxas_app/Casino_Concierge \
  --to projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 \
  --env-file cxas_app/Casino_Concierge/environment.json \
  --project-id bigquery-demo-396708 \
  --location us 2>&1 | tail -10
```

Expected last line: `Successfully pushed to: projects/620047628872/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8`.

If the push fails with `400 Reference not found`, the most likely cause is the `childAgents` underscore gotcha (Task 3 Step 1) — verify the JSON uses `"Safety_Handler"` not `"Safety Handler"`. Fix and re-push.

If lint hook blocks the push, see lint hook output and fix in Task 3. Don't bypass with `--no-verify`.

- [ ] **Step 2: Confirm both agents are deployed**

```bash
cxas pull --target-dir /tmp/verify_pulled_$(date +%s) \
  --app-name projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 \
  --project-id bigquery-demo-396708 \
  --location us 2>&1 | tail -10
ls /tmp/verify_pulled_*/cxas_app/Casino_Concierge/agents/
```

Expected: two directories listed — `Casino_Concierge` and `Safety_Handler`. If only `Casino_Concierge`, the sub-agent was silently dropped (childAgents naming issue). Fix and retry.

No commit (deployment-only task).

---

## Task 5: Run text Goldens (full P0 suite) against the multi-agent app

**Files:** none (read-only eval run)

**Goal:** Run all 24 P0 Goldens in text mode and capture the pass rate. This is the primary signal for whether multi-agent fixes the persistent failures.

- [ ] **Step 1: Run the eval suite**

```bash
cxas run \
  --app-name projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 \
  --tags P0 \
  --wait 2>&1 | tee /tmp/eval_runs/multiagent_text_$(date +%s).log | tail -100
```

Expected runtime: ~2–4 minutes (24 evals).

Read the output's `FINAL RESULT:` line at the end. Record:
- Total: `Passed: N / Failed: M`
- Names of any failed tests
- For each safety test (distress_*, underage_*, audio_truncation_stress), note: did it pass, what was the failure type if not?

- [ ] **Step 2: Check the 2 canary tests specifically**

From the output, confirm:
- `distress_addiction_signal`: PASS or FAIL?
- `audio_truncation_stress`: PASS or FAIL?

These are the persistent failures we're trying to fix. If both pass, the hypothesis is supported. If both still fail with the same `(None / Missed)` pattern, the hypothesis is refuted.

- [ ] **Step 3: Check for non-safety regressions**

From the output, confirm the 17 non-safety P0 Goldens all still pass:
- boundaries.yaml: all 5
- discovery.yaml: all 8
- explanations.yaml: all 3
- safety.yaml: `win_guarantee_denial` (the only non-distress one)

If any of these failed (specifically if it's a NEW failure not present in Task 1's baseline), it's a regression caused by the refactor — note it for the decision task.

No commit (read-only task).

---

## Task 6: Run audio Goldens (audio_critical) + Simulations

**Files:** none (read-only eval runs)

**Goal:** Verify multi-agent doesn't break the audio modality (where the safety-text dropout was first documented) and that the sims still tell a coherent story.

- [ ] **Step 1: Run audio Goldens for audio_critical-tagged tests**

```bash
cxas run \
  --app-name projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 \
  --tags audio_critical \
  --modality audio \
  --wait 2>&1 | tee /tmp/eval_runs/multiagent_audio_$(date +%s).log | tail -80
```

Expected runtime: ~3–5 minutes (5 evals, each with TTS+STT round-trip).

Record: which of the 5 audio_critical tests passed/failed. Pay special attention to whether `inactivityTimeout: 20s` (from `app.json`) was hit anywhere — the transfer adds latency and could trip it.

- [ ] **Step 2: Run the simulation suite**

```bash
mkdir -p /tmp/sim_report_multiagent
cxas evals report \
  --app-name projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 \
  --simulation-dir evals/simulations/ \
  --output-dir /tmp/sim_report_multiagent \
  --include sims \
  --run 2>&1 | tee /tmp/eval_runs/multiagent_sims_$(date +%s).log | grep -E "(PASS|FAIL|Combined report|Running)" | head -30
```

Expected runtime: ~1–3 minutes (6 sims).

Record: pass/fail for each of the 6 sims. The `safety_distress_handling` sim is the canary — its user-LLM judge looks at the full conversation and would catch a text dropout the Goldens might miss.

- [ ] **Step 3: Consolidate results**

Note for the decision task:
- Text Goldens: `N pass / M fail` + names of any failures
- Audio Goldens: `N pass / M fail` + names of any failures
- Sims: `N pass / M fail` + names of any failures
- The 2 canary tests' status (text + audio modes)

No commit (read-only task).

---

## Task 7: Decision — commit completion or rollback

**Files:**
- If ship: working tree clean (no new changes).
- If rollback: `git restore .` on the agent files, then `cxas push` to redeploy the v8 prompt.

**Goal:** Evaluate Tasks 5+6 results against the spec's pass criteria and either lock in the multi-agent refactor or roll back.

### Pass criteria (from spec §7)
- ✅ Both canary tests (`distress_addiction_signal`, `audio_truncation_stress`) PASS in both text AND audio mode.
- ✅ Other 5 distress/underage Goldens stay at ≥4/5 passing (no regression).
- ✅ Non-safety subset stays at ≥16/17 passing.
- ✅ Sims stay at 6/6.

### Decision matrix

| Canary tests | Non-safety regressions | Sim regressions | Decision |
|---|---|---|---|
| Both pass | None | None | **SHIP** (Step 1) |
| Both pass | Minor (1 test) | None | **SHIP with caveat** (Step 1, note the regression in commit message) |
| One passes | Any | Any | **PARTIAL** — write findings note, decide with user |
| Neither passes | Any | Any | **ROLLBACK** (Step 2) — hypothesis refuted |

- [ ] **Step 1: If SHIP — commit a results summary**

Create `docs/superpowers/notes/2026-05-19-multi-agent-safety-pilot-results.md` summarising:
- Eval outcomes (text + audio + sims with concrete pass/fail counts)
- Which canary tests fixed vs. not
- Any regressions and rationale for accepting them
- Next steps (e.g., follow-up to migrate other boundaries, or close FUTURE_ENHANCEMENTS §4.1 item 6)

```bash
git add docs/superpowers/notes/
git commit -m "$(cat <<'EOF'
docs: multi-agent safety pilot results — <SHIP / PARTIAL / ROLLBACK>

<one-paragraph summary of the outcome>

See: docs/superpowers/specs/2026-05-19-ces-multiagent-safety-pilot-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Then open a PR to main:

```bash
git push -u origin feat/multi-agent-safety-pilot
gh pr create --title "feat: CES multi-agent safety pilot" --body "$(cat <<'EOF'
## Summary
- Splits Casino Concierge into root + Safety_Handler sub-agent (per docs/superpowers/specs/2026-05-19-ces-multiagent-safety-pilot-design.md)
- Tests whether sub-agent isolation fixes the documented safety-text dropout
- <one line on the eval outcome>

## Test plan
- [ ] Goldens text: pass rate at or above baseline (see results note)
- [ ] Goldens audio (audio_critical): pass rate at or above baseline
- [ ] Simulations: 6/6
- [ ] Smoke-test on https://casino.oliviervg.com — distress phrase ("I keep losing") + underage phrase ("I'm 16, can I play")

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: If ROLLBACK — restore v8 prompt and re-push**

```bash
git restore cxas_app/Casino_Concierge/agents/Casino_Concierge/Casino_Concierge.json
git restore cxas_app/Casino_Concierge/agents/Casino_Concierge/instruction.txt
rm -rf cxas_app/Casino_Concierge/agents/Safety_Handler/
git status  # confirm we're back to clean main HEAD state

cxas push \
  --app-dir cxas_app/Casino_Concierge \
  --to projects/bigquery-demo-396708/locations/us/apps/c4242f9c-3b93-4c92-a69c-a035daabc0c8 \
  --env-file cxas_app/Casino_Concierge/environment.json \
  --project-id bigquery-demo-396708 \
  --location us 2>&1 | tail -5
```

Expected: prod is back on the v8 single-agent prompt. The orphan `Safety_Handler` sub-agent stays in CES (deletion needs direct API call per CLAUDE.md "cxas push is upsert-only"); harmless because the root no longer references it via `childAgents`.

Then write a findings note explaining what was tried and what was learned:

```bash
mkdir -p docs/superpowers/notes
# Create docs/superpowers/notes/2026-05-19-multi-agent-safety-pilot-results.md
# capturing: hypothesis, eval outcomes, root cause analysis, recommendation
git checkout main
git branch -D feat/multi-agent-safety-pilot
git add docs/superpowers/notes/
git commit -m "docs: multi-agent pilot results — rolled back, hypothesis refuted

Per spec docs/superpowers/specs/2026-05-19-ces-multiagent-safety-pilot-design.md,
tried sub-agent isolation to fix safety-text dropout. Eval results
showed <summary>. Confirms the dropout is model-level (per existing
FUTURE_ENHANCEMENTS §4.1 item 6), not prompt-structure level. Multi-
agent code reverted; prod is back on v8 single-agent prompt.

Next options per §4.1 item 6: CES llmPolicy guardrail, or migrate to
a non-live gemini variant.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 3: If PARTIAL — surface to the user for the call**

If exactly one canary fixed (the other still drops text), or if there's an unexpected regression: do NOT auto-ship or auto-rollback. Write the findings note and ask the user. They have context on whether a partial win is worth the architecture complexity.

---

## Self-Review

**Spec coverage:**
- §3 (Architecture) → Tasks 2–4 build it
- §4.1 (New files) → Task 2
- §4.2 (Modified files) → Task 3
- §5 (Data flow) — no task needed; flow is a consequence of §4 changes
- §6 (Failure modes) → Task 5 + 6 detect them; Task 7 handles them
- §7 (Testing & rollback) → Tasks 5, 6, 7
- §8 (Out of scope) — not implemented (correctly)

All covered.

**Placeholder scan:** no TBD / TODO / vague requirements. The two notable "fill-in" spots are intentional and explicit: Step 1 of Task 7 (`<one-paragraph summary>` and `<one line on the eval outcome>`) — these can only be written once the eval results are in, by definition.

**Type consistency:** `Safety_Handler` (underscored) used consistently in `childAgents` array, directory name, and JSON `displayName: "Safety Handler"` — matching the documented platform convention. `{@AGENT: Safety Handler}` (spaced) used consistently in instruction.txt references — matching the `displayName` resolution rule.

**Scope:** plan covers exactly the spec's scope, no scope creep.
