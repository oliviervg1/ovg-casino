# cxas-scrapi Retrofit Design

**Date:** 2026-05-15
**Status:** Approved by user during brainstorming session; ready for implementation planning.
**Scope:** Completion of the OVG Casino Concierge CES app retrofit. Remaining item is Phase D: GitHub Actions CI with branch-per-feature lifecycle and AppVersion pinning.

---

## 1. Goal

Implement a branch-per-feature CI loop with version-pinned production and one-command rollback.

This retrofit fulfills FUTURE_ENHANCEMENTS item §4.4 (AppVersion pinning + rollback).

## 2. Deploy lifecycle

```
feature branch  ──cxas branch──▶  ephemeral CES app "Casino Concierge - PR #<n>"
     │                                        │
     │                                        ▼
   PR open ──▶ GH Actions: lint + ci-test (Goldens, jailbreak, sims, audio) ──▶ block on fail
     │                                        │
     │                                        ▼
   PR merge ──▶ cxas push to prod draft ──▶ snapshot to AppVersion ──▶ flip Deployment
     │
   PR close ──▶ cxas delete on the ephemeral app
```

Rollback: `gh workflow run rollback.yaml --field version=<n>`. Single command; flips the prod `Deployment` to a prior `AppVersion`. AppVersions are immutable snapshots, so rollback is deterministic.

## 3. Remaining Phase: Phase D — CI/CD with branch lifecycle + AppVersion pinning

Outcome: PRs get an automatically-provisioned ephemeral CES app to test against, all four eval suites run on every PR, merges to `main` snapshot a new `AppVersion` and flip the prod `Deployment` to it, and stale branch apps clean themselves up.

### 3.1 Workflow files

```
.github/workflows/
├── pr-open.yaml      # cxas branch → push branch state → lint + ci-test
├── pr-sync.yaml      # on each push to a PR branch: re-push + re-run evals
├── pr-close.yaml     # cxas delete on the branch app
├── main-deploy.yaml  # on merge to main: push to prod draft → AppVersion → flip Deployment
└── rollback.yaml     # workflow_dispatch with version input → flip Deployment back
```

### 3.2 Branch app naming

`Casino Concierge - PR #<number>`. The PR number, not the branch name — PR numbers are stable identifiers, branch names can be renamed mid-PR; PR number is also what `pr-close.yaml` keys on.

### 3.3 pr-open.yaml outline

1. `gcloud` ADC via Workload Identity Federation (no long-lived service account keys).
2. `cxas branch` from prod app → new app `Casino Concierge - PR #${{ github.event.number }}`. Branch app's `search_available_games` keeps pointing at the prod datastore.
3. `cxas push` the PR's `cxas_app/Casino Concierge/` over the branch app (replacing the cloned config with the PR's proposed config).
4. `cxas lint --json` → fail-closed.
5. `cxas run` for each suite. Audio suite runs in parallel job for wall-clock reasons.
6. Post a sticky PR comment: app resource ID, eval results table, links to traces. Sticky comment is updated on each `pr-sync.yaml` run rather than spammed.

### 3.4 main-deploy.yaml outline

1. `cxas push` to prod draft.
2. Re-run lint + a fast eval subset (Goldens + Jailbreak only, not full sims/audio — those gated the PR; this is final-mile sanity).
3. Create an immutable `AppVersion` snapshot of the draft. CES has native `AppVersion` and `Deployment` resources. Use `cxas` subcommands for AppVersion CRUD if they exist; otherwise call CES directly via the cxas Python library or `gcloud` / `curl`. Naming: `v$(date +%Y%m%d)-${SHORT_SHA}`.
4. Update the prod `Deployment` to point at the new `AppVersion`.
5. Tag the git commit `prod-v${SHA}` for traceability between the version and the source.

### 3.5 rollback.yaml outline

`workflow_dispatch` with `version` input. Flips the prod `Deployment` to the named `AppVersion`. No code change; no PR. Pre-flight check: confirm the requested version exists. Post-flight: tag `prod-rollback-${VERSION}-${TIMESTAMP}`.

### 3.6 pr-close.yaml outline

Triggered on `pull_request` `closed` (whether merged or not). `cxas delete` the branch app. Uses the same PR-number naming convention. Idempotent.

### 3.7 Auth model

GitHub Workload Identity Federation → GCP service account with these IAM bindings (least privilege):

- `roles/dialogflow.client` (or its CES equivalent) for app/agent CRUD.
- `roles/discoveryengine.editor` is **not** granted — branch apps share the prod datastore read-only and don't need to mutate it.
- `roles/iam.workloadIdentityUser` on the SA for the GH OIDC subject.

### 3.8 Cost & quota notes

- Each open PR creates a CES app. Add a sanity-check step in `pr-open.yaml` that lists current `Casino Concierge - PR #*` apps and warns if >20 exist.
- Audio evals are slow. Budget ~5-10 min wall clock per PR for the full eval matrix.

## 4. Acceptance criteria

Phase D is complete when:

1. A PR opened on a feature branch automatically creates an ephemeral CES app, runs lint + all eval suites, posts results as a sticky comment, and blocks merge on failure.
2. A merge to `main` automatically creates a new `AppVersion`, flips the prod `Deployment` to it, and tags the git commit.
3. A PR close automatically deletes the corresponding ephemeral CES app.
4. `gh workflow run rollback.yaml --field version=<n>` flips the prod `Deployment` to the named version in <60s.
