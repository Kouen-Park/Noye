import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const backend = resolve(frontend, "../backend");
if (process.platform !== "darwin") throw new Error("Desktop packaging currently supports macOS only.");
const python = process.env.NOYE_DESKTOP_PYTHON ?? resolve(backend, ".venv/bin/python");
if (!existsSync(python)) throw new Error("Install backend requirements and requirements-desktop.txt in backend/.venv first.");
const host = execFileSync("rustc", ["--print", "host-tuple"], { encoding: "utf8" }).trim();
const expected = process.arch === "arm64" ? "aarch64-apple-darwin" : "x86_64-apple-darwin";
if (host !== expected || (process.env.TAURI_ENV_TARGET_TRIPLE && process.env.TAURI_ENV_TARGET_TRIPLE !== host)) {
  throw new Error("Build the Python sidecar and Tauri app on the same native architecture; cross-compilation is not supported.");
}
const name = `noye-backend-${host}`;
execFileSync(python, ["-m", "PyInstaller", "--onefile", "--noconfirm", "--clean",
  "--name", name, "--distpath", resolve(frontend, "src-tauri/binaries"),
  "--workpath", resolve(backend, "build/desktop"), "--specpath", resolve(backend, "build"),
  "--paths", backend, "--collect-all", "pymupdf",
  "--exclude-module", "pytest", "--exclude-module", "app.tests", "--exclude-module", "IPython",
  resolve(backend, "desktop.py"),
], { cwd: backend, stdio: "inherit", env: {
  ...process.env, PYINSTALLER_CONFIG_DIR: resolve(backend, "build/pyinstaller-cache"),
} });
// No .env, database, user source, document or model files are added to the bundle.
console.log(`Built ${name}`);
