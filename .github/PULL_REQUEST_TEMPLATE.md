## What & why

<!-- One paragraph: the change and the reason. Link issues/epics (MASTER-PROMPT §3). -->

## Checklist (enterprise standards — docs/MASTER-PROMPT.md §2.3)

- [ ] Tenant scoping + RBAC on every new query/route
- [ ] Explainability shipped with any new computed output
- [ ] Tests moved with the code (unit / integration / cross-instance / E2E as applicable)
- [ ] No secrets, state, or tfvars in the diff
- [ ] Conventional commits, one logical change each
- [ ] Docs synced in this PR (`AI-HANDOFF.md`, guides, `deploy-prep/tasks.md` session record)
- [ ] Migration included + defensive if the schema changed

## Rollout notes

<!-- Migration to run? Terraform apply needed? Feature visible to users? -->
