# Human Review Guide

You control this project with short comments — from your phone, a GitHub issue,
a PR comment, or Claude Code chat. Agents are instructed to recognize these
phrases and act within the specification-first workflow. You never need to open
or edit files yourself.

## Quick commands (say these in plain language)

| You say | The agent does |
| ------- | -------------- |
| **Approve spec** | Sets the spec status to `Approved`, records your approval, moves it to `docs/specs/approved/`. |
| **Reject spec** | Sets status to `Rejected`, records the reason, moves it to `docs/specs/archived/`. |
| **Revise REQ-001** | Reopens the spec, changes only that requirement, keeps status pre-approval (or adds an amendment if already Approved). |
| **Implement approved spec** | Starts implementation of the named approved spec — only its scope. |
| **Stop and summarize** | Halts current work and returns a short phone-friendly status. |
| **Re-run checks** | Re-runs governance scripts and tests, reports results. |
| **Explain failing CI** | Investigates the failing check and explains it plainly. |
| **Reduce scope** | Narrows the change to a smaller, safer subset and updates the spec/PR. |
| **Split this PR** | Proposes how to divide the change into smaller PRs. |
| **Prepare handoff** | Runs `/handoff` and returns a clear next-agent state. |

## What to look at when reviewing a spec

- Are the **non-goals** right? (Prevents scope creep.)
- Does every requirement have **acceptance criteria** you'd accept?
- Is anything **missing** or **ambiguous**? Say "Revise REQ-00X".
- Are the **open questions** answered?

You do not need to check formatting or IDs — the governance scripts do that.

## What to look at when reviewing a PR

- Does it link an **approved spec** and list **requirement IDs**?
- Is the **verification evidence** convincing?
- Are there **unrelated file changes**? If so, say "Reduce scope".
- Read the **phone-friendly summary** at the top — it should be enough to
  decide.

## If something looks wrong

Say **"Stop and summarize"**. The agent will halt and report, rather than
guessing. When an agent hits a conflict, it is required to stop and ask you —
answer with a short decision and it will proceed.
