#!/usr/bin/env python3
"""Update repository activity indicators in README.md.

Finds all <!-- ACCOUNT:owner -->emoji<!-- /ACCOUNT --> markers and replaces
the emoji based on days since the account's most recently pushed-to repo:
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


def get_account_last_push(owner: str, token: str | None) -> datetime | None:
    url = f"https://api.github.com/users/{owner}/repos?sort=pushed&per_page=1"
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
                pushed_at = data[0]["pushed_at"]
                return datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {owner}", file=sys.stderr)
    except Exception as e:
        print(f"  Error fetching {owner}: {e}", file=sys.stderr)
    return None


def days_to_emoji(last_push: datetime | None) -> str:
    if last_push is None:
        return "⬜"
    days = (datetime.now(timezone.utc) - last_push).days
    if days < THRESHOLDS[0]:
        return "🟢"
    if days < THRESHOLDS[1]:
        return "🟡"
    return "🔴"


def update_readme(path: str, token: str | None) -> bool:
    with open(path) as f:
        content = f.read()

    pattern = re.compile(r"<!-- ACCOUNT:([\w.\-]+) -->.*?<!-- /ACCOUNT -->", re.DOTALL)
    changed = False

    def replacer(m: re.Match) -> str:
        nonlocal changed
        owner = m.group(1)
        last_push = get_account_last_push(owner, token)
        emoji = days_to_emoji(last_push)
        days_ago = (datetime.now(timezone.utc) - last_push).days if last_push else "N/A"
        print(f"  {owner}: {emoji}  (last push: {days_ago} days ago)")
        replacement = f"<!-- ACCOUNT:{owner} -->{emoji}<!-- /ACCOUNT -->"
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
