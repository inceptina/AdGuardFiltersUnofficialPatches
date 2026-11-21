#!/usr/bin/env python3
"""Generate the combined annoyances and DNS filters from source filters."""

import re
from pathlib import Path


FILTERS = Path(__file__).resolve().parents[1] / "filters"
ANNOYANCES = FILTERS / "annoyances.txt"
DNS = FILTERS / "DNS.txt"
HEADER = (
    "! Title: Unofficial Patches for AdGuard - Annoyances\n"
    "! Description: Combined unofficial filters for web annoyances.\n"
    "! Homepage: https://github.com/inceptina/AdGuardFiltersUnofficialPatches\n"
)
LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
DOMAIN_RULE = re.compile(rf"\|\|{LABEL}(?:\.{LABEL})*\^", re.IGNORECASE | re.ASCII)


def main():
    sources = {
        path: path.read_text(encoding="utf-8-sig").splitlines()
        for path in sorted(FILTERS.rglob("*.txt"))
        if path not in (ANNOYANCES, DNS)
    }

    sections = [HEADER.rstrip("\n")]
    for path, lines in sources.items():
        if path.parent != FILTERS / "annoyances":
            continue
        content = "\n".join(
            line for line in lines
            if not line.startswith(("! Title:", "! Description:", "! Homepage:"))
        ).strip("\n")
        if content:
            sections.append(content)
    ANNOYANCES.write_text("\n\n".join(sections) + "\n", encoding="utf-8")

    rules = {}
    for lines in sources.values():
        for line in lines:
            if DOMAIN_RULE.fullmatch(line):
                rules.setdefault(line.lower(), line)
    DNS.write_text("".join(rule + "\n" for rule in rules.values()), encoding="utf-8")


if __name__ == "__main__":
    main()
