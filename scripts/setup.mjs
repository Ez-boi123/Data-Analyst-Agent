import { spawnSync } from "node:child_process";

import { getNpmSpawnSpec } from "./runtime-paths.mjs";

const npmInstall = getNpmSpawnSpec(["install"]);

console.log("[setup] 安装前端依赖");
let result = spawnSync(npmInstall.command, npmInstall.args, {
  cwd: process.cwd(),
  env: process.env,
  stdio: "inherit",
});
if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

console.log("[setup] 安装后端依赖");
result = spawnSync(process.execPath, ["scripts/setup-backend-env.mjs"], {
  cwd: process.cwd(),
  env: process.env,
  stdio: "inherit",
});
process.exit(result.status ?? 1);
