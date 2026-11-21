#!/usr/bin/env python3
"""Generate the combined annoyances and DNS filters from source filters."""

import re
from datetime import datetime, timezone
from pathlib import Path


FILTERS = Path(__file__).resolve().parents[1] / "filters"
ANNOYANCES = FILTERS / "annoyances.txt"
DNS = FILTERS / "dns.txt"
HEADER = """! Title: AdGuard {name} filter Unofficial Patches
! Description: Unofficial patch for AdGuard {name} filter
! Version: {version}
! TimeUpdated: {updated}
! Expires: 5 days (update frequency)
! Homepage: https://github.com/inceptina/AdGuardFiltersUnofficialPatches
! License: https://github.com/inceptina/AdGuardFiltersUnofficialPatches/blob/main/LICENSE"""
METADATA = (
    "! Title:", "! Description:", "! Version:", "! TimeUpdated:",
    "! Expires:", "! Homepage:", "! License:", "! Checksum:", "! Diff-Path:",
)
LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
DOMAIN_RULE = re.compile(rf"\|\|{LABEL}(?:\.{LABEL})*\^", re.IGNORECASE | re.ASCII)


def write_filter(path, name, body):
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    previous_header, _, previous_body = previous.partition("\n\n")
    updated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if body == previous_body.rstrip("\n"):
        for line in previous_header.splitlines():
            if line.startswith("! TimeUpdated: "):
                updated = line.removeprefix("! TimeUpdated: ")
                break
    version = datetime.fromisoformat(updated).strftime("%y%m%d")
    header = HEADER.format(name=name, updated=updated, version=version)
    path.write_text(header + ("\n\n" + body if body else "") + "\n", encoding="utf-8")


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
    write_filter(ANNOYANCES, "Annoyances", body)

    rules = {}
    for lines in sources.values():
        for line in lines:
            if DOMAIN_RULE.fullmatch(line):
                rules.setdefault(line.lower(), line)
    write_filter(DNS, "DNS", "\n".join(rules.values()))


if __name__ == "__main__":
    main()
