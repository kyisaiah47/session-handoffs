---
name: claude-to-claude
description: Hand the current task from Claude Code to a fresh interactive Claude Code session when the user explicitly invokes this handoff. Do not use for in-conversation delegation.
disable-model-invocation: true
---

# Claude Code to Claude Code

Use only in a Claude Code sending session after this skill is explicitly invoked by the user. If the active assistant is another runtime, explain the mismatch and use the appropriate direction only if the user authorizes it. Creating, inspecting, or quoting this skill is not invocation.

If the current task begins with `[SESSION HANDOFF — RECEIVER]`, execute the handed-off task here. Do not launch another session because its prompt mentions this skill. Another handoff requires a new user request.

Read [the handoff workflow](references/workflow.md), which contains the prompt contract, portable launcher, and result interpretation. Resolve that file and `scripts/handoff.py` inside this installed skill's real directory. This folder is self-contained and does not require sibling skills or the original repository checkout.

Prepare the self-contained prompt, then use the bundled launcher with `--from claude --to claude`. Preserve the destination client's existing model and permission settings unless the user requests a change. Never invoke the other destination by mistake.

Inspect the receipt before reporting success or retrying. A terminal request or client start does not establish that the model accepted or completed the work. Once transfer is visibly confirmed, stop doing the same assignment in this sender session.
