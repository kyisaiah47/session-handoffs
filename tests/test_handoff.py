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
import shutil

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
        self.script = SCRIPT

    def command(self, *extra, source="codex", destination="claude", operation="handoff-1"):
        return [sys.executable, str(self.script), "launch", "--from", source, "--to", destination,
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
        result = subprocess.run([sys.executable, str(self.script), "status", str(self.state/"handoff-1.json")], text=True, capture_output=True)
        data = json.loads(result.stdout)
        self.assertNotIn("prompt", data)
        self.assertNotIn("Fix the parser", result.stdout)

    def test_noninteractive_receiver_refuses_execution(self):
        self.invoke("--terminal-command-json", json.dumps(["/usr/bin/false"]))
        result = subprocess.run([sys.executable, str(self.script), "run", str(self.state/"handoff-1.json")], text=True, capture_output=True)
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
        result = subprocess.run([str(self.terminal), sys.executable, str(self.script), "run", str(self.state/"handoff-1.json")], env=self.env, capture_output=True)
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

    def test_each_copied_skill_runs_without_repository_assets(self):
        package = SCRIPT.parents[1]
        for skill in sorted((package / "skills").iterdir()):
            if not skill.is_dir():
                continue
            with self.subTest(skill=skill.name):
                isolated = self.root / "isolated" / skill.name
                shutil.copytree(skill, isolated, ignore=shutil.ignore_patterns("__pycache__"))
                self.assertTrue((isolated / "LICENSE").is_file())
                self.assertTrue((isolated / "agents/openai.yaml").is_file())
                text = (isolated / "SKILL.md").read_text()
                for link in __import__("re").findall(r"\]\(([^)]+)\)", text):
                    target = (isolated / link).resolve()
                    self.assertTrue(target.is_relative_to(isolated.resolve()))
                    self.assertTrue(target.is_file())
                self.assertNotIn("../../", text)
                self.assertNotIn("/absolute/package/root", (isolated / "references/workflow.md").read_text())
                self.script = isolated / "scripts/handoff.py"
                source, destination = skill.name.split("-to-")
                result = self.invoke(source=source, destination=destination, operation=skill.name)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = self.receipt(skill.name)
                self.assertEqual(data["status"], "client-exited")
                self.assertEqual(data["client_exit_code"], 0)
                self.assertEqual(data["version"], json.loads((SCRIPT.parent.parent / "plugin.json").read_text())["version"])
                self.assertEqual(self.invoke(source=source, destination=destination, operation=skill.name).returncode, 2)
                event = json.loads(self.events.read_text().splitlines()[-1])
                self.assertIn(f"fresh {destination} destination", event["argv"][-1])
                self.assertIn(self.text.strip(), event["argv"][-1])
                status = subprocess.run([sys.executable, str(self.script), "status", str(self.state/(skill.name+".json"))], text=True, capture_output=True)
                self.assertEqual(status.returncode, 0, status.stderr)
                self.assertNotIn("prompt", json.loads(status.stdout))
        self.assertEqual(len(self.events.read_text().splitlines()), 4)

    def test_bundle_sync_detects_and_repairs_drift(self):
        spec = importlib.util.spec_from_file_location("sync_skills", SCRIPT.parent / "sync_skills.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.sync(SCRIPT.parents[1], check=True), [])
        fixture = self.root / "sync-fixture"
        fixture.mkdir()
        for asset in module.ASSETS:
            target = fixture / asset
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((SCRIPT.parents[1] / asset).read_bytes())
        for name in module.SKILLS:
            folder = fixture / "skills" / name
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text("fixture")
        missing = module.sync(fixture, check=True)
        self.assertEqual(len(missing), len(module.ASSETS)*len(module.SKILLS))
        self.assertFalse((fixture/"skills/codex-to-codex/scripts/handoff.py").exists())
        self.assertEqual(module.sync(fixture), [])
        self.assertEqual(module.sync(fixture, check=True), [])
        copied = fixture/"skills/codex-to-codex/scripts/handoff.py"
        copied.write_text("changed")
        self.assertEqual(module.sync(fixture, check=True), ["codex-to-codex/scripts/handoff.py"])
        self.assertEqual(copied.read_text(), "changed")
        module.sync(fixture)
        self.assertEqual(copied.read_bytes(), (fixture/"scripts/handoff.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
