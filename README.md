# Session Handoffs

Four skills that move a task into a fresh Codex or Claude Code terminal session with a self-contained prompt and duplicate-launch protection.

| Skill | Send from | Continue in |
|---|---|---|
| `codex-to-codex` | Codex | Codex |
| `codex-to-claude` | Codex | Claude Code |
| `claude-to-claude` | Claude Code | Claude Code |
| `claude-to-codex` | Claude Code | Codex |

Use a handoff when you explicitly want a fresh conversation, including a change of assistant. Ordinary in-conversation delegation stays in the current conversation. Installation does not launch any client or change your existing skills.

## Install in Claude Code

```text
/plugin marketplace add kyisaiah47/session-handoffs
/plugin install session-handoffs@session-handoffs-marketplace
```

Start a new session, then explicitly invoke `/session-handoffs:claude-to-codex` or `/session-handoffs:claude-to-claude` and name the task. Example:

```text
/session-handoffs:claude-to-codex Finish the pagination change in the current worktree. Include the tests already run and preserve the unrelated settings edit.
```

For a temporary installation without registering a marketplace, clone the repository and start `claude --plugin-dir /absolute/path/to/session-handoffs`. Plugin installation provides all four skills. Each skill folder also contains its own launcher, reference, and license for standalone installation.

## Install in Codex

The full repository can be installed through a supported plugin marketplace. Add this GitHub marketplace source:

```text
codex plugin marketplace add kyisaiah47/session-handoffs
```

Install Session Handoffs through your client's plugin browser. Plugin install UI and availability vary by Codex surface; this package needs a local executor, filesystem access, and permission to open a terminal.

Restart Codex after installation, then invoke `$codex-to-claude` or `$codex-to-codex` explicitly. Example:

```text
Use $codex-to-claude to continue the current bug fix in Claude Code. Include the failing reproduction, completed edits, and the remaining acceptance checks.
```

## Install individual skills with the skills CLI

The [skills CLI](https://github.com/vercel-labs/skills/blob/main/docs/commands.md) can install selected folders from this repository. It requires Node.js 22.20 or later. These commands install to the current project; add `-g` for a global installation:

```sh
# The two skills sent from Codex
npx skills add kyisaiah47/session-handoffs --skill codex-to-codex --skill codex-to-claude -a codex

# The two skills sent from Claude Code
npx skills add kyisaiah47/session-handoffs --skill claude-to-claude --skill claude-to-codex -a claude-code
```

To install all four for both hosts instead:

```sh
npx skills add kyisaiah47/session-handoffs --skill '*' -a codex -a claude-code
```

Choose the desired installation method when prompted. Both copy and symlink installations work: **each `skills/<name>/` folder is self-contained**, including `SKILL.md`, `scripts/handoff.py`, `references/workflow.md`, the license, and Codex metadata. Do not install only the `SKILL.md` file. Standalone Claude skills use `/claude-to-codex` and `/claude-to-claude`; the `/session-handoffs:` prefix applies to plugin installations.

For a manual install, copy one complete `skills/<name>/` folder into the selected agent's skills directory, preserving its contents. Avoid overwriting an existing skill without reviewing it. No original repository checkout or sibling skill is required after copying.

Both hosts can discover the four packaged skills. Use the two matching the current assistant as sender; the direction names prevent collisions between same-assistant and cross-assistant handoffs.

## What gets transferred

The sender writes the objective, absolute paths, completed work, constraints, next action, and verification criteria into a prompt file. A small Python launcher opens a fresh interactive client and prepends a receiver marker to prevent accidental handoff loops.

The sender's conversation, credentials, model settings, project trust, and permissions are not cloned. Existing CLI configuration remains in effect. Authentication, trust dialogs, and platform restrictions can still require user interaction.

The launcher records what happened without treating “terminal requested” or “client exited” as proof of model acceptance or task completion. Reusing an operation ID never opens another terminal. Read [the workflow and receipt states](references/workflow.md) for configuration, recovery, and privacy details.

## Requirements and supported environments

- Python 3.9 or newer, plus the destination CLI already installed and authenticated.
- macOS with Terminal.app, or Linux with one of the supported terminal emulators. Another terminal can be supplied as an argument array. Windows has no built-in adapter in this release.
- A local interactive desktop. Web-only environments and headless hosts cannot open a visible terminal.
- Host permission to run local scripts and open a terminal. No permission/trust bypass flags are added.

The launcher accepts a configurable executable/argument prefix, uses subprocess argument arrays, and keeps prompt text out of generated shell code. Prompts still become a CLI argument, so keep secrets out; operating-system process inspection and the destination CLI's normal history can expose task text.

## Validation

```sh
python3 scripts/sync_skills.py --check
python3 -m unittest discover -s tests -v
claude plugin validate --strict .
```

Tests use stub clients and a stub terminal. They verify all four directions, exact prompt argument preservation, chosen working directory, receiver-loop refusal, failures, status redaction, and duplicate protection. They also copy each of the four skill folders into an isolated location and run its bundled launcher without accessing repository assets, then check deterministic synchronization and drift detection. They do not launch real assistant sessions or assert that an authenticated model completes a task. Terminal.app and Linux desktop integration require a user-authorized live smoke test in the target environment.

## Maintaining the shared implementation

Edit the canonical `scripts/handoff.py`, `references/workflow.md`, or root `LICENSE`, then run:

```sh
python3 scripts/sync_skills.py
python3 scripts/sync_skills.py --check
```

The first command copies those exact bytes into each distributable skill folder; the second fails on missing, changed, or symlinked bundled assets without modifying them. Commit the generated copies with the canonical changes. All copies are ordinary files, so archive and directory-based installers preserve functionality. Do not hand-edit the generated copies under `skills/*/scripts/`, `skills/*/references/`, or `skills/*/LICENSE`.

## Compatibility sources

- [Codex CLI reference](https://developers.openai.com/codex/cli/reference/)
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Claude plugin distribution](https://code.claude.com/docs/en/plugins/publish)
- [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins)

The launcher uses the documented interactive `codex [PROMPT]` and `claude [prompt]` forms. It does not depend on account-pool launchers or private local services.

Copyright 2026 Compound Labs. All rights reserved. See [LICENSE](LICENSE) for permission to install, use, and locally adapt this package.

## Privacy and terms

Read the [data-handling policy](PRIVACY.md) and [usage terms](LICENSE) before use.
