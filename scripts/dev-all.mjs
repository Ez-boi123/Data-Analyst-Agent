import { spawn } from "node:child_process";

const commands = [
  {
    name: "backend",
    command: "python",
    args: ["-m", "uvicorn", "backend_app:app", "--host", "127.0.0.1", "--port", "8001"],
  },
  {
    name: "frontend",
    command: "npm",
    args: ["run", "dev"],
  },
];

const children = [];
let shuttingDown = false;

function prefixOutput(name, data, stream) {
  const lines = data.toString().split(/\r?\n/);
  for (const line of lines) {
    if (line.trim()) {
      stream.write(`[${name}] ${line}\n`);
    }
  }
}

function stopAll(signal = "SIGTERM") {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) {
      child.kill(signal);
    }
  }
}

for (const item of commands) {
  const child = spawn(item.command, item.args, {
    cwd: process.cwd(),
    env: process.env,
    stdio: ["inherit", "pipe", "pipe"],
  });

  children.push(child);

  child.stdout.on("data", (data) => prefixOutput(item.name, data, process.stdout));
  child.stderr.on("data", (data) => prefixOutput(item.name, data, process.stderr));

  child.on("exit", (code, signal) => {
    if (!shuttingDown) {
      const reason = signal ? `signal ${signal}` : `code ${code}`;
      console.error(`[dev:all] ${item.name} exited with ${reason}. Stopping remaining processes.`);
      stopAll();
      process.exit(code ?? 1);
    }
  });
}

process.on("SIGINT", () => {
  stopAll("SIGINT");
  process.exit(130);
});

process.on("SIGTERM", () => {
  stopAll("SIGTERM");
  process.exit(143);
});
