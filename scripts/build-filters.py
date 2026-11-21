#!/usr/bin/env python3
"""Generate the combined annoyances and DNS filters from source filters."""

import re
from datetime import datetime, timezone
from pathlib import Path


FILTERS = Path(__file__).resolve().parents[1] / "filters"
ANNOYANCES = FILTERS / "annoyances.txt"
DNS = FILTERS / "dns.txt"
HEADER = """! Title: AdGuard Annoyances filter Unofficial Patches
! Description: Unofficial patch for AdGuard Annoyances filter
! Version: {version}
! TimeUpdated: {updated}
! Expires: 5 days (update frequency)
! Homepage: https://github.com/inceptina/AdGuardFiltersUnofficialPatches"""
METADATA = (
    "! Title:", "! Description:", "! Version:", "! TimeUpdated:",
    "! Expires:", "! Homepage:", "! License:", "! Checksum:", "! Diff-Path:",
)
LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
DOMAIN_RULE = re.compile(rf"\|\|{LABEL}(?:\.{LABEL})*\^", re.IGNORECASE | re.ASCII)


def main():
    sources = {
        path: path.read_text(encoding="utf-8-sig").splitlines()
        for path in sorted(FILTERS.rglob("*.txt"))
        if path not in (ANNOYANCES, DNS)
    }

    sections = []
    for path, lines in sources.items():
        if path.parent != FILTERS / "annoyances":
            continue
        content = "\n".join(
            line for line in lines
            if not line.startswith(METADATA)
        ).strip("\n")
        if content:
            sections.append(content)
    body = "\n\n".join(sections)
    previous = ANNOYANCES.read_text(encoding="utf-8") if ANNOYANCES.exists() else ""
    previous_header, _, previous_body = previous.partition("\n\n")
    updated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if body == previous_body.rstrip("\n"):
        for line in previous_header.splitlines():
            if line.startswith("! TimeUpdated: "):
                updated = line.removeprefix("! TimeUpdated: ")
                break
    version = datetime.fromisoformat(updated).strftime("%y%m%d")
    header = HEADER.format(updated=updated, version=version)
    ANNOYANCES.write_text(header + ("\n\n" + body if body else "") + "\n", encoding="utf-8")

    rules = {}
    for lines in sources.values():
        for line in lines:
            if DOMAIN_RULE.fullmatch(line):
                rules.setdefault(line.lower(), line)
    DNS.write_text("".join(rule + "\n" for rule in rules.values()), encoding="utf-8")


if __name__ == "__main__":
    main()
