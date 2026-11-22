# matt-skills-bob

A generated port of [mattpocock/skills](https://github.com/mattpocock/skills). `port.json` is the source; `plugin/skills/` and `plugin/LICENSE` are output.

- Which skills an agent may start is not kept here. `port.json` links to the playbook sets in flows-bob (`playbooks`); a skill they name, or one such a skill calls, is opened, and every other skill is reserved for the user. Change it by changing a set, then run `python3 scripts/port.py`. Edits made inside `plugin/skills/` are overwritten on the next run, and CI fails on them.
- The decision is written twice per skill: `disable-model-invocation` in `SKILL.md` for Claude Code, `allow_implicit_invocation` in `agents/openai.yaml` for Codex.
- `python3 scripts/port.py --ref main` moves the pin to the newest upstream commit. `--check` verifies that `plugin/` is what the pin generates.
- The script bumps the patch version in both manifests whenever the output changes. Bump minor or major by hand in both `plugin/.claude-plugin/plugin.json` and `plugin/.codex-plugin/plugin.json`.
- The plugin is named `matt`, so its skills are `matt:<skill>`. Disable `mattpocock-skills` wherever `matt` is enabled, or every skill appears twice.
- Exit code 2 means the port was written and something needs a person: a playbook names a skill upstream does not ship, or a skill's frontmatter or Codex agent file took a shape the script cannot rewrite.
