#!/usr/bin/env python3
"""Pre-commit hook: block commits containing credential-like patterns.

Structural over policy — make the wrong thing impossible.

This lives in tools/ (committed) and is wired via core.hooksPath.
A fresh clone needs one command:  git config core.hooksPath .githooks
The .githooks/pre-commit shim calls this script.
"""

import re
import subprocess
import sys

PATTERNS = [
    # Generic key/token values in quotes
    r"""['"](?:sk|pk|api|token|secret|password|auth|key)[-_]?[A-Za-z0-9]{20,}['"]""",
    # AWS access key IDs
    r"AKIA[0-9A-Z]{16}",
    # GitHub tokens
    r"gh[pousr]_[A-Za-z0-9_]{36,}",
    # Variable assignments with long secret-looking values
    r"(?:API_KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)\s*=\s*['\"][A-Za-z0-9+/=_\-]{16,}['\"]",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in PATTERNS]

# Lines containing this marker are intentionally exempt (e.g. test fixtures).
# Every exemption is visible in the diff and reviewable.
PRAGMA = "# pragma: allowlist secret"


def get_staged_diff() -> list[tuple[str, str]]:
    """Return list of (filename, diff_text) for staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, check=True,
    )
    filenames = [f for f in result.stdout.strip().splitlines() if f]
    if not filenames:
        return []

    pairs = []
    for fname in filenames:
        diff = subprocess.run(
            ["git", "diff", "--cached", "-U0", "--", fname],
            capture_output=True, text=True, check=True,
        )
        pairs.append((fname, diff.stdout))
    return pairs


def scan(pairs: list[tuple[str, str]]) -> list[str]:
    """Return human-readable hits."""
    hits = []
    for fname, diff_text in pairs:
        for line in diff_text.splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            if PRAGMA in line:
                continue
            for pattern in COMPILED:
                if pattern.search(line):
                    hits.append(f"  {fname}: {line.strip()}")
                    break
    return hits


def main() -> int:
    pairs = get_staged_diff()
    if not pairs:
        return 0

    hits = scan(pairs)
    if hits:
        print()
        print("=" * 60)
        print("  BLOCKED: Staged changes contain credential-like values.")
        print("  Remove secrets before committing.")
        print("=" * 60)
        print()
        for h in hits:
            print(h)
        print()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
