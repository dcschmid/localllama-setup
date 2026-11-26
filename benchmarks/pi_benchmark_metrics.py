"""Read-only observations from the local llama.cpp user service."""

import re
import subprocess


def model_pid():
    return subprocess.check_output(
        ["systemctl", "--user", "show", "-P", "MainPID", "llama-cpp.service"],
        text=True,
    ).strip()


def server_timings(start, stop):
    result = subprocess.run(
        ["journalctl", "--user", "-u", "llama-cpp.service", "--since", f"@{start:.6f}",
         "--until", f"@{stop:.6f}", "-o", "cat", "--no-pager"],
        text=True, capture_output=True,
    )
    paired = {}
    for line in result.stdout.splitlines():
        match = re.search(
            r"task\s+(\d+)\s+\|\s+(prompt eval|eval) time\s+=\s+([\d.]+) ms\s+/\s*(\d+) tokens", line,
        )
        if match:
            task, phase, ms, tokens = match.groups()
            paired.setdefault(task, {})[phase.replace(" ", "_")] = {
                "ms": float(ms), "tokens": int(tokens),
                "tokens_per_s": round(int(tokens) / float(ms) * 1000, 2) if float(ms) else None,
            }
    return list(paired.values())
