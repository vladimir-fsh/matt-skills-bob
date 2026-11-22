# matt-skills-bob

[Matt Pocock's skills](https://github.com/mattpocock/skills) for Claude Code and Codex, regenerated from his repository every day, with one change: which skills an agent may start on its own.

The playbooks in [flows-bob](https://github.com/vladimir-fsh/flows-bob) decide that. A skill one of them names, and any skill such a skill calls, can be started by an agent. Every other skill is reserved for you: start it with `/matt:<skill>` in Claude Code or `$<skill>` in Codex.

Upstream reserves a skill with `disable-model-invocation: true` in its `SKILL.md` for Claude Code, and with `allow_implicit_invocation: false` in its `agents/openai.yaml` for Codex. The port sets both for every skill to match the playbooks, and ends the description of each skill it opens with "Use only when a playbook or the user names this skill." Everything else is copied byte for byte.

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

Add the skill to a playbook in flows-bob, or take it out. Saving a set in its admin page regenerates this port. To do it by hand:

```bash
python3 scripts/port.py
```

## How it stays current

A workflow runs `scripts/port.py --ref main` every day and opens a pull request when a skill changed upstream or the playbooks name different skills. The pull request is a draft marked "needs a person" when a playbook names a skill upstream no longer ships, or a skill's files took a shape the port cannot rewrite.
