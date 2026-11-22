// Runs from a disposable project with an explicit extension and no model calls.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    const project = ctx.cwd;
    const results: Record<string, boolean> = {};
    const outside = join(dirname(project), "outside.txt");
    const skill = join(dirname(project), "skills", "probe", "SKILL.md");
    results.project_write = can(() => writeFileSync(join(project, "written.txt"), "ok"));
    results.outside_invisible = !can(() => readFileSync(outside));
    results.skill_readable = can(() => readFileSync(skill));
    results.skill_read_only = !can(() => writeFileSync(skill, "must stay read-only"));
    results.host_auth_env_hidden = !process.env.OPENAI_API_KEY;
    results.no_new_privileges = /^NoNewPrivs:\s+1$/m.test(readFileSync("/proc/self/status", "utf8"));
    results.child_inherits_boundary = spawnSync("bash", [
      "-c", 'test ! -e "$1" && test -z "${OPENAI_API_KEY:-}"', "probe", outside,
    ]).status === 0;
    const catalog = await fetch("http://127.0.0.1:8080/models").then((response) => response.json());
    const allowed = ["coding-cyber-tiel-35b", "coding-kat-35b", "coding-lfm-24b",
      "coding-mellum-12b", "coding-ornith-9b", "coding-phai-256k"];
    results.only_coding_model = catalog.data
      ?.map((model: {id: string}) => model.id).sort().join() === allowed.join();
    results.other_model_denied = (await fetch("http://127.0.0.1:8080/props?model=research")).status === 403;
    results.router_management_denied = (await fetch("http://127.0.0.1:8080/models/unload", {
      method: "POST", body: JSON.stringify({model: "coding-cyber-tiel-35b"}),
    })).status === 403;
    results.default_mcp_denied = (await fetch("http://127.0.0.1:8080/mcp")).status === 403;
    writeFileSync(join(project, "sandbox-result.json"), JSON.stringify(results));
  });
}

function can(operation: () => unknown): boolean {
  try {
    operation();
    return true;
  } catch {
    return false;
  }
}
