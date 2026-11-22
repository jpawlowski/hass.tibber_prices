# Contribution guidelines

Contributing to this project should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

## GitHub is used for everything

GitHub is used to host code, to track issues and feature requests, as well as accept pull requests.

Pull requests are the best way to propose changes to the codebase.

AI-assisted contributions are welcome, including substantially AI-generated work. Read the
[`AI_POLICY.md`](AI_POLICY.md) before contributing. Be accurate about what you reviewed and tested, and do not present
automated checks as human review or real-device testing.

1. Fork the repo and create your branch from `main`.
2. Run `script/setup/bootstrap` to install dependencies and git hooks.
3. If you've changed something, update the documentation.
4. Make sure your code passes all checks (using `script/check` for linting and type checking).
5. Test your contribution.
6. Review the resulting diff and describe its verification accurately.
7. Issue that pull request!

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using GitHub's [issues](../../issues)

GitHub issues are used to track public bugs.
Report a bug by [opening a new issue](../../issues/new/choose); it's that easy!

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People _love_ thorough bug reports. I'm not even kidding.

## Use a Consistent Coding Style

This project uses:

- [Ruff](https://github.com/astral-sh/ruff) for linting and formatting
- [Pyright](https://github.com/microsoft/pyright) for type checking

Run `script/check` to lint and type-check your code before submitting, or `script/lint` to auto-format and fix linting issues.

**Local validation:** Run `script/hassfest` to validate your integration against Home Assistant's quality standards using the official validation tools. This checks manifest.json, translations, services.yaml (service action definitions), and integration structure locally before pushing to GitHub.

## AI Agent Support

This project ships [agent skills](./.agents/skills/README.md) — task-triggered playbooks written against the open
[`SKILL.md`](https://agentskills.io/specification) standard. They work with GitHub Copilot, Claude Code, OpenAI Codex
CLI, OpenCode, Cursor, Gemini CLI, and any other tool that implements the standard. Codex, Copilot, OpenCode and
VS Code read `.agents/skills/` directly; Claude Code reaches the same files through the `.claude/skills/` symlink.

Skills cover adding entity platforms and service actions, config flow work, debugging the coordinator, translations,
testing, quality-scale review, deprecated APIs, breaking changes, planning, releases, and repository tooling. A
compatible agent loads the right one on its own; ask for it by name if it does not.

Alongside those, `AGENTS.md` provides always-on project context and `.agents/instructions/*.instructions.md` provide
per-file-type style rules for GitHub Copilot.

Two commands keep the skills honest:

```bash
script/skills-check                     # structure — runs in CI and as a pre-commit hook
```

**Companion skill for operating Home Assistant.** These skills cover _developing_ the integration. When you drive the
devcontainer's Home Assistant instance with an agent — creating test automations, dashboards, or helpers while trying
your integration out — the community
[`home-assistant-best-practices`](https://github.com/homeassistant-ai/skills) skill covers that side. It is not bundled
here and not required; install it into your own agent if you find it useful.

Please read [`AI_POLICY.md`](./AI_POLICY.md) before submitting AI-assisted contributions.

## Code Quality

This blueprint follows Home Assistant's [integration quality standards](https://contributors.home-assistant.io/core/quality-scale/) as best practices. The code includes:

- ✅ Comprehensive docstrings with links to official documentation
- ✅ Full type hints for better IDE support
- ✅ Config flow with reauthentication support
- ✅ Proper error handling and entity unavailability
- ✅ Coordinator pattern for efficient data fetching

**Don't worry!** You don't need to maintain all of this. The blueprint gives you a solid, well-documented starting point. Feel free to simplify or adapt anything to your needs - the goal is to help you get started quickly with good patterns, not to overwhelm you with requirements.

## Test your code modification

This project comes with a complete development environment in a container, easy to launch
if you use Visual Studio Code. With this container you will have a standalone
Home Assistant instance running and already configured with the included
[`configuration.yaml`](./config/configuration.yaml) file.

You can also run tests using `script/test` to ensure your changes don't break existing functionality.

## License

By contributing, you agree that your contributions will be licensed under its MIT License.
