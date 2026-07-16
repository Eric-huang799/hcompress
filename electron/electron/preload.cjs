const { contextBridge, ipcRenderer, webUtils } = require("electron");

contextBridge.exposeInMainWorld("hcompress", {
  compress: (input, output, level) =>
    ipcRenderer.invoke("hcompress:compress", { input, output, level }),
  decompress: (input, output) =>
    ipcRenderer.invoke("hcompress:decompress", { input, output }),
  hcfInfo: (filePath) =>
    ipcRenderer.invoke("hcompress:hcfInfo", filePath),
  openFile: () => ipcRenderer.invoke("dialog:openFile"),
  openDirectory: () => ipcRenderer.invoke("dialog:openDirectory"),
  openPluginDir: () => ipcRenderer.invoke("shell:openPath", ""),
  listPlugins: () => ipcRenderer.invoke("hcompress:listPlugins"),
  enablePlugin: (name) => ipcRenderer.invoke("hcompress:enablePlugin", name),
  disablePlugin: (name) => ipcRenderer.invoke("hcompress:disablePlugin", name),
  fetchStore: () => ipcRenderer.invoke("store:fetch"),
  downloadPlugin: (file) => ipcRenderer.invoke("store:download", file),
  uninstallPlugin: (file) => ipcRenderer.invoke("store:uninstall", file),
  openStoreDir: () => ipcRenderer.invoke("store:openDir"),
  getPathForFile: (file) => webUtils.getPathForFile(file),
  onTimeoutWarning: (callback) => {
    ipcRenderer.on("timeout:warning", (_e, info) => callback(info));
  },
  respondTimeout: (reqId, choice) => {
    ipcRenderer.send("timeout:resp:" + reqId, choice);
  },
  manageHub: (hubType, action, name) => {
    return ipcRenderer.invoke("hub:config", { hubType, action, name });
  },
  onPluginsChanged: (callback) => {
    ipcRenderer.on("plugins:changed", (_e, info) => callback(info));
  },
});
