"""Installed launch guard; preserve the source guard's exit-1 blocking policy."""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print("Usage: nannersvrhub-check GAME COMMAND [ARG ...]", file=sys.stderr)
        return 2
    game, command = args[0], args[1:]
    if not os.environ.get("VRHUB_SKIP_CHECK"):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        try:
            result = subprocess.run([sys.executable, "-m", "vrhub.cli", "verify", game, "--quiet"],
                                    capture_output=True, text=True, env=env)
            output = result.stdout + result.stderr
            if output:
                print(output, end="" if output.endswith("\n") else "\n", file=sys.stderr)
            if result.returncode == 1:
                notify = shutil.which("notify-send")
                if notify:
                    try:
                        subprocess.run([notify, "-u", "critical", "NAnnersVRhub: game not started",
                                        "\n".join(output.splitlines()[:6])], timeout=2, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                return 1
        except OSError as exc:
            print(f"NAnnersVRhub check unavailable: {exc}", file=sys.stderr)
    os.execvp(command[0], command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
