import { spawn, spawnSync } from "node:child_process";

import { getNpmSpawnSpec, getProcessTreeStopSpec } from "./runtime-paths.mjs";

const frontendCommand = getNpmSpawnSpec(["run", "dev"]);

const commands = [
  {
    name: "backend",
    command: "node",
    args: ["scripts/dev-backend.mjs"],
  },
  {
    name: "frontend",
    command: frontendCommand.command,
    args: frontendCommand.args,
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
      const stopSpec = getProcessTreeStopSpec(child.pid);
      if (stopSpec) {
        spawnSync(stopSpec.command, stopSpec.args, { stdio: "ignore" });
      } else {
        child.kill(signal);
      }
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
