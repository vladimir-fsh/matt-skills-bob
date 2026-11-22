# matt-skills-bob

[Matt Pocock's skills](https://github.com/mattpocock/skills) for Claude Code and Codex, regenerated from his repository every day, with one change: a playbook can run ten of the skills that upstream reserves for the user.

Upstream marks `to-questionnaire`, `handoff`, `grill-me`, `grill-with-docs`, `to-spec`, `to-tickets`, `wayfinder`, `implement`, `implement-spec` and `triage` with `disable-model-invocation: true`, so only you can start them. This port removes that flag from those ten and ends each description with "Use only when a playbook or the user names this skill." Everything else is copied byte for byte.

This is an unofficial port. The skills are Matt Pocock's work, under his MIT license.

## Install

Disable the original first, or every skill appears twice.

```bash
claude plugin disable mattpocock-skills@claude-plugins-official
claude plugin marketplace add vladimir-fsh/matt-skills-bob
claude plugin install matt@matt-skills-bob --scope user
```

```bash
codex plugin marketplace add vladimir-fsh/matt-skills-bob
codex plugin add matt@matt-skills-bob
```

Skills are named `matt:<skill>`, for example `matt:tdd`.

## Change what is unlocked

Edit `unlock` in [port.json](port.json) and regenerate:

```bash
python3 scripts/port.py
```

## How it stays current

A workflow runs `scripts/port.py --ref main` every day and opens a pull request when a skill changed upstream. The pull request is a draft marked "needs a person" when an `unlock` entry went stale: upstream renamed the skill, removed it, or unlocked it itself.
