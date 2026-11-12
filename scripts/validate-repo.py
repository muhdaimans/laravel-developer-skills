#!/usr/bin/env python3
"""Validate the laravel-developer-skills repository. Standard library only.

Usage:
    python3 scripts/validate-repo.py             structural checks
    python3 scripts/validate-repo.py --lint-php  also run `php -l` on PHP examples
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = [
    "laravel-best-practices",
    "laravel-project-architecture",
    "laravel-eloquent-optimization",
    "laravel-api-development",
    "laravel-authentication",
    "laravel-database-management",
    "laravel-queue-horizon",
    "laravel-testing",
    "laravel-debugging",
    "laravel-code-review",
    "laravel-security-audit",
    "laravel-deployment",
    "laravel-documentation",
]
ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
REQUIRED_SECTIONS = {
    "Inspect": r"^## Inspect",
    "Workflow": r"^## Workflow",
    "Version Notes": r"^## Version Notes",
    "Common Mistakes": r"^## Common Mistakes",
    "Verification": r"^## Verification",
}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)")
SKILL_REF_RE = re.compile(r"`(laravel-[a-z-]+)`")
INJECTION_RE = re.compile(r"(^|\s)!`", re.M)
PHP_BLOCK_RE = re.compile(r"^```php\n(.*?)^```", re.M | re.S)
NOT_SKILLS = {"laravel-boost"}

errors = []


def fail(message):
    errors.append(message)


def parse_frontmatter(path):
    """Parse the flat `key: value` frontmatter these skills use."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"{path}: must start with YAML frontmatter")
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        fail(f"{path}: frontmatter is not closed")
        return {}, text
    data = {}
    for number, line in enumerate(text[4:end].splitlines(), start=2):
        match = re.match(r"^([a-z-]+): (.+)$", line)
        if not match:
            fail(f"{path}:{number}: expected a single-line `key: value` entry")
            continue
        key, value = match.groups()
        if value[0] in "\"'":
            if value[-1] != value[0]:
                fail(f"{path}:{number}: unterminated quote")
            value = value[1:-1]
        elif ": " in value or value.endswith(":") or " #" in value:
            fail(f"{path}:{number}: value needs quoting for valid YAML")
        data[key] = value
    return data, text[end + 5:]


def check_manifests():
    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    if plugin.get("name") != ROOT.name and plugin.get("name") != "laravel-developer-skills":
        fail("plugin.json: unexpected name")
    if not re.match(r"^\d+\.\d+\.\d+$", plugin.get("version", "")):
        fail("plugin.json: version must be semver")
    entry = market["plugins"][0]
    if entry["name"] != plugin["name"]:
        fail("marketplace.json: entry name must equal plugin.json name")
    changelog = (ROOT / "CHANGELOG.md").read_text()
    if f"[{plugin['version']}]" not in changelog:
        fail(f"CHANGELOG.md: no entry for {plugin['version']}")
    for required in ("README.md", "LICENSE", "CHANGELOG.md"):
        if not (ROOT / required).is_file():
            fail(f"missing {required}")
    extras = {p.name for p in (ROOT / ".claude-plugin").iterdir()} - {"plugin.json", "marketplace.json"}
    if extras:
        fail(f".claude-plugin/ must only hold manifests, found {sorted(extras)}")


def check_skill(name):
    folder = ROOT / "skills" / name
    path = folder / "SKILL.md"
    if not path.is_file():
        fail(f"{name}: SKILL.md missing")
        return
    meta, body = parse_frontmatter(path)
    unknown = set(meta) - ALLOWED_KEYS
    if unknown:
        fail(f"{name}: non-portable frontmatter keys {sorted(unknown)}")
    if meta.get("name") != name or not NAME_RE.match(name) or len(name) > 64:
        fail(f"{name}: name must match the folder and the spec pattern")
    description = meta.get("description", "")
    if not 1 <= len(description) <= 1024:
        fail(f"{name}: description length {len(description)} outside 1-1024")
    if not description.startswith("Use when"):
        fail(f"{name}: description must start with 'Use when'")
    if len(meta.get("compatibility", "x")) > 500:
        fail(f"{name}: compatibility over 500 characters")

    lines = path.read_text(encoding="utf-8").count("\n")
    if lines >= 500:
        fail(f"{name}: SKILL.md has {lines} lines, limit is under 500")
    for label, pattern in REQUIRED_SECTIONS.items():
        if not re.search(pattern, body, re.M):
            fail(f"{name}: missing section '{label}'")
    if "```php" not in body and not any("```php" in p.read_text() for p in folder.rglob("*.md")):
        fail(f"{name}: no PHP example")

    linked = set()
    for md in folder.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        if INJECTION_RE.search(text):
            fail(f"{md}: contains shell-injection syntax that Claude Code would execute")
        for skill in SKILL_REF_RE.findall(text):
            if skill not in SKILLS and skill not in NOT_SKILLS:
                fail(f"{md}: unknown skill `{skill}`")
        for target in LINK_RE.findall(text):
            if re.match(r"^[a-z]+:", target):
                continue
            if ".." in target:
                fail(f"{md}: link escapes the skill folder: {target}")
            elif not (md.parent / target).is_file():
                fail(f"{md}: broken link: {target}")
            elif md == path:
                linked.add(target)
    for reference in (folder / "references").glob("*.md"):
        if f"references/{reference.name}" not in linked:
            fail(f"{name}: {reference.name} is not linked from SKILL.md")
    if len(list(folder.rglob("SKILL.md"))) != 1:
        fail(f"{name}: nested SKILL.md found")

    shared = (ROOT / "shared/version-matrix.md").read_bytes()
    copy = folder / "references/version-matrix.md"
    if not copy.is_file() or copy.read_bytes() != shared:
        fail(f"{name}: references/version-matrix.md differs from shared/ (run scripts/sync-shared.sh)")


def lint_php():
    php = shutil.which("php")
    if not php:
        fail("php not found, cannot lint")
        return 0
    count = 0
    with tempfile.TemporaryDirectory() as tmp:
        for md in sorted(list((ROOT / "skills").rglob("*.md")) + list((ROOT / "docs").rglob("*.md"))):
            for index, block in enumerate(PHP_BLOCK_RE.findall(md.read_text(encoding="utf-8"))):
                count += 1
                code = block if block.lstrip().startswith("<?php") else "<?php\n" + block
                if re.search(r"^(public|protected|private) ", block, re.M) and not re.search(
                    r"^(final |readonly |abstract )*(class|interface|trait|enum) ", block, re.M
                ):
                    imports = "".join(re.findall(r"^use [^\n]+\n", block, re.M))
                    members = re.sub(r"^use [^\n]+\n", "", block, flags=re.M)
                    code = "<?php\n" + imports + "class Example extends \\stdClass {\n" + members + "\n}\n"
                target = Path(tmp) / "snippet.php"
                target.write_text(code, encoding="utf-8")
                result = subprocess.run([php, "-l", str(target)], capture_output=True, text=True)
                if result.returncode != 0:
                    detail = (result.stdout + result.stderr).strip().splitlines()
                    fail(f"{md.relative_to(ROOT)} block {index + 1}: {detail[0] if detail else 'lint failed'}")
    return count


def main():
    check_manifests()
    folders = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}
    if folders != set(SKILLS):
        fail(f"skill folders differ from expected: {sorted(folders ^ set(SKILLS))}")
    for name in SKILLS:
        check_skill(name)
    linted = lint_php() if "--lint-php" in sys.argv else None

    for message in errors:
        print(f"ERROR {message}")
    summary = f"{len(SKILLS)} skills, {len(errors)} error(s)"
    if linted is not None:
        summary += f", {linted} PHP examples linted"
    print(summary)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
