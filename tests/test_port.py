import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import port

SUFFIX = " Use only when named."
CONFIG = {"manifest": ".claude-plugin/plugin.json", "descriptionSuffix": SUFFIX}
LOCKED = '---\nname: to-spec\ndescription: "Write the spec."\ndisable-model-invocation: true\n---\n\nBody.\n'
OPEN = "---\nname: tdd\ndescription: Test first.\n---\n\nBody.\n"
CODEX_OPEN = 'interface:\n  display_name: "Skill"\n'
CODEX_RESERVED = CODEX_OPEN + "policy:\n  allow_implicit_invocation: false\n"


def upstream(root, skills):
    """Lay out an upstream checkout holding these {manifest path: SKILL.md text} skills, each with its Codex agent file."""
    for listed, text in skills.items():
        (root / listed / "agents").mkdir(parents=True)
        (root / listed / "SKILL.md").write_text(text, encoding="utf-8")
        reserved = "disable-model-invocation: true" in text
        (root / listed / "agents/openai.yaml").write_text(CODEX_RESERVED if reserved else CODEX_OPEN, encoding="utf-8")
    (root / ".claude-plugin").mkdir()
    manifest = {"version": "9.9.9", "skills": [f"./{listed}" for listed in skills]}
    (root / ".claude-plugin/plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    return root


def calling(text, callee):
    return text.replace("Body.", f'Call the Skill tool with "{callee}" once done.')


class UnlockFrontmatter(unittest.TestCase):
    def test_double_quoted_description_gains_the_suffix_inside_the_quotes(self):
        text, problem = port.unlock_frontmatter(LOCKED, SUFFIX)
        self.assertIsNone(problem)
        self.assertEqual(text, '---\nname: to-spec\ndescription: "Write the spec. Use only when named."\n---\n\nBody.\n')

    def test_plain_and_single_quoted_descriptions_gain_the_suffix(self):
        for written, expected in (("Write it.", "Write it. Use only when named."), ("'Write it.'", "'Write it. Use only when named.'")):
            source = f"---\ndescription: {written}\ndisable-model-invocation: true\n---\nBody.\n"
            text, problem = port.unlock_frontmatter(source, SUFFIX)
            self.assertIsNone(problem)
            self.assertEqual(text, f"---\ndescription: {expected}\n---\nBody.\n")

    def test_a_flag_in_the_body_is_left_alone(self):
        text, _ = port.unlock_frontmatter(LOCKED + "disable-model-invocation: true\n", SUFFIX)
        self.assertTrue(text.endswith("Body.\ndisable-model-invocation: true\n"))

    def test_a_description_that_spans_lines_is_a_problem(self):
        for written in (">\n  Write\n  it.", "Write\n  it.", '"Write\n  it."'):
            source = f"---\ndescription: {written}\ndisable-model-invocation: true\n---\nBody.\n"
            self.assertEqual(port.unlock_frontmatter(source, SUFFIX), (None, "has a description that spans lines"))


class LockFrontmatter(unittest.TestCase):
    def test_the_flag_lands_at_the_end_of_the_frontmatter(self):
        text, problem = port.lock_frontmatter(OPEN)
        self.assertIsNone(problem)
        self.assertEqual(text, "---\nname: tdd\ndescription: Test first.\ndisable-model-invocation: true\n---\n\nBody.\n")


class CodexPolicy(unittest.TestCase):
    def test_a_startable_skill_may_be_started_unasked(self):
        self.assertEqual(port.codex_policy(CODEX_RESERVED, True), (CODEX_OPEN + "policy:\n  allow_implicit_invocation: true\n", None))
        self.assertEqual(port.codex_policy(CODEX_OPEN, True), (CODEX_OPEN, None))

    def test_a_reserved_skill_may_not(self):
        self.assertEqual(port.codex_policy(CODEX_OPEN, False), (CODEX_RESERVED, None))
        self.assertEqual(port.codex_policy(CODEX_RESERVED, False), (CODEX_RESERVED, None))

    def test_a_policy_block_without_the_key_is_a_problem(self):
        self.assertEqual(port.codex_policy("policy:\n  other: 1\n", False), (None, "has a Codex policy block this port cannot extend"))


class Build(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def state(self, files, name):
        """Whether Claude Code and Codex may each start the skill on their own."""
        claude = b"disable-model-invocation: true" not in files[f"skills/{name}/SKILL.md"][0]
        codex = b"allow_implicit_invocation: false" not in files[f"skills/{name}/agents/openai.yaml"][0]
        return claude, codex

    def test_skills_land_flat_and_only_what_playbooks_name_can_be_started(self):
        source = upstream(self.root, {
            "skills/engineering/to-spec": LOCKED, "skills/productivity/handoff": LOCKED,
            "skills/engineering/tdd": OPEN, "skills/engineering/retro": OPEN,
        })
        (source / "skills/engineering/tdd/notes.md").write_text("Notes.\n", encoding="utf-8")
        (source / "skills/misc/unlisted").mkdir(parents=True)
        (source / "skills/misc/unlisted/SKILL.md").write_text(OPEN, encoding="utf-8")

        files, report, version = port.build(source, CONFIG, {"to-spec", "tdd"})

        self.assertEqual(sorted(path for path in files if not path.endswith("openai.yaml")), [
            "LICENSE", "skills/handoff/SKILL.md", "skills/retro/SKILL.md", "skills/tdd/SKILL.md", "skills/tdd/notes.md", "skills/to-spec/SKILL.md",
        ])
        self.assertEqual({name: self.state(files, name) for name in ("to-spec", "tdd", "handoff", "retro")}, {
            "to-spec": (True, True), "tdd": (True, True), "handoff": (False, False), "retro": (False, False),
        })
        self.assertIn(b"Use only when named.", files["skills/to-spec/SKILL.md"][0])
        self.assertEqual(files["skills/tdd/SKILL.md"][0], OPEN.encode())
        self.assertEqual(files["skills/handoff/SKILL.md"][0], LOCKED.encode())
        self.assertEqual((report.unlocked, report.locked, report.problems, version), (["to-spec"], ["retro"], [], "9.9.9"))

    def test_a_skill_that_a_named_skill_calls_can_be_started_too(self):
        source = upstream(self.root, {
            "skills/a/implement": calling(LOCKED, "tdd"), "skills/a/tdd": calling(OPEN, "design"),
            "skills/a/design": LOCKED, "skills/a/retro": calling(LOCKED, "notes"), "skills/a/notes": OPEN,
        })

        files, report, _ = port.build(source, CONFIG, {"implement"})

        self.assertEqual({name: self.state(files, name)[0] for name in ("implement", "tdd", "design", "retro", "notes")}, {
            "implement": True, "tdd": True, "design": True, "retro": False, "notes": False,
        })
        self.assertEqual((report.unlocked, report.locked), (["design", "implement"], ["notes"]))

    def test_a_named_skill_that_upstream_lacks_is_reported(self):
        source = upstream(self.root, {"skills/a/tdd": OPEN})
        _, report, _ = port.build(source, CONFIG, {"tdd", "gone"})
        self.assertEqual(report.problems, ["a playbook names gone, which upstream does not ship"])

    def test_two_listed_skills_with_one_name_stop_the_port(self):
        source = upstream(self.root, {"skills/a/tdd": OPEN, "skills/b/tdd": OPEN})
        with self.assertRaises(port.PortError):
            port.build(source, CONFIG, set())


class SkillsNamed(unittest.TestCase):
    def test_collects_this_plugins_skills_from_any_depth(self):
        sets = [
            {"stages": [{"routes": [{"steps": [{"skill": "matt:tdd"}, {"skill": "pstack:arena"}, {"note": "Go"}]}]}]},
            {"steps": [{"skill": "matt:pr"}, {"skill": "matt:tdd"}]},
        ]
        self.assertEqual(port.skills_named(sets, "matt:"), {"tdd", "pr"})


class Compare(unittest.TestCase):
    def test_names_added_removed_and_changed_skills(self):
        before = {"LICENSE": (b"old", 0o644), "skills/a/SKILL.md": (b"1", 0o644), "skills/b/SKILL.md": (b"1", 0o644), "skills/b/x.md": (b"1", 0o644)}
        after = {"LICENSE": (b"new", 0o644), "skills/b/SKILL.md": (b"1", 0o644), "skills/c/SKILL.md": (b"1", 0o644)}
        report = port.Report()

        port.compare(before, after, report)

        self.assertEqual((report.added, report.removed, report.changed), (["c"], ["a"], ["b"]))


if __name__ == "__main__":
    unittest.main()
