# Working with AI coding agents

This repository is set up for several coding agents at once — GitHub Copilot (VS Code and CLI), Claude Code, Codex
CLI, and OpenCode. Their shared instructions live in `AGENTS.md`; what follows is the workflow around them and where
each agent's own configuration is kept.

## Human Review and Transparency

An agent prepares a draft; that does not establish that the integration is understood, tested, or ready to
publish. Before merging, review the diff and accurately record which checks, automated tests, and real-device tests were
performed. If review is partial or some behavior could not be tested, document that limitation instead of implying full
verification.

Before that, agents run a review pass of their own — simplify, run the gates again, then a review in a context that
did not write the change ([`blueprint-change-review`](../../.agents/skills/blueprint-change-review/SKILL.md)). It is
recorded as _Agent review_ in the pull request, and it does not replace yours.

Extensive AI assistance is acceptable for a community custom integration. See [`AI_POLICY.md`](../../AI_POLICY.md) for
the project's approach to AI use, transparency, and informed user choice. Do not use this workflow for autonomous
contributions to an Open Home Foundation repository, where the official OHF AI Policy applies.

## Reviewing an agent's changes

After an agent opens a draft pull request — the workflow below is written for the GitHub Copilot Coding Agent, which runs in GitHub Actions, but the review steps apply to any agent that hands you a branch:

1. **Open the PR branch in Codespaces**
   - Navigate to the pull request on GitHub
   - Click "Code" → "Create codespace on `branch-name`"
   - Codespace starts with all dependencies pre-installed (see [CODESPACES.md](CODESPACES.md))

2. **Start Home Assistant**
   - Run `./script/develop` in the terminal
   - Port 8123 forwards automatically (forwarded URL appears in notification)
   - Click the forwarded port URL to open HA in browser

3. **Test the integration**
   - Run the relevant automated tests using `script/test`
   - Add the integration via Home Assistant UI
   - Verify entities appear correctly
   - Test functionality with your actual device/service
   - Check logs: `config/home-assistant.log` or live in terminal

4. **Iterate if needed**
   - Comment on the PR with `@copilot` to request changes
   - Or make manual adjustments and commit to the PR branch
   - Stop Codespace when done to save free hours

> [!NOTE]
> Copilot Agent runs in GitHub Actions (ephemeral environment), so it cannot provide live web access to Home Assistant during development. Manual testing in Codespaces is required.

For detailed Codespaces usage, troubleshooting, and resource management, see [CODESPACES.md](CODESPACES.md).

## Tips

- Start simple - get a working prototype first
- Use `@copilot` in PR comments to iterate
- Review every iteration before merging and keep the PR's verification context accurate
- Break large changes into multiple PRs

## Agent Configuration Matrix (Vendor-Supported)

Use this matrix to keep security/approval behavior in real, vendor-supported
configuration files rather than in instruction prose.

| Agent                   | Policy and hook configuration                                                                                       | Shared hook implementation             | Notes                                                                                                           |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Copilot / VS Code agent | VS Code approval settings plus [.claude/settings.json](../../.claude/settings.json) for local lifecycle hooks       | [.agents/hooks/](../../.agents/hooks/) | VS Code currently ignores hook matchers, so every shared hook must safely ignore unrelated calls.               |
| Copilot CLI             | CLI defaults plus [.claude/settings.json](../../.claude/settings.json)                                              | [.agents/hooks/](../../.agents/hooks/) | The GitHub-hosted coding agent only reads `.github/hooks/`; this repository does not duplicate its local hooks. |
| Claude Code             | Managed policy plus project hooks in [.claude/settings.json](../../.claude/settings.json)                           | [.agents/hooks/](../../.agents/hooks/) | The project settings repeat the managed protections, so they hold outside the container too.                    |
| Codex CLI               | Sandbox defaults plus project hooks in [.codex/hooks.json](../../.codex/hooks.json)                                 | [.agents/hooks/](../../.agents/hooks/) | Codex asks the user to trust changed project hooks before executing them.                                       |
| OpenCode                | Managed policy, [opencode.json](../../opencode.json) and a plugin in [.opencode/plugins/](../../.opencode/plugins/) | [.agents/hooks/](../../.agents/hooks/) | Requires OpenCode 2; version 1 silently ignores both the plugin and the managed `permissions` list.             |
| Gemini                  | Not configured                                                                                                      | —                                      | Not part of the default devcontainer experience.                                                                |

### Editor extensions

The dev container installs every agent's command-line tool but none of their VS Code extensions.
[`.vscode/extensions.json`](../../.vscode/extensions.json) recommends all of them — `anthropic.claude-code`,
`GitHub.copilot-chat`, `openai.chatgpt` and `sst-dev.opencode`, which also installs itself when `opencode` runs in the
integrated terminal — so VS Code offers them when the repository is opened. Pick yours under _Workspace
Recommendations_ in the Extensions view rather than installing all at once. A project that settles on one agent
narrows the list as described in [`CUSTOMIZATION.md`](CUSTOMIZATION.md#recommended-and-required-extensions).

If you edit the instructions and skills under `.agents/` with VS Code's chat,
`ms-vscode.vscode-chat-customizations-evaluations` checks them the way VS Code loads them.

### Practical rule

- Put policy and defaults in vendor config files first.
- Protect a path in [managed-settings.json](../../.devcontainer/claude-code/managed-settings.json), the project
  [.claude/settings.json](../../.claude/settings.json), both OpenCode configs ([managed](../../.devcontainer/opencode/opencode.json)
  and [project](../../opencode.json)) and both copies of `chat.tools.edits.autoApprove` together. The managed files
  apply only inside the dev container; the project files carry the same protection to a local or cloud session. `script/skills-check` fails when they disagree and prints the missing entry in each tool's syntax.
- Keep markdown instruction files for workflow guidance only.

Claude Code, Codex, OpenCode, VS Code, and Copilot CLI all support lifecycle hooks. The configuration paths differ, but the
commands here converge on `.agents/hooks/` so security behavior is implemented and tested once. Claude slash commands
under `.claude/commands/` remain Claude-specific; the corresponding reusable workflow is the vendor-neutral
[`ha-issue-triage`](../../.agents/skills/ha-issue-triage/SKILL.md), with `.github/prompts/` providing Copilot dispatch.
These agent lifecycle hooks are unrelated to `script/hooks/`, which customizes the repository's validation scripts.

### Session start

Every agent runs [`session-start.sh`](../../.agents/hooks/session-start.sh) when a session begins, so a checkout works
without the dev container. Nothing slow happens in front of the session: in a Claude Code cloud session, which starts
on a fresh machine each time, it runs `script/setup/bootstrap` in the background, which installs mise from its GitHub
release (checksum-verified); everywhere else it checks the tools [`mise.toml`](../../mise.toml) pins in the background
and reports a checkout that still needs `script/setup/bootstrap`. Both scripts record their state, with the PID, in
`.local/<script>.status`, so a run in progress is waited for and a dead one is not mistaken for it. Every later command
of the session applies `mise env` — the pinned tools and the Home Assistant venv; OpenCode has no session-start event,
so its plugin runs the script when it loads and applies `mise env` to every shell. Codex cloud builds its environment from the repository; `AGENTS.md` names the install command it should
record. After pulling this change, Codex asks once to trust the changed `.codex/hooks.json`.

### Previewing Home Assistant

[`.claude/launch.json`](../../.claude/launch.json) tells the Claude desktop app how to start Home Assistant
(`script/develop`, port 8123) for its browser pane, so Claude can look at the UI it is changing. That is a desktop
feature: a Claude Code cloud session documents no preview of a server running in its machine, and Codex, OpenCode
and Copilot have no counterpart. There, `script/ha` is how an agent inspects the running instance.

### Push gate

Every push, by a person or an agent, goes through [`script/push-gate`](../../script/push-gate), which prek installs
as git's pre-push hook. It accepts only the checked-out HEAD of a clean worktree and runs `script/lint-check` and
`script/type-check` on it. Git hands the hook only the first ref of a push, so the shared agent hook adds what the
gate cannot see. It reads the git commands a shell call actually runs, including those inside `bash -c`, `$(…)` and
subshells, and blocks `--no-verify` and `core.hooksPath`, pushes of several refs, tags or deletions, and pushes from a
repository whose `.pre-commit-config.yaml` does not install the hook. Commit messages, here-documents and searches
that merely mention such a push pass. A person who needs any of that pushes with `--no-verify` deliberately. After pulling this change, run `prek install` once (`script/setup/bootstrap` does
it) so the hook exists in your clone.

### Work reaches `main` through a pull request

The `main` ruleset takes every change through a pull request, squash-merged by default — what it requires and how to
relax it is in [REPOSITORY_SETUP.md](REPOSITORY_SETUP.md). That suits agent work: a branch's working commits never reach `main`,
each change can be reverted as a whole, and release-please reads exactly one commit per change. Open a pull request as
a draft while an agent still pushes to it; [`ha-issue-triage`](../../.agents/skills/ha-issue-triage/SKILL.md) walks a
backlog the same way, one branch and pull request per issue.

## Resources

- [GitHub Copilot Best Practices](https://docs.github.com/en/copilot/tutorials/coding-agent/get-the-best-results)
- [GitHub Copilot hooks reference](https://docs.github.com/en/copilot/reference/hooks-reference)
- [VS Code hooks reference](https://code.visualstudio.com/docs/agents/reference/hooks-reference)
- [Codex hooks](https://learn.chatgpt.com/docs/hooks)
- [OpenCode plugins](https://opencode.ai/v2/docs/build/plugins/server) and
  [permissions](https://opencode.ai/v2/docs/permissions/)
- `AGENTS.md` - Read automatically by Copilot; the single always-loaded instruction file for every agent
- [`.agents/skills/`](../../.agents/skills/README.md) - Task-triggered agent skills. Copilot reads this location
  directly; Claude Code reaches the same files through the `.claude/skills/` symlink
