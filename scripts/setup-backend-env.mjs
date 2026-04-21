import { existsSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join } from "node:path";

const venvDir = join(process.cwd(), ".venv");
const venvPython = join(venvDir, "bin", "python");

const candidates = [
  process.env.PYTHON,
  "/opt/homebrew/bin/python3",
  "/usr/local/bin/python3",
  "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
  "/usr/bin/python3",
  "python3",
  "python",
].filter(Boolean);

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

const python = findPython();

if (!python.command) {
  console.error("[setup:backend] 没找到可用的非 conda Python。");
  if (python.diagnostics.length) {
    console.error("[setup:backend] 候选 Python 诊断：");
    for (const item of python.diagnostics) {
      console.error(`[setup:backend] - ${item}`);
    }
  }
  console.error("[setup:backend] 请先安装官方 Python 或 Homebrew Python，然后运行：");
  console.error("[setup:backend]   PYTHON=/path/to/python3 npm run setup:backend");
  process.exit(1);
}

console.log(`[setup:backend] 使用 Python: ${python.resolved}`);

if (existsSync(venvDir)) {
  console.log("[setup:backend] 删除旧的 .venv");
  rmSync(venvDir, { recursive: true, force: true });
}

console.log("[setup:backend] 创建 .venv");
let result = spawnSync(python.command, ["-m", "venv", ".venv"], {
  cwd: process.cwd(),
  env: process.env,
  stdio: "inherit",
});
if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

console.log("[setup:backend] 安装 requirements.txt");
result = spawnSync(venvPython, ["-m", "pip", "install", "-r", "requirements.txt"], {
  cwd: process.cwd(),
  env: process.env,
  stdio: "inherit",
});
if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

console.log("[setup:backend] 后端 Python 环境已就绪。");
