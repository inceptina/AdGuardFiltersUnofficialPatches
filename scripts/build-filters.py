#!/usr/bin/env python3
"""Generate the combined annoyances and DNS filters from source filters."""

import re
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from subprocess import check_output


ROOT = Path(__file__).resolve().parents[1]
FILTERS = ROOT / "filters"
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
CONDITIONAL = re.compile(r"^[ \t]*!#(if|endif)(?:[ \t]|$)")
INCLUDE = re.compile(r"([ \t]*!#include[ \t]+)(\S+)([ \t]*)")
URL_SCHEME = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:")
SOURCE_DATE_FIELDS = ("! Version:", "! TimeUpdated:")
RULE_CHANGE = r"^[[:space:]]*([^![:space:]]|!#)"


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


def rebase_include(line, source_dir):
    match = INCLUDE.fullmatch(line)
    if match is None:
        return line
    prefix, target, suffix = match.groups()
    if target.startswith("/") or URL_SCHEME.match(target):
        return line
    return f"{prefix}{source_dir}/{target.removeprefix('./')}{suffix}"


def update_source_metadata(path, lines):
    if not any(line.startswith(SOURCE_DATE_FIELDS) for line in lines):
        return

    # Find the last commit that changed rules or directives on the published branch.
    timestamp = check_output(
        [
            "git", "log", "-1", "--first-parent", "--diff-merges=first-parent",
            "--format=%ct", "--no-patch", "-G", RULE_CHANGE, "--", path.relative_to(ROOT).as_posix(),
        ],
        cwd=ROOT,
        text=True,
    ).strip()
    if not timestamp:
        return

    updated = datetime.fromtimestamp(int(timestamp), timezone.utc)
    original = path.read_bytes().decode("utf-8")
    contents = original
    for field, date in zip(SOURCE_DATE_FIELDS, (updated.strftime("%y%m%d"), updated.isoformat())):
        contents = re.sub(
            rf"(?m)^(\ufeff?{field})[^\r\n]*", rf"\g<1> {date}", contents, count=1,
        )
    if contents != original:
        path.write_bytes(contents.encode("utf-8"))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-source-metadata", action="store_true",
        help="also date source filters from their committed rule changes",
    )
    args = parser.parse_args()

    sources = {
        path: path.read_text(encoding="utf-8-sig").splitlines()
        for path in sorted(FILTERS.rglob("*.txt"))
        if path not in (ANNOYANCES, DNS)
    }

    sections = []
    for path, lines in sources.items():
        if path.parent != FILTERS / "annoyances":
            continue
        source_dir = path.parent.relative_to(ANNOYANCES.parent).as_posix()
        content = "\n".join(
            rebase_include(line, source_dir) for line in lines
            if not line.startswith(METADATA)
        ).strip("\n")
        if content:
            sections.append(content)
    body = "\n\n".join(sections)
    write_filter(ANNOYANCES, "Annoyances", body)

    rules = {}
    for lines in sources.values():
        depth = 0
        for line in lines:
            conditional = CONDITIONAL.match(line)
            if conditional:
                depth = depth + 1 if conditional.group(1) == "if" else max(0, depth - 1)
            elif depth == 0 and DOMAIN_RULE.fullmatch(line):
                rules.setdefault(line.lower(), line)
    write_filter(DNS, "DNS", "\n".join(rules.values()))

    if args.update_source_metadata:
        for path, lines in sources.items():
            update_source_metadata(path, lines)


if __name__ == "__main__":
    main()
