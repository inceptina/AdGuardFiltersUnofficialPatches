#!/usr/bin/env python3
"""Import upstream issues and fill the next three places in the queue."""

import argparse
import json
import re
from html import escape
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "AdguardTeam/AdguardFilters"
FIRST_CREATED_AT = "2026-01-01T00:00:00Z"
LABELS = (
    "A: Rejected",
    "A: Problematic",
    "A: By Design",
    "A: Won't fix",
)
QUEUE_SIZE = 3
STATUSES = {"open", "fixed", "skipped"}
WEB_URL = re.compile(r"https?://[^\s<>\[\]\"()]+", re.IGNORECASE)
DOMAIN = re.compile(
    r"(?<![\w@.\-])"
    r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
    r"(?:xn--[a-z0-9-]+|[a-z]{2,63})(?::[0-9]+)?"
    r"(?:/[^\s<>\[\]\"()]*)?(?![\w-]|\.[\w-])",
    re.IGNORECASE | re.ASCII,
)


def fetch_issues():
    """List each label separately so an issue with any of the labels qualifies."""
    incoming = {}
    for label in LABELS:
        for page in count(1):
            query = urlencode({
                "state": "all",
                "labels": label,
                "sort": "created",
                "direction": "desc",
                "per_page": 100,
                "page": page,
            })
            request = Request(
                f"https://api.github.com/repos/{UPSTREAM}/issues?{query}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "AdGuardFiltersUnofficialPatches",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            with urlopen(request, timeout=30) as response:
                batch = json.load(response)

            for issue in batch:
                if issue["created_at"] < FIRST_CREATED_AT or "pull_request" in issue:
                    continue
                number = issue["number"]
                incoming[number] = {
                    "number": number,
                    "url": issue["html_url"],
                    "title": issue["title"],
                    "created_at": issue["created_at"],
                    "labels": [item["name"] for item in issue["labels"]],
                    "state": issue["state"],
                }
            # Pages are newest first. Nothing beyond the cutoff can qualify.
            if len(batch) < 100 or batch[-1]["created_at"] < FIRST_CREATED_AT:
                break
    return sorted(incoming.values(), key=lambda issue: (issue["created_at"], issue["number"]))


def site_from_title(title):
    urls = set(WEB_URL.findall(title))
    if not urls and not title.lstrip().lower().startswith(("google play:", "app store:")):
        urls = set(DOMAIN.findall(title))
    # Ambiguous titles and app package names do not identify a site.
    return next(iter(urls)) if len(urls) == 1 else None


def fill_queue(issues, statuses, history):
    if any(record["status"] not in {"fixed", "skipped"} for record in history):
        raise ValueError("issue-history.json must contain only fixed or skipped records")

    # An interrupted local write may already have saved a finished record.
    statuses[:] = [record for record in statuses if record not in history]
    numbers = {issue["number"] for issue in issues}
    if len(numbers) != len(issues):
        raise ValueError("issues.json contains duplicate issue numbers")

    tracked = set()
    active = set()
    for record in [*history, *statuses]:
        status = record["status"]
        issue_numbers = record["issues"]
        if status not in STATUSES or not isinstance(issue_numbers, list) or not issue_numbers:
            raise ValueError("each status record needs a valid status and an issues list")
        for number in issue_numbers:
            if type(number) is not int or number not in numbers:
                raise ValueError(f"unknown issue in status files: {number}")
            if number in tracked:
                raise ValueError(f"issue #{number} appears more than once in the status files")
            tracked.add(number)
        if status == "open":
            active.update(issue_numbers)
    if len(active) > QUEUE_SIZE:
        raise ValueError(f"issue-status.json has more than {QUEUE_SIZE} open issues")

    history.extend(record for record in statuses if record["status"] != "open")
    statuses[:] = [record for record in statuses if record["status"] == "open"]

    for issue in issues:
        if len(active) == QUEUE_SIZE:
            break
        number = issue["number"]
        if number in tracked:
            continue
        statuses.append({
            "siteurl": site_from_title(issue["title"]),
            "issues": [number],
            "status": "open",
        })
        active.add(number)
    return [issue for issue in issues if issue["number"] in active]


def render_schedule(active):
    lines = [
        "# 対応予定",
        "",
        "対応を終えたら [issue-status.json](issue-status.json) の `status` を",
        "`fixed`（修正済み）または `skipped`（見送り）に変更してください。",
        "処理済みの案件は [issue-history.json](issue-history.json) に移ります。",
        "",
    ]
    if not active:
        lines.append("対応予定のIssueはありません。")
    for position, issue in enumerate(active, start=1):
        number = issue["number"]
        title = escape(" ".join(issue["title"].split()), quote=False)
        title = re.sub(r"([\\\[\]`*_~])", r"\\\1", title)
        url = f"https://github.com/{UPSTREAM}/issues/{number}"
        lines.append(f"{position}. [#{number} {title}]({url})")
    return "\n".join(lines) + "\n"


def read_list(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.name} must contain a JSON array")
    return data


def write_if_changed(path, text):
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    with TemporaryDirectory(dir=path.parent) as directory:
        temporary = Path(directory) / path.name
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="also import new upstream issues")
    args = parser.parse_args()

    issues_path = ROOT / "issues.json"
    statuses_path = ROOT / "issue-status.json"
    history_path = ROOT / "issue-history.json"
    try:
        issues = read_list(issues_path)
        statuses = read_list(statuses_path)
        history = read_list(history_path)
        if args.sync:
            numbers = {issue["number"] for issue in issues}
            issues.extend(issue for issue in fetch_issues() if issue["number"] not in numbers)
        active = fill_queue(issues, statuses, history)

        if args.sync:
            write_if_changed(issues_path, json.dumps(issues, ensure_ascii=False, indent=2) + "\n")
        write_if_changed(history_path, json.dumps(history, ensure_ascii=False, indent=2) + "\n")
        write_if_changed(statuses_path, json.dumps(statuses, ensure_ascii=False, indent=2) + "\n")
        write_if_changed(ROOT / "schedule.md", render_schedule(active))
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.exit(1, f"could not update issue queue: {error}\n")


if __name__ == "__main__":
    main()
