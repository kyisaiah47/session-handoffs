"""Integration tests use local stubs and PTYs; no assistant API or GUI is launched."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import importlib.util

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/handoff.py"


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="session-handoff-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cwd = self.root / "work with ' quotes and spaces"
        self.cwd.mkdir()
        self.state = self.root / "state"
        self.prompt = self.root / "prompt.txt"
        self.text = "Fix the parser.\nLiteral: $(touch NEVER) `echo bad` ; 'quoted' \"double\" — $HOME\n"
        self.prompt.write_text(self.text, encoding="utf-8")
        self.events = self.root / "events.jsonl"
        self.client = self.root / "stub client"
        self.client.write_text("#!/usr/bin/env python3\nimport os,json,sys\nfrom pathlib import Path\nwith Path(os.environ['TEST_EVENTS']).open('a') as f: f.write(json.dumps({'argv':sys.argv[1:],'cwd':os.getcwd(),'claudecode':os.environ.get('CLAUDECODE')})+'\\n')\nraise SystemExit(int(os.environ.get('TEST_CLIENT_EXIT','0')))\n")
        self.client.chmod(0o700)
        self.terminal = self.root / "stub terminal"
        self.terminal.write_text("#!/usr/bin/env python3\nimport os,pty,subprocess,sys\nmaster,slave=pty.openpty()\np=subprocess.Popen(sys.argv[1:],stdin=slave,stdout=slave,stderr=slave)\nos.close(slave)\nwhile True:\n try:\n  if not os.read(master,65536): break\n except OSError: break\nos.close(master)\nraise SystemExit(p.wait())\n")
        self.terminal.chmod(0o700)
        self.env = dict(os.environ, TEST_EVENTS=str(self.events), CLAUDECODE="1")

    def command(self, *extra, source="codex", destination="claude", operation="handoff-1"):
        return [sys.executable, str(SCRIPT), "launch", "--from", source, "--to", destination,
                "--cwd", str(self.cwd), "--prompt-file", str(self.prompt), "--id", operation,
                "--state-dir", str(self.state), "--client-command-json", json.dumps([str(self.client), "--chosen-option", "literal value"]),
                "--terminal-command-json", json.dumps([str(self.terminal)]), *extra]

    def invoke(self, *extra, **kwargs):
        return subprocess.run(self.command(*extra, **kwargs), env=self.env, text=True, capture_output=True)

    def receipt(self, operation="handoff-1"):
        path = self.state / (operation + ".json")
        for _ in range(100):
            data = json.loads(path.read_text())
            if data["status"] in ("client-exited", "client-start-failed", "launch-uncertain"):
                return data
            time.sleep(.02)
        self.fail("stub receiver did not finish")

    def test_all_four_directions_preserve_prompt_cwd_and_settings(self):
        for source in ("codex", "claude"):
            for target in ("codex", "claude"):
                with self.subTest(source=source, target=target):
                    operation = source + "-" + target
                    result = self.invoke(source=source, destination=target, operation=operation)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    data = self.receipt(operation)
                    self.assertEqual(data["status"], "client-exited")
                    self.assertEqual(data["client_exit_code"], 0)
                    event = json.loads(self.events.read_text().splitlines()[-1])
                    self.assertEqual(event["argv"][:2], ["--chosen-option", "literal value"])
                    self.assertEqual(len(event["argv"]), 3)
                    self.assertTrue(event["argv"][-1].startswith("[SESSION HANDOFF — RECEIVER]"))
                    self.assertIn(f"fresh {target} destination", event["argv"][-1])
                    self.assertIn(f"handed off from {source}", event["argv"][-1])
                    self.assertTrue(event["argv"][-1].endswith(self.text.strip()+"\n"))
                    self.assertEqual(event["cwd"], str(self.cwd.resolve()))
                    self.assertEqual(event["claudecode"], None if target == "claude" else "1")
                    self.assertNotIn("prompt", data)
                    self.assertEqual(os.stat(self.state).st_mode & 0o777, 0o700)
                    self.assertEqual(os.stat(self.state / (operation+".json")).st_mode & 0o777, 0o600)
        self.assertFalse((self.cwd / "NEVER").exists())

    def test_same_id_cannot_launch_again(self):
        self.assertEqual(self.invoke().returncode, 0)
        self.receipt()
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["launched"])
        self.assertEqual(len(self.events.read_text().splitlines()), 1)

    def test_receiver_marker_is_not_relaunched(self):
        self.prompt.write_text("[SESSION HANDOFF — RECEIVER]\nAlready transferred")
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot be forwarded", result.stderr)
        self.assertFalse(self.events.exists())

    def test_terminal_failure_is_uncertain_and_reserved(self):
        result = self.invoke("--terminal-command-json", json.dumps(["/usr/bin/false"]))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.receipt()["status"], "launch-uncertain")
        self.assertEqual(self.invoke().returncode, 2)
        self.assertFalse(self.events.exists())

    def test_client_failure_is_reported_without_relaunch(self):
        self.env["TEST_CLIENT_EXIT"] = "17"
        self.invoke()
        data = self.receipt()
        self.assertEqual(data["client_exit_code"], 17)
        self.assertEqual(self.invoke().returncode, 2)
        self.assertEqual(len(self.events.read_text().splitlines()), 1)

    def test_status_hides_prepared_prompt(self):
        self.invoke("--terminal-command-json", json.dumps(["/usr/bin/false"]))
        result = subprocess.run([sys.executable, str(SCRIPT), "status", str(self.state/"handoff-1.json")], text=True, capture_output=True)
        data = json.loads(result.stdout)
        self.assertNotIn("prompt", data)
        self.assertNotIn("Fix the parser", result.stdout)

    def test_noninteractive_receiver_refuses_execution(self):
        self.invoke("--terminal-command-json", json.dumps(["/usr/bin/false"]))
        result = subprocess.run([sys.executable, str(SCRIPT), "run", str(self.state/"handoff-1.json")], text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires an interactive terminal", result.stderr)
        self.assertFalse(self.events.exists())

    def test_concurrent_requests_launch_only_once(self):
        procs = [subprocess.Popen(self.command(), env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        results = [p.communicate(timeout=10) for p in procs]
        self.assertEqual(sorted(p.returncode for p in procs), [0,2], results)
        self.receipt()
        self.assertEqual(len(self.events.read_text().splitlines()), 1)

    def test_reopened_receiver_cannot_launch_twice(self):
        self.invoke()
        self.receipt()
        result = subprocess.run([str(self.terminal), sys.executable, str(SCRIPT), "run", str(self.state/"handoff-1.json")], env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.events.read_text().splitlines()), 1)

    def test_macos_runner_contains_only_quoted_receiver_command(self):
        spec = importlib.util.spec_from_file_location("handoff", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        runner = self.root / "quote ' ; $HOME.command"
        command = [sys.executable, "/package with ' quotes/handoff.py", "run", "/state/receipt.json"]
        with mock.patch.object(module.sys, "platform", "darwin"):
            actual = module.terminal_command(type("Args", (), {"terminal_command_json":None})(), command, runner)
        self.assertEqual(actual, ["/usr/bin/open", "-a", "Terminal", str(runner)])
        import shlex
        self.assertEqual(shlex.split(runner.read_text().splitlines()[1])[1:], command)
        self.assertNotIn("Fix the parser", runner.read_text())


if __name__ == "__main__":
    unittest.main()
