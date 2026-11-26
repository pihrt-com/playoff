"""Validate published GitHub release names against their version tags."""
import json
import os
import re
import sys
import urllib.request


VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
LEGACY_TITLES = {
    "1.0.2": "Výchozí verze",
    "1.0.3": "Přidán časovač pro odpočet při hře",
    "1.0.4": "Fix updater",
    "1.0.5": "Oprava exportů, grafiky, odpočet atd",
    "1.0.6": "Opravy chyb, USB status",
}


def validate(release):
    tag = release.get("tag_name", "")
    name = release.get("name") or ""
    if not VERSION.fullmatch(tag) or (name != tag and LEGACY_TITLES.get(tag) != name):
        return f"Nesprávný název vydání: tag={tag!r}, název={name!r}; očekává se samotné číslo verze."
    return None


def main():
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ.get("GH_TOKEN", "")
    releases = []
    page = 1
    while True:
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repository}/releases?per_page=100&page={page}",
            headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
                     "User-Agent": "Playoff-release-title-check"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.load(response)
        releases.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        with open(event_path, encoding="utf-8") as event_file:
            event_release = json.load(event_file).get("release")
        if event_release:
            releases.append(event_release)
    errors = [error for release in releases if (error := validate(release))]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Zkontrolováno {len(releases)} vydání: názvy odpovídají verzím.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
