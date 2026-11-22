# matt-skills-bob

A generated port of [mattpocock/skills](https://github.com/mattpocock/skills). `port.json` is the source; `plugin/skills/` and `plugin/LICENSE` are output.

- Change which skills an agent may start by editing `port.json`, then run `python3 scripts/port.py`: `unlock` opens a skill upstream reserves for the user, `lock` reserves one upstream leaves open. Keep open only what the playbooks in flows-bob name, and what those skills call. Edits made inside `plugin/skills/` are overwritten on the next run, and CI fails on them.
- `python3 scripts/port.py --ref main` moves the pin to the newest upstream commit. `--check` verifies that `plugin/` is what the pin generates.
- Exit code 2 means the port was written and `port.json` needs a fix: an `unlock` or `lock` entry is stale (upstream renamed the skill, removed it, or changed its flag itself), or a skill an agent can start calls a locked one. Fix the lists and rerun.
- The script bumps the patch version in both manifests whenever the output changes. Bump minor or major by hand in both `plugin/.claude-plugin/plugin.json` and `plugin/.codex-plugin/plugin.json`.
- The plugin is named `matt`, so its skills are `matt:<skill>`. Disable `mattpocock-skills` wherever `matt` is enabled, or every skill appears twice.
