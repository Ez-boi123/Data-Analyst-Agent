import { existsSync } from "node:fs";
import { spawn, spawnSync } from "node:child_process";
import { join } from "node:path";

const localPython = join(process.cwd(), ".venv", "bin", "python");
const pythonCommand = process.env.PYTHON || (existsSync(localPython) ? localPython : "python3");
const args = ["-m", "uvicorn", "backend_app:app", "--host", "127.0.0.1", "--port", "8001"];

const preflight = spawnSync(pythonCommand, ["-c", "import sqlite3, uvicorn"], {
  cwd: process.cwd(),
  env: process.env,
  encoding: "utf8",
});

if (preflight.status !== 0) {
  const message = [preflight.stderr, preflight.stdout].filter(Boolean).join("\n").trim();
  console.error("[backend] Python 后端环境不可用。");
  if (message) {
    console.error(message);
  }
  console.error("");
  console.error("[backend] 推荐修复：");
  console.error("[backend]   npm run setup:backend");
  console.error("[backend] 如果自动修复仍然找不到可用 Python，请安装官方或 Homebrew Python 后执行：");
  console.error("[backend]   PYTHON=/path/to/python3 npm run setup:backend");
  console.error("[backend]   npm run dev:all");
  process.exit(preflight.status ?? 1);
}

const child = spawn(pythonCommand, args, {
  cwd: process.cwd(),
  env: process.env,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (code === 1) {
    console.error("");
    console.error("[backend] FastAPI 依赖可能还没有安装。推荐先执行：");
    console.error("[backend]   npm run setup:backend");
    console.error("[backend] 然后重新运行 npm run dev:all。");
  }
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
