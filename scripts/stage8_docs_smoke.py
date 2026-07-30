from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    phase = repository / ".venv" / "Scripts" / ("phase.exe" if os.name == "nt" else "phase")
    commands = [
        [str(phase), "--version"],
        [str(phase), "doctor"],
        [str(phase), "contracts", "list"],
        [str(phase), "contracts", "describe", "--contract", "source_admission.v1@1.0.0"],
        [str(phase), "contracts", "describe", "--contract", "knowledge_admission.v1@1.0.0"],
        [str(phase), "validate", "--help"],
        [str(phase), "plan", "--help"],
        [str(phase), "execute", "--help"],
        [str(phase), "inspect", "--help"],
    ]
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    records: list[dict[str, object]] = []
    for command in commands:
        completed = subprocess.run(command, cwd=repository, env=environment, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise AssertionError(f"documented command failed: {command!r} stdout={completed.stdout!r} stderr={completed.stderr!r}")
        records.append({"command": command[1:], "stdout_lines": len(completed.stdout.splitlines())})
    if records[0]["stdout_lines"] != 1:
        raise AssertionError("version output is not one line")
    for index in (1, 2, 3, 4):
        json.loads(subprocess.run(commands[index], cwd=repository, env=environment, capture_output=True, text=True, check=True).stdout)

    readme = (repository / "README.md").read_text(encoding="utf-8")
    links = [target for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", readme) if not target.startswith(("http://", "https://", "#"))]
    missing = [target for target in links if not (repository / target).is_file()]
    if missing:
        raise AssertionError(f"missing documentation links: {missing}")
    summary = {"success": True, "commands": len(commands), "links_checked": len(links), "records": records}
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
