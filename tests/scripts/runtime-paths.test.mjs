import { describe, expect, test } from "vitest";

import {
  getNpmCommand,
  getNpmSpawnSpec,
  getProcessTreeStopSpec,
  getPythonCandidates,
  getVenvPythonPath,
} from "../../scripts/runtime-paths.mjs";

describe("development runtime paths", () => {
  test("uses the Windows virtual-environment interpreter", () => {
    expect(getVenvPythonPath("C:\\workspace\\app", "win32")).toBe(
      "C:\\workspace\\app\\.venv\\Scripts\\python.exe",
    );
  });

  test("uses npm.cmd when spawning npm on Windows", () => {
    expect(getNpmCommand("win32")).toBe("npm.cmd");
  });

  test("checks the Windows Python launcher before python", () => {
    expect(getPythonCandidates("win32")).toEqual(["py", "python"]);
  });

  test("keeps an explicitly configured Python first", () => {
    expect(getPythonCandidates("win32", "C:\\Python312\\python.exe")).toEqual([
      "C:\\Python312\\python.exe",
      "py",
      "python",
    ]);
  });

  test("builds a shell-free npm invocation on Windows", () => {
    expect(getNpmSpawnSpec(["run", "dev"], "win32", "C:\\Windows\\System32\\cmd.exe")).toEqual({
      command: "C:\\Windows\\System32\\cmd.exe",
      args: ["/d", "/s", "/c", "npm.cmd run dev"],
    });
  });

  test("terminates the complete child-process tree on Windows", () => {
    expect(getProcessTreeStopSpec(1234, "win32")).toEqual({
      command: "taskkill",
      args: ["/pid", "1234", "/t", "/f"],
    });
  });
});
