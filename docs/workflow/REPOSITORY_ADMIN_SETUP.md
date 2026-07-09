# Repository Admin Setup (Manual Actions)

Some protections require GitHub admin actions that an agent cannot perform (or
cannot verify) from inside a session. **None of the settings below are
configured by this bootstrap.** They are a checklist for you, the repository
owner, to apply manually in GitHub settings.

> An agent must never claim these are configured unless it actually configured
> and verified them.

## Branch protection (recommended)

In **Settings → Branches → Add branch ruleset / protection rule** for `main`:

- [ ] **Protect `main`** — require pull requests before merging.
- [ ] **Require a PR before merge** — no direct commits to `main`.
- [ ] **Require status checks to pass** — select the `governance` workflow
      checks once they have run at least once and appear in the list.
- [ ] **Block direct pushes to `main`** — if practical for a solo project
      (you can allow yourself to bypass, but keeping it on builds the habit).

## Security features (recommended)

In **Settings → Code security and analysis**:

- [ ] **Dependabot alerts** — enable once dependencies exist.
- [ ] **Secret scanning** — enable if available for the repository.
- [ ] **Push protection** for secrets — enable if available.

## Secrets

In **Settings → Secrets and variables → Actions**:

- [ ] Configure repository secrets only if/when a workflow needs them. None are
      required by the governance workflow.

## Integrations

- [ ] Install or configure Claude-related GitHub integrations only if you decide
      to later. Not required by this bootstrap.

## Status

At bootstrap time: **nothing in this list has been applied.** These are your
next manual steps if you want them.
