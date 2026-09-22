# Noye agent guide

Read `NOYE_DEVELOPMENT_PLAN.md` before changing the project. Its operating
rules, roadmap, and Git workflow govern this repository unless the user's
latest explicit instruction says otherwise. Inspect the current branch and
working tree before editing; the plan may lag behind the implementation.

## Commit history

Make focused Conventional Commits for meaningful units of work, such as a
service change, its API surface, a UI change, or documentation. Keep each
commit reviewable and validate the relevant behavior. Do not turn a branch
into one large commit merely because its PR will be reviewed as one feature.
Follow the plan's rule requiring explicit approval before rewriting a
published branch or force-pushing.

## Pull request writing

Use the Phase 2 library PR as the writing model and the detailed rules in
`NOYE_DEVELOPMENT_PLAN.md` under **PR title style** and **PR description
style**. Write in English. Use a lowercase Conventional Commit title in the
imperative, under 70 characters, with no trailing period.

Use these sections in order, omitting one only when it genuinely does not
apply:

``` text
## Summary
## Changes
## Validated
## Not validated
## Notes
## Review
## Roadmap
```

Explain the purpose and context in Summary. In Changes, name the important
files or groups and state their contribution. In Validated, report commands,
results, measured numbers, and direct browser observations precisely. In Not
validated, record blocked checks and remaining uncertainty. Use Notes for
non-obvious decisions and their tradeoffs. If separate review passes ran,
use Review for their findings, resulting changes, and suggestions declined
with reasons; do not invent a review. End with the relevant roadmap phase and
what this PR unblocks. Keep the detail proportional to the change and do not
claim validation that did not happen.

The `frontend/AGENTS.md` file contains generated Next.js version guidance for
that directory. Follow it for frontend work as well.
