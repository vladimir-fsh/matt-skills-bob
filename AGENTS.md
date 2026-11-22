# matt-skills-bob

A generated port of [mattpocock/skills](https://github.com/mattpocock/skills). `port.json` is the source; `plugin/skills/` and `plugin/LICENSE` are output.

- Change which skills a playbook can run by editing `unlock` in `port.json`, then run `python3 scripts/port.py`. Edits made inside `plugin/skills/` are overwritten on the next run, and CI fails on them.
- `python3 scripts/port.py --ref main` moves the pin to the newest upstream commit. `--check` verifies that `plugin/` is what the pin generates.
- Exit code 2 means the port was written and an `unlock` entry is stale: upstream renamed the skill, removed it, or unlocked it itself. Fix `unlock` and rerun.
- The script bumps the patch version in both manifests whenever the output changes. Bump minor or major by hand in both `plugin/.claude-plugin/plugin.json` and `plugin/.codex-plugin/plugin.json`.
- The plugin is named `matt`, so its skills are `matt:<skill>`. Disable `mattpocock-skills` wherever `matt` is enabled, or every skill appears twice.
