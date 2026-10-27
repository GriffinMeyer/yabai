"""Exercise installer failure paths without signing, sudo, or live service changes."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class InstallLocalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "bin").mkdir()
        self.installer = self.root / "scripts/install-local.sh"
        shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts/install-local.sh", self.installer)
        self.source = self.root / "bin/yabai"
        self.source.write_text('#!/bin/sh\nprintf "candidate %s\\n" "$*" >> "$CALL_LOG"\n')
        self.source.chmod(0o755)
        self.prefix = self.root / "installed"
        (self.prefix / "bin").mkdir(parents=True)
        self.installed = self.prefix / "bin/yabai"
        self.installed.write_text("original working binary\n")
        self.log = self.root / "calls.log"
        mock_bin = self.root / "mock-bin"
        mock_bin.mkdir()
        mock = mock_bin / "mock-command"
        mock.write_text("#!" + sys.executable + "\n" + '''
import os
from pathlib import Path
import sys

name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["CALL_LOG"], "a") as stream:
    stream.write(name + " " + " ".join(args) + "\\n")
if name == "id":
    print("501")
elif name == "whoami":
    print("testuser")
elif name == "codesign":
    failure = os.environ.get("FAIL_AT")
    if (failure == "sign" and "-fs" in args) or (failure == "verify" and "--verify" in args):
        sys.exit(1)
elif name == "sudo":
    if args == ["-v"] and os.environ.get("FAIL_AT") == "sudo":
        sys.exit(1)
    if args and args[0] == "tee":
        sys.stdin.read()  # Never write to the real /private/etc/sudoers.d.
''')
        mock.chmod(0o755)
        for command in ("id", "whoami", "codesign", "sudo", "yabai"):
            (mock_bin / command).symlink_to(mock)
        self.env = dict(os.environ, PREFIX=str(self.prefix), YABAI_CERT="test-cert",
                        CALL_LOG=str(self.log), TMPDIR=str(self.root),
                        PATH=str(mock_bin) + os.pathsep + os.environ["PATH"])
        self.env.pop("FAIL_AT", None)

    def run_installer(self, failure=None):
        env = self.env.copy()
        if failure:
            env["FAIL_AT"] = failure
        return subprocess.run(["/bin/bash", str(self.installer)], env=env,
                              capture_output=True, text=True)

    def test_preflight_failures_preserve_installation(self):
        for failure in ("sign", "verify", "sudo"):
            with self.subTest(failure=failure):
                self.log.write_text("")
                result = self.run_installer(failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.installed.read_text(), "original working binary\n")
                self.assertNotIn("--stop-service", self.log.read_text())
                self.assertNotIn("--uninstall-service", self.log.read_text())
                self.assertEqual(list(self.root.glob("yabai-install.*")), [])

    def test_success_signs_before_stopping_service(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.installed.read_bytes(), self.source.read_bytes())
        calls = self.log.read_text()
        self.assertLess(calls.index("codesign --verify"), calls.index("yabai --stop-service"))
        self.assertLess(calls.index("sudo -v"), calls.index("yabai --stop-service"))
        self.assertIn("--load-sa", calls)
        self.assertIn("candidate --start-service", calls)
        self.assertEqual(list(self.root.glob("yabai-install.*")), [])


if __name__ == "__main__":
    unittest.main()
