import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join } from "node:path";

import { getPythonCandidates, getVenvPythonPath } from "./runtime-paths.mjs";

const venvDir = join(process.cwd(), ".venv");
const venvPython = getVenvPythonPath();
const candidates = getPythonCandidates();

function run(command, args, options = {}) {
  return spawnSync(command, args, {
    cwd: process.cwd(),
    env: process.env,
    encoding: "utf8",
    ...options,
  });
}

function isUsablePython(command) {
  const result = run(command, ["-c", "import sqlite3, venv"]);
  return {
    ok: result.status === 0,
    error: [result.stderr, result.stdout].filter(Boolean).join("\n").trim(),
  };
}

function findPython() {
  const seen = new Set();
  const diagnostics = [];
  for (const candidate of candidates) {
    if (seen.has(candidate)) {
      continue;
    }
    seen.add(candidate);

    const result = run(candidate, ["-c", "import sys; print(sys.executable)"]);
    if (result.status !== 0) {
      const error = [result.error?.message, result.stderr, result.stdout].filter(Boolean).join("\n").trim();
      diagnostics.push(`${candidate}: 无法执行${error ? `\n${error}` : ""}`);
      continue;
    }
    const resolved = result.stdout.trim() || candidate;
    if (resolved.includes("/opt/anaconda3/")) {
      diagnostics.push(`${candidate}: 跳过 conda Python (${resolved})`);
      continue;
    }
    const usable = isUsablePython(candidate);
    if (usable.ok) {
      return { command: candidate, resolved, diagnostics };
    }
    diagnostics.push(`${candidate}: sqlite3/venv 预检失败${usable.error ? `\n${usable.error}` : ""}`);
  }
  return { command: null, resolved: "", diagnostics };
}

if (!existsSync(venvPython)) {
  const python = findPython();

  if (!python.command) {
    console.error("[setup:backend] 没找到可用的 Python。");
    if (python.diagnostics.length) {
      console.error("[setup:backend] 候选 Python 诊断：");
      for (const item of python.diagnostics) {
        console.error(`[setup:backend] - ${item}`);
      }
    }
    console.error("[setup:backend] 请先安装 Python 3，然后重新运行 npm run setup。");
    process.exit(1);
  }

  console.log(`[setup:backend] 使用 Python: ${python.resolved}`);
  console.log("[setup:backend] 创建 .venv");
  const createResult = spawnSync(python.command, ["-m", "venv", venvDir], {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit",
  });
  if (createResult.status !== 0) {
    process.exit(createResult.status ?? 1);
  }
} else {
  console.log(`[setup:backend] 复用现有虚拟环境: ${venvPython}`);
}

console.log("[setup:backend] 安装 requirements.txt");
const result = spawnSync(venvPython, ["-m", "pip", "install", "-r", "requirements.txt"], {
  cwd: process.cwd(),
  env: process.env,
  stdio: "inherit",
});
if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

console.log("[setup:backend] 后端 Python 环境已就绪。");
