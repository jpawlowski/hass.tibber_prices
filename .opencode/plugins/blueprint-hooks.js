/**
 * Runs the shared .agents/hooks/ scripts for OpenCode 2, as .claude/settings.json and .codex/hooks.json do for their
 * agents. Each script receives the Claude-shaped payload it is written against.
 */

import { execFile } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const EDIT_TOOLS = new Set(["edit", "write", "patch"]);

const LOCAL_BIN = join(homedir(), ".local", "bin");

// What `mise env` resolves for a directory — the pinned tools and the Home Assistant venv — or nothing without mise.
const miseEnv = (cwd, env) =>
  new Promise((resolve) => {
    const path = [LOCAL_BIN, env.PATH ?? process.env.PATH ?? ""].join(":");
    const options = { cwd, env: { ...process.env, ...env, PATH: path, MISE_HIDE_UPDATE_WARNING: "1" }, timeout: 5000 };
    execFile("mise", ["env", "--json"], options, (error, stdout) => {
      try {
        resolve(error ? {} : JSON.parse(stdout));
      } catch {
        resolve({});
      }
    });
  });

const runHook = (root, script, payload) =>
  new Promise((resolve) => {
    const child = execFile("bash", [`${root}/${script}`], { cwd: root }, (error, stdout, stderr) => {
      resolve({ stdout, stderr: stderr || error?.message || "", exitCode: error ? 1 : 0 });
    });
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify(payload));
  });

export default {
  id: "agent-hooks",
  async setup(ctx) {
    const root = ctx.location.project.directory;

    // OpenCode has no session-start hook and no CLAUDE_ENV_FILE: the setup runs when the plugin loads, and every
    // shell gets what `mise env` resolves instead.
    runHook(root, ".agents/hooks/session-start.sh", { hook_event_name: "SessionStart", cwd: ctx.location.directory });

    await ctx.shell.hook("create.before", async (event) => {
      const resolved = await miseEnv(event.cwd ?? root, event.env ?? {});
      if (Object.keys(resolved).length > 0) event.env = { ...event.env, ...resolved };
    });

    await ctx.tool.hook("execute.before", async (event) => {
      if (event.tool !== "shell") return;
      const { stderr, exitCode } = await runHook(root, ".agents/hooks/pre-push-check.sh", { tool_input: event.input });
      if (exitCode !== 0) {
        throw new Error(stderr.trim() || "the push command was blocked by .agents/hooks/pre-push-check.sh");
      }
    });

    await ctx.tool.hook("execute.after", async (event) => {
      if (event.status !== "completed" || !EDIT_TOOLS.has(event.tool)) return;
      const { stdout } = await runHook(root, ".agents/hooks/remind-dependency-sync.sh", { tool_input: event.input });
      let additionalContext;
      try {
        additionalContext = JSON.parse(stdout)?.hookSpecificOutput?.additionalContext;
      } catch {
        return;
      }
      if (!additionalContext) return;
      const content = event.result.content;
      event.result = {
        ...event.result,
        content:
          typeof content === "string"
            ? `${content}\n\n${additionalContext}`
            : [...(content ?? []), { type: "text", text: additionalContext }],
      };
    });
  },
};
