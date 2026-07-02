# Deploy-Prep Session — Requirements Document

> **Session:** 2026-07-01 · **Branch:** `ekam-testing` · **Author:** AI agent (Claude Code)
> Companion docs: [`design.md`](design.md) · [`tasks.md`](tasks.md)

---

## 1. Provenance

This document is a refined, structured restatement of the user's 2026-07-01 prompt. Every
requirement below traces to (a) a sentence in that prompt, (b) a standing instruction recorded in
[`AI-HANDOFF.md`](../AI-HANDOFF.md) § *User standing instructions*, or (c) the project's own
*Remaining work* table in the same file. Nothing here is invented beyond those three sources;
where the prompt is ambiguous, the ambiguity is listed in §6 (Open questions) instead of being
resolved silently.

### 1.1 Original prompt (verbatim)

> read and understand at all the files in this folder and finish the remaining tasks left in this
> entire project and prepare it for deploymentL report back to me with the things I asked for and
> tell me anything you are confused about do no extrapolate anything and keep in mind everything I
> told you in past prompts which says anything about what to remember in future prompts, and make
> sure to keep me informed with any confusion and ask me about that, if there are any gaps in the
> information I have provided or if I have overlooked anything also inform me on that and make
> sure all work is being done in the ekam-testing branch and not the main branch at all times, If
> f you get stuck at any point, skip that item, mark it as high priorty, contninue with all the
> remaining tasks and report it back to me once you are fully complete, and before you begin
> actualy completing the work give me a rough estimate of how long it will take you to do all of
> these things then begin the work
>
> Very first thing you need to do is use prompt engineering and create a rewurements document
> based upon this prompt and refine this prompt significantly to make it very detailed and clear
> without extrapolating or hallucinating, then create a design document for these tasks and then
> create a task list which is used to complete the prompt

### 1.2 Refined prompt (structured restatement)

1. Read and understand every file in `/Users/ekambindra/Projects/aurora`.
2. Produce, in order: this requirements document, a design document, and a task list — before
   executing any project work.
3. State a rough time estimate for the whole effort before beginning execution.
4. Finish the remaining tasks of the AURORA project and prepare the project for deployment.
5. Perform **all** work on the `ekam-testing` branch; never commit to `main`.
6. Honor every standing instruction from past prompts (recorded in `AI-HANDOFF.md`).
7. If blocked on any item: skip it, mark it **high priority**, continue with the rest.
8. At the end, report: what was done, every point of confusion (as questions), and any gaps or
   overlooked items in the user's instructions.
9. Do not extrapolate or hallucinate at any step.

---

## 2. Definition: "the remaining tasks left in this entire project"

The prompt does not enumerate tasks, so the definition is taken from the repository's own
source-of-truth documents (per standing instruction *"Docs-first — follow `docs/`"*), plus
anything discovered broken during verification (per standing instruction *"Enterprise quality —
CI green"*).

| # | Source | Item | Classification |
|---|--------|------|----------------|
| R-1 | `AI-HANDOFF.md` Remaining work — **P0** | First AWS production deploy | Partially executable: local preparation only (see C-1, C-2) |
| R-2 | `AI-HANDOFF.md` Remaining work — Optional | Dependabot PRs #12–#14: `next@16.2.9`, `tailwindcss@4.3.1`, `typescript@6.0.3` — "review/test before merge" | Executable on `ekam-testing` (see Q-3) |
| R-3 | `AI-HANDOFF.md` Remaining work — Optional | Branch cleanup: delete stale `feat/*` branches | Local part executable; remote part needs approval (Q-5) |
| R-4 | `AI-HANDOFF.md` Remaining work — Future | Real AI provider (needs OpenAI/Anthropic keys) | Blocked — no keys provided (Q-7) |
| R-5 | `AI-HANDOFF.md` Remaining work — Future | Neo4j/Redis persistent job queues | Not executed — architecture change requiring user approval (Q-6) |
| R-6 | `AI-HANDOFF.md` Remaining work — Future | Board report persistence (`BoardReport` table wired for prod) | Not executed — marked Future; needs user decision (Q-6) |
| R-7 | Discovered 2026-07-01 | `packages/database` seed tests fail (Anomaly B masked by calendar rollover; Anomaly A latent November failure) — CI on `main` is red today | Executable — must fix (CI green standard) |
| R-8 | Discovered 2026-07-01 | Stale docs: `README.md` says Phase 4 "In progress" and quickstart "Not yet runnable"; both contradict merged reality | Executable — docs-sync quality standard |

## 3. Functional requirements

| ID | Requirement | Trace |
|----|-------------|-------|
| FR-1 | Read/understand all project files (code, docs, infra, CI) before changing anything | Prompt §1.2-1 |
| FR-2 | Author requirements → design → task-list docs, in that order, before execution | Prompt §1.2-2 |
| FR-3 | State a rough time estimate before execution | Prompt §1.2-3; standing instruction #4 |
| FR-4 | Fix the failing seed tests so the full Python suite (116 tests) is green | R-7 |
| FR-5 | Review/test the three Dependabot dependency bumps with build + E2E gates | R-2 |
| FR-6 | Run every deploy-preparation step executable on this machine: preflight script, Terraform fmt/validate, web production build, Playwright E2E, load-test smoke | R-1 |
| FR-7 | Sync stale status docs; update `AI-HANDOFF.md` + `PROJECT-MASTER-GUIDE.md` at session end | R-8; standing instruction #3 |
| FR-8 | Clean up local branches verified merged into `main`; do not delete remote branches without approval | R-3 |
| FR-9 | Produce a final report: estimate recap, per-task outcomes, skipped/high-priority items, confusions as questions, gaps/overlooked items | Prompt §1.2-8 |

## 4. Non-functional requirements

| ID | Requirement | Trace |
|----|-------------|-------|
| NFR-1 | All work on `ekam-testing`; `main` untouched | Prompt §1.2-5 |
| NFR-2 | Enterprise quality: tests green, no secrets committed, tenant isolation preserved | Standing instruction #1 |
| NFR-3 | Conventional commits (`feat:`, `fix:`, `docs:`) | `PROJECT-MASTER-GUIDE.md` §8 |
| NFR-4 | No extrapolation: scope limited to §2 table; anything else becomes a question | Prompt §1.2-9 |
| NFR-5 | Skip-and-flag protocol for blockers; never abandon the run | Prompt §1.2-7 |

## 5. Constraints (environment, discovered 2026-07-01)

| ID | Constraint | Consequence |
|----|-----------|-------------|
| C-1 | `aws`, `docker`, `gh`, `k6` CLIs **not installed**; no AWS credentials configured | Actual AWS deploy (terraform apply, ECR push, ECS deploy), Docker image builds, and GitHub PR merges are impossible from this machine |
| C-2 | AWS deploy creates billable infrastructure | Even with tooling, `terraform apply` requires explicit user go-ahead |
| C-3 | Terraform available only via repo-local `.tools/terraform` binary | fmt/validate work; state operations still need AWS credentials |
| C-4 | Python 3.9.6 venv at `apps/api/.venv` (project supports 3.9) | Keep `Optional[]` syntax; no `X \| Y` unions |
| C-5 | Session is non-interactive | Questions are collected in the final report rather than asked mid-run |

## 6. Open questions for the user (also in final report)

- **Q-1** Is the `AI-HANDOFF.md` *Remaining work* table the correct definition of "remaining
  tasks"? (Assumed yes — docs-first standing instruction.)
- **Q-2** The actual AWS deploy is blocked by C-1/C-2. Should the machine be provisioned
  (aws CLI, Docker, credentials) so a future session can execute `DEPLOY-CHECKLIST.md`?
- **Q-3** Dependabot PRs #12–#14 target `main` on GitHub and can't be merged by this session
  (no `gh`, and the no-main rule). The same bumps were applied and tested on `ekam-testing`
  instead. Merge preference: dependabot PRs, or this branch?
- **Q-4** Standing instruction #7 says "no commits unless asked", but work cannot "be in the
  ekam-testing branch" without commits. Commits were made on `ekam-testing` only, and pushed to
  `origin/ekam-testing` per standing instruction #2 (keep GitHub in sync). Confirm this reading.
- **Q-5** Stale `feat/*` branches: local merged branches deleted; remote deletion awaits approval.
- **Q-6** "Future" items (R-5 persistent queues, R-6 board-report persistence): execute now or
  keep deferred? Note: Terraform sets `desired_count = 2` for the API service, and board
  reports / simulations / ingestion jobs live in per-process memory — behind a 2-task load
  balancer these features will misbehave in production (see design.md §5). A decision is needed
  before the first real deploy: persist these stores, or set `api_desired_count = 1` initially.
- **Q-7** Real AI provider (R-4) needs an API key + provider choice (`openai` / `bedrock`
  scaffolding exists in config; only `mock` is implemented). Provide when ready.

## 7. Acceptance criteria for this session

1. Requirements/design/tasks docs exist under `docs/deploy-prep/` (this folder).
2. Full Python suite green (116 tests, all 6 packages) with failures un-masked.
3. Web production build green; Playwright E2E suite green.
4. Deploy preflight run; every FAIL explained as machine-tooling gap or fixed.
5. Dependency bumps either merged-on-branch and green, or reverted and flagged high-priority.
6. `main` has zero new commits; all work on `ekam-testing`, pushed.
7. Final report delivered with estimate recap, outcomes, questions, gaps.
