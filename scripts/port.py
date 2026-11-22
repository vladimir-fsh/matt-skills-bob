#!/usr/bin/env python3
"""Generate plugin/ from mattpocock/skills.

plugin/skills and plugin/LICENSE are output, never edited by hand. Every skill
the upstream manifest lists is copied as it is, except for one line: whether an
agent may start it. The playbook sets port.json links to decide that. A skill
they name, or one such a skill calls, loses its disable-model-invocation flag
and gains a sentence at the end of its description. Every other skill carries
the flag, so only the user can start it. Codex reads the same decision from
each skill's agents/openai.yaml, which is rewritten to match.
"""

import argparse
from dataclasses import dataclass, field
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "port.json"
PLUGIN = ROOT / "plugin"
MANIFESTS = (PLUGIN / ".claude-plugin/plugin.json", PLUGIN / ".codex-plugin/plugin.json")
GENERATED = ("skills", "LICENSE")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?\r?\n)---\r?\n", re.DOTALL)
LOCK = re.compile(r"^disable-model-invocation:[ \t]*true[ \t]*\r?\n", re.MULTILINE)
DESCRIPTION = re.compile(r"^description:[ \t]*(\S.*?)[ \t]*$", re.MULTILINE)
# A suffix made of these characters needs no escaping in any YAML scalar style.
PLAIN_SUFFIX = re.compile(r"[A-Za-z0-9 ,.()-]*")
LOCK_LINE = "disable-model-invocation: true\n"
CODEX_AGENT_FILE = "agents/openai.yaml"
CODEX_IMPLICIT = re.compile(r"^([ \t]*allow_implicit_invocation:[ \t]*)(?:true|false)[ \t]*$", re.MULTILINE)
CODEX_RESERVED = "policy:\n  allow_implicit_invocation: false\n"
EXECUTABLE = 0o111


class PortError(Exception):
    pass


@dataclass
class Report:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unlocked: list[str] = field(default_factory=list)
    locked: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def git(*args, cwd=None, binary=False):
    output = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True).stdout
    return output if binary else output.decode().strip()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch(repository, ref, cache):
    if not (cache / ".git").exists():
        git("init", "--quiet", str(cache))
    git("fetch", "--quiet", "--depth=1", repository, ref, cwd=cache)
    return git("rev-parse", "FETCH_HEAD", cwd=cache)


def export(cache, commit, target):
    target.mkdir(parents=True)
    archive = git("archive", commit, cwd=cache, binary=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(target, filter="data")


def unlock_frontmatter(text, suffix):
    """Return the skill text a playbook can run, or the reason it cannot be made."""
    frontmatter = FRONTMATTER.match(text)
    header = LOCK.sub("", frontmatter.group(1))
    description = DESCRIPTION.search(header)
    if not description:
        return None, "has no one-line description"
    value = description.group(1)
    following = header[description.end():].lstrip("\r\n")
    quote = value[0] if value[0] in "\"'" else ""
    if quote and (len(value) < 2 or not value.endswith(quote)):
        return None, "has a description that spans lines"
    if not quote and (value[0] in "|>" or following[:1] in (" ", "\t")):
        return None, "has a description that spans lines"
    extended = value[:-1] + suffix + quote if quote else value + suffix
    header = header[:description.start(1)] + extended + header[description.end(1):]
    return text[:frontmatter.start(1)] + header + text[frontmatter.end(1):], None


def lock_frontmatter(text):
    """Return the skill text only the user can start, or the reason it cannot be made."""
    frontmatter = FRONTMATTER.match(text)
    if not frontmatter:
        return None, "has no frontmatter"
    return text[:frontmatter.end(1)] + LOCK_LINE + text[frontmatter.end(1):], None


def codex_policy(text, startable):
    """Return the Codex agent file that lets Codex start the skill unasked, or forbids it; or why it cannot be made."""
    if CODEX_IMPLICIT.search(text):
        return CODEX_IMPLICIT.sub(lambda found: found.group(1) + ("true" if startable else "false"), text), None
    if startable:
        return text, None
    if re.search(r"^policy:", text, re.MULTILINE):
        return None, "has a Codex policy block this port cannot extend"
    return text.rstrip("\n") + "\n" + CODEX_RESERVED, None


def is_locked(text):
    frontmatter = FRONTMATTER.match(text)
    return bool(frontmatter and LOCK.search(frontmatter.group(1)))


def called_through_skill_tool(name, text):
    return re.search(r'Skill tool[^.\n]{0,80}["`]' + re.escape(name) + r'["`]', text) is not None


def stored_mode(path):
    """Git keeps only the executable bit, so nothing else about a mode may count as a difference."""
    return 0o755 if path.stat().st_mode & EXECUTABLE else 0o644


def startable_skills(used, texts):
    """Return the skills an agent must be able to start: the ones playbooks name and the ones those call."""
    startable, queue = set(), sorted(used)
    while queue:
        name = queue.pop()
        if name in startable:
            continue
        startable.add(name)
        queue += [callee for callee in texts if callee != name and called_through_skill_tool(callee, texts[name])]
    return startable


def build(upstream, config, used):
    """Return the generated files as {path: (bytes, mode)}, the report, and the upstream version."""
    manifest = read_json(upstream / config["manifest"])
    files, report, texts = {}, Report(), {}
    for listed in manifest["skills"]:
        source = upstream / listed
        name = source.name
        if not (source / "SKILL.md").is_file():
            raise PortError(f"upstream lists {listed}, which has no SKILL.md")
        if name in texts:
            raise PortError(f"upstream lists two skills named {name}")
        for path in sorted(source.rglob("*")):
            if path.is_file() and not path.is_symlink():
                files[f"skills/{name}/{path.relative_to(source).as_posix()}"] = (path.read_bytes(), stored_mode(path))
        texts[name] = files[f"skills/{name}/SKILL.md"][0].decode("utf-8")
    report.problems += [f"a playbook names {name}, which upstream does not ship" for name in sorted(used - texts.keys())]
    startable = startable_skills(used & texts.keys(), texts)
    for name, text in sorted(texts.items()):
        if (name in startable) != is_locked(text):
            continue
        if name in startable:
            changed, problem = unlock_frontmatter(text, config["descriptionSuffix"])
            (report.problems if problem else report.unlocked).append(f"{name} {problem}" if problem else name)
        else:
            changed, problem = lock_frontmatter(text)
            (report.problems if problem else report.locked).append(f"{name} {problem}" if problem else name)
        if changed:
            files[f"skills/{name}/SKILL.md"] = (changed.encode("utf-8"), files[f"skills/{name}/SKILL.md"][1])
    for name in sorted(texts):
        agent_file = f"skills/{name}/{CODEX_AGENT_FILE}"
        if agent_file not in files:
            if name not in startable:
                report.problems.append(f"{name} has no {CODEX_AGENT_FILE}, so Codex may start it unasked")
            continue
        data, mode = files[agent_file]
        policy, problem = codex_policy(data.decode("utf-8"), name in startable)
        if problem:
            report.problems.append(f"{name} {problem}")
        else:
            files[agent_file] = (policy.encode("utf-8"), mode)
    license_file = upstream / "LICENSE"
    files["LICENSE"] = (license_file.read_bytes(), stored_mode(license_file))
    return files, report, manifest["version"]


def skills_named(value, prefix):
    """Collect every "skill" a set names for this plugin, wherever it sits in the set."""
    if isinstance(value, dict):
        own = value.get("skill")
        found = {own.removeprefix(prefix)} if isinstance(own, str) and own.startswith(prefix) else set()
        return found.union(*(skills_named(item, prefix) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(skills_named(item, prefix) for item in value))
    return set()


def used_by_playbooks(link):
    """Return this plugin's skills that the linked playbook sets name, from the sibling checkout when there is one."""
    local = ROOT / link["local"] if link.get("local") else None
    with tempfile.TemporaryDirectory() as scratch:
        if local and (local / link["sets"]).is_dir():
            directory = local / link["sets"]
        else:
            git("clone", "--quiet", "--depth=1", link["repository"], scratch)
            directory = Path(scratch) / link["sets"]
        return skills_named([read_json(path) for path in sorted(directory.glob("*.json"))], link["plugin"] + ":")


def current_files():
    files = {}
    for entry in GENERATED:
        path = PLUGIN / entry
        for item in [path] if path.is_file() else sorted(path.rglob("*")) if path.is_dir() else []:
            if item.is_file():
                files[item.relative_to(PLUGIN).as_posix()] = (item.read_bytes(), stored_mode(item))
    return files


def skill_names(files, differing_from=None):
    return {
        path.split("/")[1] for path in files
        if path.startswith("skills/") and (differing_from is None or files[path] != differing_from.get(path))
    }


def compare(before, after, report):
    old_skills, new_skills = skill_names(before), skill_names(after)
    report.added = sorted(new_skills - old_skills)
    report.removed = sorted(old_skills - new_skills)
    report.changed = sorted((skill_names(before, after) | skill_names(after, before)) & old_skills & new_skills)


def write(files):
    for entry in GENERATED:
        path = PLUGIN / entry
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    for relative_path, (data, mode) in files.items():
        path = PLUGIN / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)


def manifest_version():
    versions = {read_json(path)["version"] for path in MANIFESTS}
    if len(versions) != 1:
        raise PortError(f"manifest versions differ: {sorted(versions)}")
    return versions.pop()


def bump_version():
    major, minor, patch = map(int, manifest_version().split("."))
    version = f"{major}.{minor}.{patch + 1}"
    for path in MANIFESTS:
        manifest = read_json(path)
        manifest["version"] = version
        write_json(path, manifest)
    return version


def render(report, old, new, upstream_version, version):
    sections = [
        ("Needs a person", report.problems),
        ("Added skills", report.added),
        ("Removed skills", report.removed),
        ("Changed skills", report.changed),
        ("Opened for playbooks", report.unlocked),
        ("Reserved for the user", report.locked),
    ]
    moved = old[:7] if old == new else f"{old[:7]} -> {new[:7]}"
    lines = [f"mattpocock/skills {moved} (upstream {upstream_version}), plugin version {version}", ""]
    for title, items in sections:
        if items:
            lines += [f"{title} ({len(items)}):", *(f"- {item}" for item in items), ""]
    return "\n".join(lines)


def load_config():
    config = read_json(CONFIG)
    if not PLAIN_SUFFIX.fullmatch(config["descriptionSuffix"]):
        raise PortError("descriptionSuffix may hold only letters, digits, spaces and , . ( ) -")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", help="move the pin to this upstream ref, such as main")
    parser.add_argument("--repo", help="fetch from this repository instead of port.json's")
    parser.add_argument("--report", type=Path, help="also write the report to this file")
    parser.add_argument("--check", action="store_true", help="fail when plugin/ is not what the pin generates")
    args = parser.parse_args()

    config = load_config()
    repository = args.repo or config["repository"]
    old = config["commit"]
    with tempfile.TemporaryDirectory() as scratch:
        cache = Path(scratch) / "cache"
        cache.mkdir()
        new = fetch(repository, args.ref or old, cache)
        export(cache, new, Path(scratch) / "upstream")
        files, report, upstream_version = build(Path(scratch) / "upstream", config, used_by_playbooks(config["playbooks"]))

    before = current_files()
    if args.check:
        problems = report.problems + (["plugin/ differs from what port.json and the playbooks generate; run scripts/port.py"] if before != files else [])
        manifest_version()
        if problems:
            raise PortError("\n".join(problems))
        print("plugin/ is what port.json and the playbooks generate, and the manifests agree.")
        return

    compare(before, files, report)
    version = manifest_version()
    if before == files and new != old:
        print(f"No skill this plugin carries changed between {old[:7]} and {new[:7]}; pin left alone.")
        return
    if before != files:
        write(files)
        if before:
            version = bump_version()
        if new != old:
            config["commit"] = new
            write_json(CONFIG, config)
    text = render(report, old, new, upstream_version, version)
    print(text)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    if report.problems:
        sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except (PortError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", b"")
        sys.exit(f"port failed: {error}" + (f"\n{detail.decode()}" if detail else ""))
