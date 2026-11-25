"""PreToolUse hook: ask the user before commands that change stbc.exe or overwrite edited game files.

Covers tools/exe_patch.py apply|revert|upgrade and tools/deploy.py install --force.
Reads the hook JSON on stdin; prints a permission decision only when a rule matches.
"""
import json
import re
import sys

RULES = [
    (re.compile(r"exe_patch(\.py)?\b.*\b(apply|revert|upgrade)\b", re.I | re.S),
     "exe_patch.py changes stbc.exe (every ship in the game): needs the user's explicit OK and the game closed."),
    (re.compile(r"deploy(\.py)?\b(?=.*\binstall\b)(?=.*--force\b)", re.I | re.S),
     "deploy.py install --force overwrites files the user edited in the game: diff the game copy first."),
]


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    for pattern, reason in RULES:
        if pattern.search(command):
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
            }}))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
