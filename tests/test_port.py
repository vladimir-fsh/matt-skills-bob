import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import port

SUFFIX = " Use only when named."
LOCKED = '---\nname: to-spec\ndescription: "Write the spec."\ndisable-model-invocation: true\n---\n\nBody.\n'
OPEN = "---\nname: tdd\ndescription: Test first.\n---\n\nBody.\n"


def upstream(root, skills):
    """Lay out an upstream checkout holding these {manifest path: SKILL.md text} skills."""
    for listed, text in skills.items():
        (root / listed).mkdir(parents=True)
        (root / listed / "SKILL.md").write_text(text, encoding="utf-8")
    (root / ".claude-plugin").mkdir()
    manifest = {"version": "9.9.9", "skills": [f"./{listed}" for listed in skills]}
    (root / ".claude-plugin/plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    return root


def config(unlock):
    return {"manifest": ".claude-plugin/plugin.json", "unlock": unlock, "descriptionSuffix": SUFFIX}


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
        source = LOCKED + "disable-model-invocation: true\n"
        text, _ = port.unlock_frontmatter(source, SUFFIX)
        self.assertTrue(text.endswith("Body.\ndisable-model-invocation: true\n"))

    def test_a_skill_that_is_not_locked_is_a_problem(self):
        self.assertEqual(port.unlock_frontmatter(OPEN, SUFFIX), (None, "is not locked upstream; drop it from unlock"))

    def test_a_description_that_spans_lines_is_a_problem(self):
        for written in (">\n  Write\n  it.", "Write\n  it.", '"Write\n  it."'):
            source = f"---\ndescription: {written}\ndisable-model-invocation: true\n---\nBody.\n"
            self.assertEqual(port.unlock_frontmatter(source, SUFFIX), (None, "has a description that spans lines"))


class Build(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def test_listed_skills_land_flat_and_only_named_ones_are_unlocked(self):
        source = upstream(self.root, {"skills/engineering/to-spec": LOCKED, "skills/productivity/handoff": LOCKED, "skills/engineering/tdd": OPEN})
        (source / "skills/engineering/tdd/notes.md").write_text("Notes.\n", encoding="utf-8")
        (source / "skills/misc/unlisted").mkdir(parents=True)
        (source / "skills/misc/unlisted/SKILL.md").write_text(OPEN, encoding="utf-8")

        files, report, version = port.build(source, config(["to-spec"]))

        self.assertEqual(sorted(files), ["LICENSE", "skills/handoff/SKILL.md", "skills/tdd/SKILL.md", "skills/tdd/notes.md", "skills/to-spec/SKILL.md"])
        self.assertNotIn(b"disable-model-invocation", files["skills/to-spec/SKILL.md"][0])
        self.assertEqual(files["skills/handoff/SKILL.md"][0], LOCKED.encode())
        self.assertEqual(files["skills/tdd/SKILL.md"][0], OPEN.encode())
        self.assertEqual((report.unlocked, report.problems, version), (["to-spec"], [], "9.9.9"))

    def test_stale_unlock_entries_are_reported(self):
        source = upstream(self.root, {"skills/engineering/tdd": OPEN})

        files, report, _ = port.build(source, config(["tdd", "gone"]))

        self.assertEqual(files["skills/tdd/SKILL.md"][0], OPEN.encode())
        self.assertEqual(report.problems, [
            "tdd is not locked upstream; drop it from unlock",
            "gone is not a skill upstream ships; drop it from unlock",
        ])

    def test_two_listed_skills_with_one_name_stop_the_port(self):
        source = upstream(self.root, {"skills/a/tdd": OPEN, "skills/b/tdd": OPEN})
        with self.assertRaises(port.PortError):
            port.build(source, config([]))


class Compare(unittest.TestCase):
    def test_names_added_removed_and_changed_skills(self):
        before = {"LICENSE": (b"old", 0o644), "skills/a/SKILL.md": (b"1", 0o644), "skills/b/SKILL.md": (b"1", 0o644), "skills/b/x.md": (b"1", 0o644)}
        after = {"LICENSE": (b"new", 0o644), "skills/b/SKILL.md": (b"1", 0o644), "skills/c/SKILL.md": (b"1", 0o644)}
        report = port.Report()

        port.compare(before, after, report)

        self.assertEqual((report.added, report.removed, report.changed), (["c"], ["a"], ["b"]))


if __name__ == "__main__":
    unittest.main()
