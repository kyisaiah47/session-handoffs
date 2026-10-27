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

For a temporary installation without registering a marketplace, clone the repository and start `claude --plugin-dir /absolute/path/to/session-handoffs`. The full bundle is required; copying one `SKILL.md` omits the shared launcher.

## Install in Codex

The full repository can be installed through a supported plugin marketplace. Add this GitHub marketplace source:

```text
codex plugin marketplace add kyisaiah47/session-handoffs
```

Install Session Handoffs through your client's plugin browser. Plugin install UI and availability vary by Codex surface; this package needs a local executor, filesystem access, and permission to open a terminal.

For CLI skill-directory installation, clone this repository to a stable location and link the two Codex-origin folders into your skills directory:

```sh
git clone https://github.com/kyisaiah47/session-handoffs.git
mkdir -p "$HOME/.agents/skills"
ln -s "$(pwd)/session-handoffs/skills/codex-to-codex" "$HOME/.agents/skills/codex-to-codex"
ln -s "$(pwd)/session-handoffs/skills/codex-to-claude" "$HOME/.agents/skills/codex-to-claude"
```

Do not overwrite an existing folder or link. Keep the checkout in place so the shared scripts and references remain available. Restart Codex, then invoke `$codex-to-claude` or `$codex-to-codex` explicitly. Example:

```text
Use $codex-to-claude to continue the current bug fix in Claude Code. Include the failing reproduction, completed edits, and the remaining acceptance checks.
```

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
python3 -m unittest discover -s tests -v
claude plugin validate --strict .
```

Tests use stub clients and a stub terminal. They verify all four directions, exact prompt argument preservation, chosen working directory, receiver-loop refusal, failures, status redaction, and duplicate protection. They do not launch real assistant sessions or assert that an authenticated model completes a task. Terminal.app and Linux desktop integration require a user-authorized live smoke test in the target environment.

## Compatibility sources

- [Codex CLI reference](https://developers.openai.com/codex/cli/reference/)
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Claude plugin distribution](https://code.claude.com/docs/en/plugins/publish)
- [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins)

The launcher uses the documented interactive `codex [PROMPT]` and `claude [prompt]` forms. It does not depend on account-pool launchers or private local services.

Copyright 2026 Compound Labs. All rights reserved. See [LICENSE](LICENSE) for permission to install, use, and locally adapt this package.
