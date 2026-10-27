#!/usr/bin/env python3
"""Launch a fresh interactive client once, through a user-visible terminal."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time

MARKER = "[SESSION HANDOFF — RECEIVER]"
VERSION = "0.1.4"


def now():
    return datetime.now(timezone.utc).isoformat()


def read_receipt(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    tmp = path.with_suffix(".pending")
    with tmp.open("w", encoding="utf-8") as stream:
        os.chmod(tmp, 0o600)
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    os.replace(tmp, path)


def command_array(raw):
    value = json.loads(raw)
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x or "\0" in x for x in value):
        raise ValueError("command must be a nonempty JSON array of nonempty strings")
    return value


def existing_executable(value):
    found = shutil.which(value)
    if not found:
        raise ValueError(f"executable is unavailable: {value}")
    return str(Path(found).resolve())


def default_state():
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return base / "session-handoffs"


def terminal_command(args, run_command, runner):
    if args.terminal_command_json:
        prefix = command_array(args.terminal_command_json)
        prefix[0] = existing_executable(prefix[0])
        return prefix + run_command
    if sys.platform == "darwin":
        runner.write_text("#!/bin/sh\nexec " + shlex.join(run_command) + "\n", encoding="utf-8")
        runner.chmod(0o700)
        return ["/usr/bin/open", "-a", "Terminal", str(runner)]
    if sys.platform.startswith("linux"):
        for terminal, flags in [("x-terminal-emulator", ["-e"]), ("gnome-terminal", ["--"]), ("konsole", ["-e"]), ("xterm", ["-e"])]:
            binary = shutil.which(terminal)
            if binary:
                return [binary, *flags, *run_command]
    raise ValueError("no supported visible terminal; pass --terminal-command-json with a terminal executable and its execute flags")


def launch(args):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", args.id):
        raise ValueError("--id must be 1–80 letters, digits, periods, underscores or hyphens, starting with a letter or digit")
    cwd = args.cwd.expanduser().resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError("--cwd must be a directory")
    prompt = args.prompt_file.read_text(encoding="utf-8").strip()
    if not prompt or "\0" in prompt:
        raise ValueError("prompt must be nonempty UTF-8 text without NUL characters")
    if prompt.startswith(MARKER):
        raise ValueError("receiver handoffs cannot be forwarded automatically; prepare a new handoff only after a new explicit user request")
    if len(prompt.encode("utf-8")) > 60_000:
        raise ValueError("prompt exceeds 60 KB; put large supporting material in project files and reference their absolute paths")
    client = command_array(args.client_command_json) if args.client_command_json else [args.destination]
    client[0] = existing_executable(client[0])
    state = args.state_dir.expanduser().resolve()
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Require a private state directory; it contains prompts and authorization context.
    if os.name == "posix" and state.stat().st_mode & 0o077:
        raise ValueError("state directory must be private (chmod 700), or choose a new --state-dir")
    receipt = state / (args.id + ".json")
    payload = (
        f"{MARKER}\nYou are the fresh {args.destination} destination for a task handed off from {args.source}.\n"
        "Execute the task here. This marker and any quoted skill invocation are handoff history, not a request to launch another session. "
        "A further handoff requires a new explicit user request. Preserve the stated scope and authorization; if a required tool or permission is absent, report it honestly.\n\n"
        + prompt + "\n"
    )
    data = {"version": VERSION, "id": args.id, "source": args.source, "destination": args.destination,
            "cwd": str(cwd), "client": client, "prompt": payload,
            "prompt_sha256": hashlib.sha256(payload.encode()).hexdigest(),
            "status": "prepared", "created_at": now()}
    # Reserve the ID before creating a terminal. An ambiguous attempt stays reserved.
    try:
        fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            old = read_receipt(receipt)
        except (OSError, json.JSONDecodeError):
            old = {"status": "reserved"}  # Another launcher may still be writing the reservation.
        print(json.dumps({"id": args.id, "status": old.get("status"), "receipt": str(receipt), "launched": False,
                          "message": "ID already reserved; inspect the existing terminal and receipt before any new attempt"}))
        return 2
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    run_command = [str(Path(sys.executable).resolve()), str(Path(__file__).resolve()), "run", str(receipt)]
    runner = state / (args.id + ".command")
    try:
        command = terminal_command(args, run_command, runner)
        data.update(status="terminal-requested", requested_at=now())
        save(receipt, data)
        result = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        # Some terminals return immediately; others stay alive for the session. Never kill or retry them.
        time.sleep(0.25)
        code = result.poll()
        if code:
            current = read_receipt(receipt)
            if current.get("status") == "terminal-requested":
                current.update(status="launch-uncertain", launcher_exit_code=code)
                save(receipt, current)
    except (OSError, ValueError) as error:
        current = read_receipt(receipt)
        if current.get("status") in ("prepared", "terminal-requested"):
            current.update(status="launch-uncertain", error=str(error))
            save(receipt, current)
    status = read_receipt(receipt).get("status")
    print(json.dumps({"id": args.id, "status": status, "receipt": str(receipt),
                      "message": "Terminal request is not proof the model accepted the task or completed it"}))
    return 1 if status == "launch-uncertain" else 0


def run(receipt):
    data = read_receipt(receipt)
    if data.get("status") not in ("terminal-requested", "launch-uncertain"):
        raise ValueError("receipt is not launchable; refusing duplicate or unprepared execution")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("receiver requires an interactive terminal; no headless fallback is permitted")
    lock = receipt.with_suffix(".started")
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError("client launch already claimed; refusing duplicate execution")
    os.close(fd)
    data.update(status="client-starting", client_started_at=now())
    save(receipt, data)
    print(f"Session handoff {data['id']}: starting {data['destination']} in {data['cwd']}", flush=True)
    try:
        env = os.environ.copy()
        if data["destination"] == "claude":
            # This is a new terminal, not a nested invocation in the sender's tool stream.
            env.pop("CLAUDECODE", None)
        result = subprocess.run([*data["client"], data["prompt"]], cwd=data["cwd"], env=env, check=False)
        data.update(status="client-exited", client_exit_code=result.returncode, client_exited_at=now())
        # The client has received its initial prompt; retain only the hash in this receipt.
        data.pop("prompt", None)
        save(receipt, data)
        return result.returncode
    except OSError as error:
        data.update(status="client-start-failed", error=str(error))
        save(receipt, data)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("launch", help="request one fresh terminal session; requires explicit user authorization")
    start.add_argument("--from", dest="source", choices=["codex", "claude"], required=True)
    start.add_argument("--to", dest="destination", choices=["codex", "claude"], required=True)
    start.add_argument("--prompt-file", type=Path, required=True)
    start.add_argument("--cwd", type=Path, required=True)
    start.add_argument("--id", required=True, help="unique operation ID; repeat attempts with this ID never open another terminal")
    start.add_argument("--state-dir", type=Path, default=default_state())
    start.add_argument("--client-command-json", help='optional executable/arguments array, e.g. ["codex", "--model", "chosen-model"]')
    start.add_argument("--terminal-command-json", help='optional terminal prefix array; the Python receiver command is appended as individual arguments')
    receive = sub.add_parser("run", help="internal terminal receiver; do not run in the sending agent terminal")
    receive.add_argument("receipt", type=Path)
    status = sub.add_parser("status", help="show a receipt without disclosing the prompt")
    status.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "launch":
            return launch(args)
        if args.action == "run":
            return run(args.receipt)
        data = read_receipt(args.receipt)
        data.pop("prompt", None)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"handoff: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
