// Manual Electron packager — no SSL, uses cached Electron binary.
const fs = require("fs");
const path = require("path");
const AdmZip = require("adm-zip");

const RELEASE = path.resolve("release/win-unpacked");
const CACHE = path.resolve(process.env.LOCALAPPDATA, "electron/Cache");

// 1. Find newest cached Electron zip
let bestZip = null, bestVer = 0;
for (const dir of fs.readdirSync(CACHE)) {
  const full = path.join(CACHE, dir);
  if (!fs.statSync(full).isDirectory()) continue;
  for (const f of fs.readdirSync(full)) {
    const m = f.match(/^electron-v(\d+)\.\d+\.\d+-win32-x64\.zip$/);
    if (m && parseInt(m[1]) > bestVer) {
      bestVer = parseInt(m[1]); bestZip = path.join(full, f);
    }
  }
}
if (!bestZip) { console.error("No cached Electron found."); process.exit(1); }
console.log("Using:", bestZip);

// 2. Clean + extract
fs.rmSync(RELEASE, { recursive: true, force: true });
fs.mkdirSync(RELEASE, { recursive: true });
console.log("Extracting...");
new AdmZip(bestZip).extractAllTo(RELEASE, true);

// v43+ extracts flat, older versions in subfolder
let electronRoot = RELEASE;
const subs = fs.readdirSync(RELEASE).filter(d => d.startsWith("electron-"));
if (subs.length) electronRoot = path.join(RELEASE, subs[0]);

// 3. Copy app into resources/
const appDir = path.join(electronRoot, "resources", "app");
fs.rmSync(appDir, { recursive: true, force: true });
fs.mkdirSync(appDir, { recursive: true });
copyDir("dist", path.join(appDir, "dist"));
copyDir("electron", path.join(appDir, "electron"));
// Copy engine (onedir)
const engineDir = path.resolve("electron/hcompress-engine");
if (fs.existsSync(engineDir)) {
  const destDir = path.join(appDir, "electron/hcompress-engine");
  fs.rmSync(destDir, { recursive: true, force: true });
  copyDir(engineDir, destDir);
}
fs.writeFileSync(path.join(appDir, "package.json"),
  JSON.stringify({ main: "electron/main.cjs", name: "hcompress", version: "2.0.0" }, null, 2));

// 4. Rename
const exe = path.join(electronRoot, "electron.exe");
const target = path.join(electronRoot, "hcompress.exe");
if (fs.existsSync(exe)) { fs.renameSync(exe, target); }

// 5. Copy icon
const iconSrc = path.resolve("public/icon.ico");
if (fs.existsSync(iconSrc)) fs.copyFileSync(iconSrc, path.join(electronRoot, "hcompress.ico"));

// Clean
for (const f of ["LICENSE","LICENSES.chromium.html","version"])
  try { fs.unlinkSync(path.join(electronRoot, f)); } catch {}

console.log("\n✅ Done!  Launch:", target);

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, e.name), d = path.join(dest, e.name);
    if (e.isDirectory()) copyDir(s, d); else fs.copyFileSync(s, d);
  }
}
