# Shared handoff workflow

## Prepare the transfer

Infer the assignment from the current conversation. If there is no identifiable task, ask for it before launching. Check which runtime is sending and which one the user requested as destination.

Write a concise UTF-8 prompt file containing:

- The objective, acceptance criteria, and next concrete action.
- Absolute project and reference paths, branch/worktree, and relevant running server details.
- Completed work and verification evidence, including commit IDs where useful.
- Decisions already settled, constraints, and unrelated work to preserve.
- Exact verification commands and what a passing result looks like.
- Existing authorization and its boundaries. A handoff does not authorize deployment, purchases, external messages, or unrelated edits.

Do not include passwords, tokens, private account-routing information, or unrelated conversation history. The receiving client can only access tools, accounts, project instructions, and permissions actually configured in its environment; do not promise inherited authentication or trust. Do not add the receiver marker yourself: the launcher prepends it.

## Launch one session

Resolve this installed skill's directory from the real location of its `SKILL.md`. Use the `scripts/handoff.py` bundled inside that directory with Python 3.9 or newer. Every skill folder contains its own launcher, workflow, and license, so it works when copied independently by a skill installer.

```text
python3 /absolute/installed/skill/scripts/handoff.py launch \
  --from codex --to claude \
  --prompt-file /absolute/path/to/handoff.txt \
  --cwd /absolute/project/path \
  --id unique-task-20261027
```

Replace `--from` and `--to` with the selected skill's direction. Use a unique operation ID, and retain that same ID when inspecting an uncertain attempt. `--cwd` is explicit because session history and project instructions may depend on the starting directory. Use the user's requested session directory; otherwise use the project's directory. A machine-specific convention that every session starts in the home directory is not imposed on other users.

The destination must already be installed and signed in. Defaults are the `codex` or `claude` executable on PATH. The launcher starts an interactive client with the prompt as a single argument; it does not use `exec`, `--print`, resume flags, permission bypasses, or a forced model.

For a Claude Code destination, the receiver clears the inherited `CLAUDECODE` nested-session marker inside the new terminal. Other environment values, including the user's normal CLI authentication configuration, remain unchanged. The receiver refuses to start without an interactive terminal.

For an existing user-configured wrapper or explicitly selected model, `--client-command-json` accepts an executable/argument array. Example: `["codex", "--model", "user-selected-model"]`. This is executable configuration, not untrusted task content. Do not add resume/continue flags, replace identity/account settings, or weaken permissions. The prompt is appended as one final argument.

macOS uses Terminal.app. Linux tries `x-terminal-emulator`, `gnome-terminal`, `konsole`, then `xterm`. For another terminal, pass a JSON prefix such as `--terminal-command-json '["kitty", "--"]'`; the receiver command is appended as individual arguments. The prefix must open a new interactive terminal, not run the client in the sending session. Windows is not supported by the default launcher; a compatible terminal adapter can be configured and tested separately. Do not improvise a detached headless job as a substitute for a visible interactive session.

## Inspect the result

The launcher prints a receipt path. Use:

```text
python3 /absolute/installed/skill/scripts/handoff.py status /absolute/receipt.json
```

`status` excludes the prompt. Receipts and temporary terminal runner files are stored under `$XDG_STATE_HOME/session-handoffs`, or `~/.local/state/session-handoffs`. The directory must be private, mode 0700. Files are mode 0600, except executable runner files (0700).

| Status | Evidence |
|---|---|
| `prepared` | Operation ID reserved; no terminal claim. |
| `terminal-requested` | The terminal launcher was requested; prompt acceptance is unverified. |
| `launch-uncertain` | Terminal launch failed or was ambiguous; inspect before taking another action. |
| `client-starting` | The terminal receiver claimed this operation and attempted the client. This is not model acceptance. |
| `client-start-failed` | The receiver could not start the executable. |
| `client-exited` | The client process exited; its code is recorded. This does not prove the task was completed. |

Read the actual terminal/client output when available before reporting that the handoff is active. If the environment cannot inspect it, report the evidence level honestly. Never claim task completion from a launcher return code.

The operation ID can launch at most once. Repeating `launch` with that ID returns its current status without opening another terminal. The receiver has a separate exclusive start marker, so reopening its runner cannot start another client. If an attempt is uncertain, inspect the terminal and receipt; do not delete receipts or automatically choose a new ID to retry. A further attempt requires evidence no prior client is working and an explicit user decision.

After transfer is confirmed, end the sender's work on that assignment. If launch failed, report the concrete failure and preserve the prepared prompt; do not silently continue the same assignment while a possibly active receiver also works.

The prompt is removed from a receipt after the client exits normally, including nonzero client exits; its SHA-256 remains. An interrupted receiver or failed start can leave the prompt in its private receipt so the user can recover. Once no client/runner is active and the outcome is known, the user may remove the input prompt, `.command` runner, and receipt files. Retain the `.started` marker (or remember retired IDs) if duplicate protection is still needed. Do not remove files used by an active session.
