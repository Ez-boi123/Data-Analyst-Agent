import path from "node:path";

export function getVenvPythonPath(cwd = process.cwd(), platform = process.platform) {
  const pathApi = platform === "win32" ? path.win32 : path.posix;
  const executable = platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"];
  return pathApi.join(cwd, ".venv", ...executable);
}

export function getNpmCommand(platform = process.platform) {
  return platform === "win32" ? "npm.cmd" : "npm";
}

export function getPythonCandidates(platform = process.platform, configuredPython = process.env.PYTHON) {
  const defaults = platform === "win32"
    ? ["py", "python"]
    : [
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
        "/usr/bin/python3",
        "python3",
        "python",
      ];
  return [...new Set([configuredPython, ...defaults].filter(Boolean))];
}

export function getNpmSpawnSpec(args, platform = process.platform, commandShell = process.env.ComSpec) {
  if (platform === "win32") {
    return {
      command: commandShell || "cmd.exe",
      args: ["/d", "/s", "/c", [getNpmCommand(platform), ...args].join(" ")],
    };
  }
  return { command: getNpmCommand(platform), args };
}

export function getProcessTreeStopSpec(pid, platform = process.platform) {
  if (platform !== "win32") {
    return null;
  }
  return {
    command: "taskkill",
    args: ["/pid", String(pid), "/t", "/f"],
  };
}
