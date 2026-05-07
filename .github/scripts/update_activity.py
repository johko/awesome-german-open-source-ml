#!/usr/bin/env python3
"""Update repository activity indicators in README.md.

Finds all <!-- REPO:owner/repo -->emoji<!-- /REPO --> markers and replaces
the emoji based on days since the last commit:
  🟢 < 30 days  |  🟡 30–180 days  |  🔴 > 180 days  |  ⬜ unavailable
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

THRESHOLDS = (30, 180)  # green→yellow, yellow→red (days)


def get_last_commit_date(repo: str, token: str | None) -> datetime | None:
    url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "awesome-german-ml-activity-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data:
                date_str = data[0]["commit"]["committer"]["date"]
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {repo}", file=sys.stderr)
    except Exception as e:
        print(f"  Error fetching {repo}: {e}", file=sys.stderr)
    return None


def days_to_emoji(last_commit: datetime | None) -> str:
    if last_commit is None:
        return "⬜"
    days = (datetime.now(timezone.utc) - last_commit).days
    if days < THRESHOLDS[0]:
        return "🟢"
    if days < THRESHOLDS[1]:
        return "🟡"
    return "🔴"


def update_readme(path: str, token: str | None) -> bool:
    with open(path) as f:
        content = f.read()

    pattern = re.compile(r"<!-- REPO:([\w./\-]+) -->.*?<!-- /REPO -->", re.DOTALL)
    changed = False

    def replacer(m: re.Match) -> str:
        nonlocal changed
        repo = m.group(1)
        last_commit = get_last_commit_date(repo, token)
        emoji = days_to_emoji(last_commit)
        days_ago = (datetime.now(timezone.utc) - last_commit).days if last_commit else "N/A"
        print(f"  {repo}: {emoji}  (last commit: {days_ago} days ago)")
        replacement = f"<!-- REPO:{repo} -->{emoji}<!-- /REPO -->"
        if replacement != m.group(0):
            changed = True
        return replacement

    new_content = pattern.sub(replacer, content)
    if changed:
        with open(path, "w") as f:
            f.write(new_content)
    return changed


if __name__ == "__main__":
    readme = sys.argv[1] if len(sys.argv) > 1 else "README.md"
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Warning: GITHUB_TOKEN not set — unauthenticated requests (60/hr limit)")
    print(f"Updating activity indicators in {readme}...")
    changed = update_readme(readme, token)
    print("README updated." if changed else "No changes needed.")
