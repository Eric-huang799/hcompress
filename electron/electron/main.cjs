const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const path = require("path");
const { spawn, spawnSync } = require("child_process");
const os = require("os");

let mainWindow = null;

// ── Find hcompress engine EXE ──
function findEngine() {
  const candidates = [
    // Bundled onedir (packaged)
    path.join(__dirname, "hcompress-engine", "hcompress-engine.exe"),
    // Bundled onefile (legacy)
    path.join(__dirname, "hcompress-engine.exe"),
    // Dev mode
    path.join(__dirname, "../../dist/hcompress-engine", "hcompress-engine.exe"),
    path.join(__dirname, "../../../hcompress/dist/hcompress-engine", "hcompress-engine.exe"),
  ];
  for (const c of candidates) {
    if (require("fs").existsSync(c)) return c;
  }
  return null;
}

function runEngine(args, extraEnv = {}) {
  const exe = findEngine();
  if (!exe) return Promise.resolve({ success: false, stderr: "引擎未找到，请重新安装 hcompress" });

  return new Promise((resolve) => {
    const env = { ...process.env, PYTHONIOENCODING: "utf-8", ...extraEnv };
    const proc = spawn(exe, args, { env, windowsHide: true });
    let out = "", err = "";
    proc.stdout.on("data", d => out += String(d));
    proc.stderr.on("data", d => err += String(d));
    proc.on("error", e => resolve({ success: false, stderr: "引擎启动失败: " + e.message }));
    proc.on("close", code => resolve({ success: code === 0, stdout: out, stderr: err }));
  });
}

// ── Timeout watchdog for compress / decompress ──
let _reqCounter = 0;

function _calcTimeout(args) {
  // Estimate file size for timeout calculation
  let sizeBytes = 0;
  try {
    if (args[0] === "c" || args[0] === "d") {
      const p = args[1];  // input path
      if (p && require("fs").existsSync(p)) {
        sizeBytes = require("fs").statSync(p).size;
      }
    }
  } catch (_) {}
  const mb = sizeBytes / (1024 * 1024);
  if (sizeBytes === 0) return 8000;                     // unknown → 8s
  if (mb < 100) return 8000;                            // <100MB → 8s
  if (mb >= 1024) return 30000;                         // >=1GB → 30s
  return Math.round(8000 + (30000 - 8000) * (mb - 100) / (1024 - 100));
}

function runEngineWatchdog(args, extraEnv = {}) {
  const exe = findEngine();
  if (!exe) return Promise.resolve({ success: false, stderr: "引擎未找到" });

  const timeoutMs = _calcTimeout(args);
  const reqId = ++_reqCounter;

  return new Promise((resolve) => {
    const env = { ...process.env, PYTHONIOENCODING: "utf-8", ...extraEnv };
    const proc = spawn(exe, args, { env, windowsHide: true });
    let out = "", err = "";
    let finished = false;
    let warnTimer = null;

    const done = (result) => {
      if (finished) return;
      finished = true;
      clearTimeout(warnTimer);
      resolve(result);
    };

    proc.stdout.on("data", d => out += String(d));
    proc.stderr.on("data", d => err += String(d));
    proc.on("error", e => done({ success: false, stderr: "引擎启动失败: " + e.message }));
    proc.on("close", code => done({ success: code === 0, stdout: out, stderr: err }));

    warnTimer = setTimeout(() => {
      if (finished) return;
      if (mainWindow) {
        mainWindow.webContents.send("timeout:warning", {
          reqId, timeout: timeoutMs,
          action: args[0] === "d" ? "解压" : "压缩",
          file: String(args[1] || ""),
        });
      }
    }, timeoutMs);

    // Listen for user response — use a named channel per request
    const chan = "timeout:resp:" + reqId;
    const handler = (_e, choice) => {
      if (choice === "abort") {
        ipcMain.removeListener(chan, handler);
        proc.kill();
        done({ success: false, stderr: "操作已被用户终止" });
      } else {
        // Continue — restart the same timeout, warn again later
        clearTimeout(warnTimer);
        warnTimer = setTimeout(() => {
          if (finished) return;
          if (mainWindow) {
            mainWindow.webContents.send("timeout:warning", {
              reqId, timeout: timeoutMs,
              action: args[0] === "d" ? "解压" : "压缩",
              file: String(args[1] || ""),
            });
          }
        }, timeoutMs);
      }
    };
    ipcMain.on(chan, handler);
  });
}

// ── Disabled plugins (session-level, shared across IPC calls) ──
let disabledPlugins = new Set();

function _disabledEnv() {
  if (disabledPlugins.size === 0) return {};
  return { HCOMPRESS_DISABLED_PLUGINS: Array.from(disabledPlugins).join(",") };
}

// ── Window ──
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100, height: 750, minWidth: 700, minHeight: 500,
    title: "hcompress", backgroundColor: "#06060a",
    icon: path.join(__dirname, "../hcompress.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true, nodeIntegration: false,
    },
  });
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(() => {
  findEngine(); // pre-warm
  createWindow();
  watchPlugins();
});
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });

// ── Plugin file watcher ──
function watchPlugins() {
  const candidates = [
    path.resolve(__dirname, "../../../hcompress/hcompress/plugins/builtin"),
    path.resolve(__dirname, "../../../../hcompress/hcompress/plugins/builtin"),
    path.join(require("os").homedir(), "hcompress/hcompress/plugins/builtin"),
  ];
  let pluginDir = null;
  for (const c of candidates) {
    if (require("fs").existsSync(c)) { pluginDir = c; break; }
  }
  if (!pluginDir) return;

  try {
    require("fs").watch(pluginDir, (eventType, filename) => {
      if (filename && filename.endsWith(".py")) {
        console.log("[plugin-watcher] detected:", filename, eventType);
        if (mainWindow) {
          mainWindow.webContents.send("plugins:changed", { file: filename, event: eventType });
        }
      }
    });
    console.log("[plugin-watcher] watching:", pluginDir);
  } catch (e) {
    console.log("[plugin-watcher] failed to watch:", e.message);
  }
}

// ── IPC ──
ipcMain.handle("hcompress:compress", async (_e, { input, output, level }) =>
  runEngineWatchdog(["c", input, "-o", output, "--level", String(level || 6), "-f"], _disabledEnv())
);

ipcMain.handle("hcompress:decompress", async (_e, { input, output }) => {
  const r = await runEngineWatchdog(["d", input, "-o", output, "-f"], _disabledEnv());
  const combined = (r.stdout || "") + (r.stderr || "");
  r.bombDetected = combined.includes("检测到疑似压缩炸弹") || combined.includes("BombDetectedError");
  return r;
});

ipcMain.handle("hcompress:hcfInfo", async (_e, filePath) =>
  runEngine(["info", filePath])
);

ipcMain.handle("hcompress:listPlugins", async () => {
  const r = await runEngine(["plugin", "list", "--json"]);
  try {
    const data = JSON.parse((r.stdout || "").trim().split("\n").pop() || "{}");
    if (data.plugins) {
      data.plugins = data.plugins.map(p => ({
        ...p,
        enabled: p.enabled && !disabledPlugins.has(p.name)
      }));
      data.count_enabled = data.plugins.filter(p => p.enabled).length;
    }
    return { success: true, ...data };
  } catch {
    return { success: false, plugins: [], count: 0, count_enabled: 0 };
  }
});

ipcMain.handle("hcompress:enablePlugin", async (_e, name) => {
  disabledPlugins.delete(name);
  return { success: true };
});

ipcMain.handle("hcompress:disablePlugin", async (_e, name) => {
  disabledPlugins.add(name);
  return { success: true };
});

ipcMain.handle("dialog:openFile", async () => {
  const r = await dialog.showOpenDialog(mainWindow, { properties: ["openFile", "multiSelections"] });
  return r.canceled ? [] : r.filePaths;
});

ipcMain.handle("dialog:openDirectory", async () => {
  const r = await dialog.showOpenDialog(mainWindow, { properties: ["openDirectory"] });
  return r.canceled ? [] : r.filePaths;
});

// ── Plugin Store ──
const STORE_URLS = [
  "https://api.github.com/repos/Eric-huang799/hcompress-win-plugins/contents/index.json",
  "https://cdn.jsdelivr.net/gh/Eric-huang799/hcompress-win-plugins@main/index.json",
];
const STORE_RAW_BASES = [
  "https://cdn.jsdelivr.net/gh/Eric-huang799/hcompress-win-plugins@main/",
  "https://raw.githubusercontent.com/Eric-huang799/hcompress-win-plugins/main/",
];

function _findPluginsDir() {
  const fs = require("fs");
  const candidates = [
    path.join(path.dirname(process.execPath || process.argv[0]), "plugins"),
    path.join(require("os").homedir(), ".hcompress", "plugins"),
    path.join(__dirname, "../../../plugins"),
  ];
  for (const d of candidates) {
    if (fs.existsSync(d)) return d;
  }
  const def = path.join(path.dirname(process.execPath || process.argv[0]), "plugins");
  fs.mkdirSync(def, { recursive: true });
  return def;
}

async function _netFetchMulti(urls) {
  const { net } = require("electron");
  let lastErr = null;
  for (const url of urls) {
    try {
      const resp = await net.fetch(url);
      if (resp.ok) return resp;
      lastErr = new Error("HTTP " + resp.status);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error("所有源均不可用");
}

ipcMain.handle("store:fetch", async () => {
  try {
    const resp = await _netFetchMulti(STORE_URLS);
    const text = await resp.text();
    let parsed;

    // GitHub API returns { content: "<base64>", encoding: "base64" }
    try { parsed = JSON.parse(text); } catch (_) { throw new Error("数据格式错误"); }
    if (parsed.content && parsed.encoding === "base64") {
      parsed = JSON.parse(Buffer.from(parsed.content, "base64").toString("utf-8"));
    }

    // Check external plugins dir
    const pluginsDir = _findPluginsDir();
    const fs = require("fs");
    const externalInstalled = fs.existsSync(pluginsDir)
      ? fs.readdirSync(pluginsDir).filter(f => f.endsWith(".py"))
      : [];

    // Also query engine for builtin plugins
    let engineNames = new Set();
    try {
      const engineResp = await runEngine(["plugin", "list", "--json"]);
      if (engineResp.success && engineResp.stdout) {
        const data = JSON.parse(String(engineResp.stdout).trim().split("\n").pop() || "{}");
        if (data.plugins) {
          data.plugins.forEach(p => engineNames.add(p.name));
        }
      }
    } catch (_) {}

    if (parsed.plugins) {
      parsed.plugins = parsed.plugins.map(p => ({
        ...p,
        installed: externalInstalled.includes(p.file) || engineNames.has(p.name),
      }));
    }
    return { success: true, ...parsed };
  } catch (e) {
    console.error("[store:fetch]", e);
    return { success: false, error: "网络连接失败: " + (e.message || String(e)) };
  }
});

ipcMain.handle("store:download", async (_e, pluginFile) => {
  const { net } = require("electron");
  const fs = require("fs");
  const pluginsDir = _findPluginsDir();
  let lastErr = null;

  for (const base of STORE_RAW_BASES) {
    try {
      const resp = await net.fetch(base + pluginFile);
      if (!resp.ok) { lastErr = new Error("HTTP " + resp.status); continue; }
      const buf = await resp.arrayBuffer();
      fs.writeFileSync(path.join(pluginsDir, pluginFile), Buffer.from(buf));
      return { success: true };
    } catch (e) {
      lastErr = e;
    }
  }
  return { success: false, error: "下载失败: " + (lastErr ? lastErr.message : "所有源不可用") };
});

ipcMain.handle("store:uninstall", async (_e, pluginFile) => {
  const fs = require("fs");
  const pluginsDir = _findPluginsDir();
  try {
    fs.unlinkSync(path.join(pluginsDir, pluginFile));
    return { success: true };
  } catch (e) {
    return { success: false, error: e.message };
  }
});

// ── Hub management ──
ipcMain.handle("hub:config", async (_e, { hubType, action, name }) => {
  const fs = require("fs");
  const configFile = path.join(_findPluginsDir(), hubType === "transform" ? "transform_hub.json" : "filter_hub.json");
  let cfg = { chain: [] };
  try { cfg = JSON.parse(fs.readFileSync(configFile, "utf-8")); } catch (_) {}

  if (action === "list") {
    return { success: true, chain: cfg.chain || [] };
  }
  if (action === "add" && name) {
    cfg.chain = [...(cfg.chain || []), { name, enabled: true }];
    fs.writeFileSync(configFile, JSON.stringify(cfg, null, 2));
    return { success: true };
  }
  if (action === "remove" && name) {
    cfg.chain = (cfg.chain || []).filter(e => e.name !== name);
    fs.writeFileSync(configFile, JSON.stringify(cfg, null, 2));
    return { success: true };
  }
  if (action === "reorder" && name) {
    const order = name.split(",");
    cfg.chain = order.map(n => (cfg.chain || []).find(e => e.name === n) || { name: n, enabled: true });
    fs.writeFileSync(configFile, JSON.stringify(cfg, null, 2));
    return { success: true };
  }
  return { success: false, error: "Unknown action" };
});

// ── open plugin dir for store ──
ipcMain.handle("store:openDir", async () => {
  const dir = _findPluginsDir();
  return require("electron").shell.openPath(dir);
});

ipcMain.handle("shell:openPath", async (_e, dirPath) => {
  const { shell } = require("electron");
  const fs = require("fs");
  // Try the given path, or find the hcompress plugins dir
  if (fs.existsSync(dirPath)) {
    return shell.openPath(dirPath);
  }
  // Try to find plugins directory relative to hcompress v1
  const candidates = [
    path.resolve(__dirname, "../../../hcompress/hcompress/plugins/builtin"),
    path.resolve(__dirname, "../../../../hcompress/hcompress/plugins/builtin"),
    path.join(require("os").homedir(), "hcompress/hcompress/plugins/builtin"),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return shell.openPath(c);
  }
  return "Plugin directory not found";
});
