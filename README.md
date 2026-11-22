# matt-skills-bob

[Matt Pocock's skills](https://github.com/mattpocock/skills) for Claude Code and Codex, regenerated from his repository every day, with one change: which skills an agent may start on its own.

Upstream marks some skills with `disable-model-invocation: true`, so only you can start them. [port.json](port.json) moves that line in two directions:

- `unlock` removes it from the skills a playbook has to run: `to-questionnaire`, `handoff`, `grill-me`, `grill-with-docs`, `to-spec`, `to-tickets`, `wayfinder`, `implement` and `implement-spec`. Each description then ends with "Use only when a playbook or the user names this skill."
- `lock` adds it to `writing-for-agents`, which no playbook uses and which would otherwise start on its own.

Everything else is copied byte for byte. An agent can start the skills the playbooks in [flows-bob](https://github.com/vladimir-fsh/flows-bob) name, plus `grilling`, which they call. The rest you start yourself with `/matt:<skill>`.

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

## Change what an agent may start

Edit `unlock` or `lock` in [port.json](port.json) and regenerate:

```bash
python3 scripts/port.py
```

## How it stays current

A workflow runs `scripts/port.py --ref main` every day and opens a pull request when a skill changed upstream. The pull request is a draft marked "needs a person" when an `unlock` or `lock` entry went stale (upstream renamed the skill, removed it, or changed its flag itself), or when a skill an agent can start began calling a locked one.
