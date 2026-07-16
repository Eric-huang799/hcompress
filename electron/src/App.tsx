import { useState, useCallback, useEffect } from "react";
import { useTheme } from "./hooks/useTheme";
import "./styles/theme.css";

type ThemeMode = "light" | "dark" | "system";

/* ── Types ── */
interface FileEntry {
  id: number; name: string; path: string; size: number; isDir: boolean; ext: string;
}

function fmt(n: number): string {
  for (const u of ["B","KB","MB","GB"]) { if (n < 1024) return `${n.toFixed(1)} ${u}`; n /= 1024; }
  return `${n.toFixed(1)} TB`;
}

function estRatio(ext: string): number {
  const g = [".txt",".md",".log",".csv",".json",".xml",".html",".css",".js",".py",".c",".cpp",".obj",".bmp",".wav"];
  if (ext === "folder") return 0.52;
  if (g.some(e => ext.toLowerCase().endsWith(e))) return 0.48;
  return 0.98;
}
function est(ext: string): string { const r = estRatio(ext); return `~${(r*100).toFixed(0)}%`; }

/* ── Sidebar ── */
function Sidebar({ active, onNav, pluginCount, subCount, onRefreshPlugins }: { active: string; onNav: (t: string) => void; pluginCount: number; subCount: number; onRefreshPlugins: () => void }) {
  const items = [
    { id: "compress", label: "📦 压缩" },
    { id: "decompress", label: "📂 解压" },
    { id: "browser", label: "📁 归档浏览器" },
    { id: "store", label: "🏪 插件商店" },
    { id: "plugins", label: "🔌 已安装插件", badge: String(pluginCount), subBadge: subCount > 0 ? String(subCount) : undefined },
  ];
  return (
    <aside className="sidebar">
      <div className="logo">hcompress <span>v2</span></div>
      {items.map(it => (
        <button key={it.id} className={`nav-item ${active === it.id ? "active" : ""}`} onClick={() => onNav(it.id)}>
          {it.label}{it.badge && <span className="badge">{it.badge}</span>}{it.subBadge && <span className="badge" style={{ background: "var(--yellow)", color: "#000", fontSize: ".65em", marginLeft: 2 }}>{it.subBadge}</span>}
        </button>
      ))}
      <div style={{ flex: 1 }} />
      <button className="btn btn-ghost" style={{ fontSize: ".75em", color: "var(--dim)", justifyContent: "center" }}
              onClick={onRefreshPlugins} title="手动刷新插件">
        🛡️ BombGuard · 🔄 刷新
      </button>
    </aside>
  );
}

/* ── Settings Modal ── */
function SettingsModal({ mode, setMode, onClose }: {
  mode: ThemeMode; setMode: (m: ThemeMode) => void; onClose: () => void;
}) {
  const themes: { key: ThemeMode; label: string }[] = [
    { key: "light", label: "☀️ 浅色" }, { key: "system", label: "💻 跟随系统" }, { key: "dark", label: "🌙 深色" },
  ];
  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <span style={{ fontWeight: 700, fontSize: "1.1em" }}>⚙️ 设置</span>
          <button className="btn btn-ghost" onClick={onClose} style={{ fontSize: "1.2em" }}>✕</button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <div style={{ fontSize: ".8em", color: "var(--dim)", marginBottom: 8 }}>主题外观</div>
            <div className="theme-row">
              {themes.map(t => (
                <button key={t.key} className={`theme-btn ${mode === t.key ? "active" : ""}`}
                        onClick={() => setMode(t.key)}>{t.label}</button>
              ))}
            </div>
          </div>
          <div>
            <div style={{ fontSize: ".8em", color: "var(--dim)", marginBottom: 6 }}>默认压缩级别</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input type="range" min={0} max={9} defaultValue={6} style={{ flex: 1 }} />
              <span style={{ fontWeight: 600, width: 20, textAlign: "center" }}>6</span>
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: ".88em" }}>🛡️ BombGuard</span>
            <span style={{ color: "var(--green)", fontWeight: 600 }}>已启用</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: ".88em" }}>📦 默认输出目录</span>
            <span style={{ color: "var(--muted)", fontSize: ".82em" }}>~/Desktop</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Drop Zone ── */
function DropZone({ onAdd, onDropFiles }: { onAdd: () => void; onDropFiles: (paths: string[]) => void }) {
  const [drag, setDrag] = useState(false);
  return (
    <div className={`dropzone ${drag ? "active" : ""}`}
         onDragOver={e => { e.preventDefault(); setDrag(true); }}
         onDragLeave={() => setDrag(false)}
         onDrop={e => {
           e.preventDefault(); setDrag(false);
           const dt = e.dataTransfer;
           if (dt?.files?.length) {
             const paths: string[] = [];
             for (let i = 0; i < dt.files.length; i++) {
               const f = dt.files[i];
               const p = api?.getPathForFile ? api.getPathForFile(f) : (f as any).path;
               if (p) paths.push(p);
             }
             if (paths.length) { onDropFiles(paths); return; }
           }
           onAdd();
         }}
         onClick={onAdd}>
      <div className="icon">📦</div>
      <div className="hint">拖拽文件或文件夹到此处<br />
        <span style={{ fontSize: ".8em", marginTop: 4, display: "inline-block", color: "var(--dim)" }}>
          或点击 <strong>添加文件 / 文件夹</strong> 按钮
        </span>
      </div>
    </div>
  );
}

/* ── File Table ── */
function FileTable({ files, onRemove }: { files: FileEntry[]; onRemove: (id: number) => void }) {
  if (files.length === 0) return null;
  const total = files.reduce((s, f) => s + f.size, 0);
  const totalEst = files.reduce((s, f) => s + f.size * estRatio(f.ext), 0);
  return (
    <>
      <table className="file-table">
        <thead><tr><th>文件</th><th style={{ width: 90 }}>大小</th><th style={{ width: 100 }}>预计压缩率</th><th style={{ width: 50 }}></th></tr></thead>
        <tbody>
          {files.map(f => {
            const cls = estRatio(f.ext) < 0.6 ? "ratio-good" : estRatio(f.ext) < 0.95 ? "ratio-ok" : "ratio-bad";
            return (
              <tr key={f.id}>
                <td><span className="name">{f.isDir ? "📁" : "📄"} {f.name} <span className="ext">{f.ext}</span></span></td>
                <td className="size">{fmt(f.size)}</td>
                <td className={cls}>{est(f.ext)}</td>
                <td><button className="btn btn-ghost" style={{ padding: "4px 8px", fontSize: ".8em" }} onClick={() => onRemove(f.id)}>✕</button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="cards">
        <div className="card"><div className="label">总原始大小</div><div className="value">{fmt(total)}</div></div>
        <div className="card"><div className="label">预计压缩后</div><div className="value" style={{ color: "var(--accent2)" }}>{fmt(totalEst)}</div></div>
        <div className="card" style={{ borderColor: "rgba(30,157,91,.2)" }}>
          <div className="label">🛡️ BombGuard</div><div className="value" style={{ color: "var(--green)", fontSize: "1.1em" }}>✓ 已启用 · 阈值 100:1</div>
        </div>
      </div>
    </>
  );
}

/* ── Progress Bar ── */
function Prog({ pct, isDecomp }: { pct: number; isDecomp?: boolean }) {
  return (
    <div className="card" style={{ animation: "scaleIn .3s ease-out" }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ fontWeight: 600 }}>{isDecomp ? "🧊 解压中…" : "⚡ 压缩中…"}</span><span style={{ color: "var(--muted)", fontSize: ".85em" }}>{pct}%</span>
      </div>
      <div className="progress-bar"><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
      <div className="progress-meta"><span>13.7 MB / 20.4 MB</span><span>5.2 MB/s · 剩余 ~1.3s</span></div>
    </div>
  );
}

/* ── Toast ── */
function Toast({ msg }: { msg: string }) {
  if (!msg) return null;
  return <div className="toast success"><span>✅</span> {msg}</div>;
}

/* ── Archive Browser ── */
function ArchiveBrowser() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, alignItems: "center", paddingTop: 40 }}>
      <div style={{ fontSize: "3em", opacity: .4 }}>📁</div>
      <div style={{ color: "var(--muted)", textAlign: "center", lineHeight: 1.8 }}>
        打开一个 <strong>.hcf</strong> 文件即可浏览归档内容<br />
        <span style={{ fontSize: ".85em", color: "var(--dim)" }}>
          支持查看目录结构和文件列表
        </span>
      </div>
      <button className="btn btn-outline" onClick={async () => {
        const api = (window as any).hcompress;
        if (api) {
          const paths = await api.openFile();
          if (paths.length) {
            // Show file info via backend
            const r = await api.hcfInfo(paths[0]);
            alert("HCF 文件信息:\n" + (r?.stdout || "无法读取"));
          }
        }
      }}>📂 打开 HCF 文件</button>
    </div>
  );
}

/* ── Plugin Store ── */
interface StorePlugin {
  name: string; type: string; version: string; author: string;
  description: string; file: string; size_kb: number;
  dependencies: string[]; tags: string[]; installed: boolean;
}

function PluginStore() {
  const [plugins, setPlugins] = useState<StorePlugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [downloading, setDownloading] = useState<string | null>(null);

  const fetchStore = useCallback(() => {
    setLoading(true); setError("");
    const api = (window as any).hcompress;
    if (api?.fetchStore) {
      api.fetchStore().then((r: any) => {
        if (r?.success) setPlugins(r.plugins || []);
        else setError(r?.error || "获取商店失败");
        setLoading(false);
      }).catch(() => { setError("网络连接失败"); setLoading(false); });
    } else {
      setError("未连接到后端"); setLoading(false);
    }
  }, []);

  useState(() => { fetchStore(); });

  const download = async (p: StorePlugin) => {
    const api = (window as any).hcompress;
    if (!api?.downloadPlugin) return;
    setDownloading(p.file);
    const r = await api.downloadPlugin(p.file);
    if (r?.success) {
      setToast(`✅ ${p.name} 安装完成`);
      setTimeout(() => setToast(""), 3000);
      fetchStore(); // refresh installed status
    } else {
      setToast(`❌ 安装失败: ${r?.error || "未知错误"}`);
      setTimeout(() => setToast(""), 3000);
    }
    setDownloading(null);
  };

  const uninstall = async (p: StorePlugin) => {
    const api = (window as any).hcompress;
    if (!api?.uninstallPlugin) return;
    const r = await api.uninstallPlugin(p.file);
    if (r?.success) {
      setToast(`🗑 ${p.name} 已卸载`);
      setTimeout(() => setToast(""), 3000);
      fetchStore();
    } else {
      setToast(`❌ 卸载失败`);
      setTimeout(() => setToast(""), 3000);
    }
  };

  const typeIcon = (t: string) => {
    switch (t) {
      case "transform": return "🔄"; case "extension": return "🧩";
      case "filter": return "🔍"; case "codec": return "📦";
      default: return "🔌";
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontWeight: 600 }}>
          🏪 Windows 插件社区
          {!loading && (
            <span style={{ fontWeight: 400, color: "var(--dim)", fontSize: ".85em", marginLeft: 8 }}>
              共 {plugins.length} 个 · 已安装 {plugins.filter(p => p.installed).length} 个
            </span>
          )}
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-outline" style={{ fontSize: ".8em" }} onClick={fetchStore} disabled={loading}>
            🔄 刷新
          </button>
          <button className="btn btn-outline" style={{ fontSize: ".8em" }} onClick={() => {
            (window as any).hcompress?.openStoreDir();
          }}>
            📂 打开目录
          </button>
        </div>
      </div>

      {loading && (
        <div className="card" style={{ textAlign: "center", padding: 24, color: "var(--muted)" }}>
          加载社区插件列表中…
        </div>
      )}
      {error && (
        <div className="card" style={{ textAlign: "center", padding: 24, borderColor: "rgba(229,83,91,.3)" }}>
          <div style={{ color: "var(--red)", marginBottom: 8 }}>⚠ {error}</div>
          <button className="btn btn-outline" style={{ fontSize: ".8em" }} onClick={fetchStore}>重试</button>
        </div>
      )}
      {!loading && !error && plugins.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: 24, color: "var(--muted)" }}>
          社区暂无插件
        </div>
      )}

      {plugins.map(p => (
        <div key={p.file} className="card" style={{
          opacity: p.installed ? 1 : .85,
          borderColor: p.installed ? "rgba(69,217,193,.2)" : undefined,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: "1.2em" }}>{typeIcon(p.type)}</span>
                <span style={{ fontWeight: 600 }}>{p.name}</span>
                <span style={{ fontSize: ".7em", color: "var(--dim)", background: "var(--bg)", padding: "1px 6px", borderRadius: 4 }}>
                  v{p.version}
                </span>
                <span style={{ fontSize: ".72em", color: "var(--accent2)", background: "rgba(69,217,193,.1)", padding: "1px 7px", borderRadius: 4 }}>
                  {p.type}
                </span>
                <span style={{ fontSize: ".7em", color: "var(--dim)", marginLeft: "auto" }}>
                  ⚡{p.size_kb}KB
                </span>
              </div>
              <div style={{ fontSize: ".82em", color: "var(--muted)", marginBottom: 2 }}>{p.description}</div>
              <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                {p.author && <span style={{ fontSize: ".72em", color: "var(--dim)" }}>by {p.author}</span>}
                {p.dependencies && p.dependencies.length > 0 && (
                  <span style={{ fontSize: ".72em", color: "var(--yellow)" }}>
                    🔗 需要: {p.dependencies.join(", ")}
                  </span>
                )}
                {p.tags && p.tags.length > 0 && (
                  <span style={{ fontSize: ".7em", color: "var(--dim)" }}>
                    {p.tags.map((t: string) => (
                      <span key={t} style={{ marginRight: 4, background: "var(--bg)", padding: "1px 5px", borderRadius: 3 }}>{t}</span>
                    ))}
                  </span>
                )}
              </div>
            </div>
            <div style={{ marginLeft: 16, display: "flex", alignItems: "center", gap: 8 }}>
              {p.installed ? (
                <button
                  className="btn btn-outline"
                  style={{ fontSize: ".75em", padding: "4px 12px", color: "var(--green)", borderColor: "rgba(62,201,126,.3)" }}
                  onClick={() => uninstall(p)}
                >
                  ✓ 已安装
                </button>
              ) : (
                <button
                  className="btn btn-primary"
                  style={{ fontSize: ".75em", padding: "4px 12px" }}
                  onClick={() => download(p)}
                  disabled={downloading === p.file}
                >
                  {downloading === p.file ? "下载中…" : "⬇ 下载"}
                </button>
              )}
            </div>
          </div>
        </div>
      ))}

      <div className="card" style={{ borderStyle: "dashed", textAlign: "center", padding: 20, fontSize: ".85em", color: "var(--muted)" }}>
        💡 下载的插件保存在 exe 旁边的 <code style={{ color: "var(--accent)" }}>plugins/</code> 目录<br />
        下次压缩时自动生效 · 也可手动放入 .py 文件
      </div>

      {toast && (
        <div style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 300,
          background: "var(--card)", border: "1px solid var(--accent)",
          borderRadius: 10, padding: "14px 20px", boxShadow: "var(--shadow)",
          fontSize: ".88em", animation: "slideUp .3s ease-out",
        }}>
          {toast}
        </div>
      )}
    </div>
  );
}


/* ── Plugin Wiring Panel ── */
interface PluginInfo {
  id: string; name: string; version: string; type: string;
  description: string; author: string; priority: number;
  enabled: boolean; isHub?: boolean; subCount?: number;
  errorMsg?: string;
}
const PIPELINE_SLOTS = ["transform","filter","codec","checksum","io","splitter","matcher"];
const SYSTEM_SLOTS = ["hook","extension","observer"];
const SLOT_LABELS: Record<string,string> = { transform:"Transform", filter:"Filter", codec:"Codec", checksum:"Checksum", io:"IO Backend", splitter:"Splitter", matcher:"MatchFinder", hook:"Hook", extension:"Extension", observer:"Observer" };

function PluginManager() {
  const [allPlugins, setAllPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");
  const [selRight, setSelRight] = useState<string | null>(null);
  const [confirmSlot, setConfirmSlot] = useState<{plugName:string; slotType:string; subOf:string; action?:string; existingName?:string} | null>(null);
  const [hubChildren, setHubChildren] = useState<Record<string,string[]>>({});
  const [slotDisabled, setSlotDisabled] = useState<Set<string>>(new Set());  // in-slot but turned off

  const api = (window as any).hcompress;
  const refresh = useCallback(async () => {
    if (!api?.listPlugins) { setLoading(false); return; }
    try {
      const r = await api.listPlugins();
      if (r?.plugins) {
        setAllPlugins(r.plugins.map((p:any) => ({
          id: p.name.toLowerCase().replace(/[^a-z0-9]/g,"_"),
          name:p.name, version:p.version||"0.0.0", type:p.plugin_type,
          description:p.description||"", author:p.author||"",
          priority:p.priority??100, enabled:p.enabled,
          isHub:!!p.is_hub, subCount:p.sub_count||0,
        })));
      }
    } catch (_) {}
    setLoading(false);
  }, []);
  useState(() => { refresh(); });
  useState(() => { if (api?.onPluginsChanged) api.onPluginsChanged(() => setTimeout(refresh, 800)); });

  const pByName = (n:string) => allPlugins.find(p=>p.name===n);
  const slotPlugins = (slot:string) => allPlugins.filter(p => (p.enabled || slotDisabled.has(p.name)) && p.type === slot);
  const rightPlugins = allPlugins.filter(p => !p.enabled && !slotDisabled.has(p.name));

  const send = (msg:string) => { setToast(msg); setTimeout(()=>setToast(""),2500); };

  const doToggle = async (name:string) => {
    const p = pByName(name); if (!p) return;
    if (p.enabled) {
      await api.disablePlugin(name);
      setSlotDisabled(prev => new Set(prev).add(name));
      send(name+" 已关闭（仍占槽位）");
    } else {
      await api.enablePlugin(name);
      setSlotDisabled(prev => { const n = new Set(prev); n.delete(name); return n; });
      send(name+" 已启用");
    }
    refresh();
  };
  const doEject = async (name:string, subOf?:string) => {
    if (subOf) {
      await api.manageHub?.(pByName(subOf)?.type==="filter"?"filter":"transform","remove",name);
      setHubChildren(prev=>({...prev,[subOf]:(prev[subOf]||[]).filter(n=>n!==name)}));
    } else { await api.disablePlugin(name); }
    setSlotDisabled(prev => { const n = new Set(prev); n.delete(name); return n; });
    send(name+" 已弹出"); refresh();
  };
  const doConnect = async (plugName:string, slotType:string, subOf:string) => {
    if (subOf) {
      await api.manageHub?.(slotType,"add",plugName);
      setHubChildren(prev=>({...prev,[subOf]:[...(prev[subOf]||[]),plugName]}));
    } else { await api.enablePlugin(plugName); }
    setConfirmSlot(null); setSelRight(null); send(plugName+" 已连接"); refresh();
  };

  const doCreateHub = async (plugName:string, existingName:string, slotType:string) => {
    // 1. Disable existing plugin
    await api.disablePlugin(existingName);
    // 2. Find Hub plugin of matching type
    const hubName = slotType==="filter"?"FilterHub":"TransformHub";
    const hub = pByName(hubName);
    if (!hub || hub.enabled) {
      // Hub already connected? Just add both to it
      const hubConnection = allPlugins.find(p=>p.isHub&&p.enabled&&p.type===slotType);
      if (hubConnection) {
        await api.manageHub?.(slotType, "add", existingName);
        await api.manageHub?.(slotType, "add", plugName);
        await api.enablePlugin(plugName);
        setHubChildren(prev=>({...prev,[hubConnection.name]:[...(prev[hubConnection.name]||[]),existingName,plugName]}));
        send("已接入 "+hubConnection.name+" 扩展坞"); refresh(); return;
      }
      // Enable the hub if not already
      await api.enablePlugin(hubName);
    }
    // 3. Add both to hub chain
    await api.manageHub?.(slotType, "add", existingName);
    await api.manageHub?.(slotType, "add", plugName);
    await api.enablePlugin(plugName);
    setHubChildren(prev=>({...prev,[hubName]:[existingName,plugName]}));
    setConfirmSlot(null); setSelRight(null); send(existingName+" + "+plugName+" 已接入扩展坞"); refresh();
  };

  const renderSlot = (slot:string, isSystem:boolean) => {
    const conn = slotPlugins(slot);
    const isBlink = !!selRight && (pByName(selRight)?.type||"") === slot;
    const slotFull = PIPELINE_SLOTS.includes(slot) && conn.filter(c=>!c.isHub).length >= 1;
    const hubConn = conn.filter(c=>c.isHub);
    const plainConn = conn.filter(c=>!c.isHub);
    return (
      <div key={slot} style={{padding:"10px 12px",margin:"6px 0",borderRadius:10,border:isSystem?"2px solid rgba(229,83,91,.2)":"2px solid rgba(108,140,255,.15)",background:"var(--card)",transition:"all .15s",...(isBlink?{animation:"blinkPulse .8s ease-in-out infinite",cursor:"pointer",boxShadow:"0 0 8px rgba(108,140,255,.3)"}:{})}}
        onClick={()=>{
          if(!isBlink||!selRight)return;
          if(slotFull){
            const existName = plainConn[0]?.name || "";
            setConfirmSlot({plugName:selRight,slotType:slot,subOf:"",action:"createHub",existingName:existName});
            return;
          }
          setConfirmSlot({plugName:selRight,slotType:slot,subOf:""});
        }}>
        <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:8}}>
          <span style={{fontSize:".9em",fontWeight:600,color:isSystem?"var(--red)":"var(--accent)"}}>{isSystem?"▣":"▢"}</span>
          <span style={{fontSize:".85em",fontWeight:600}}>{SLOT_LABELS[slot]}</span>
          <span style={{fontSize:".7em",color:"var(--dim)"}}>{isSystem?"多槽":"单槽"}</span>
          {isBlink && <span style={{fontSize:".7em",color:"var(--yellow)",marginLeft:"auto"}}>← 点击连接</span>}
        </div>
        {conn.length===0 && <div style={{fontSize:".8em",color:"var(--dim)",textAlign:"center",padding:"10px 0",fontStyle:"italic"}}>{isBlink?"点击接入":"空槽位"}</div>}
        {plainConn.map(c=>{
          const effEnabled = c.enabled && !slotDisabled.has(c.name);
          return (
          <div key={c.name} style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"8px 10px",margin:"3px 0",borderRadius:8,border:effEnabled?"2px solid rgba(108,140,255,.3)":"2px dashed rgba(255,255,255,.08)",background:effEnabled?"var(--surface)":"rgba(255,255,255,.02)"}}>
            <div><span style={{fontWeight:600,fontSize:".88em",color:effEnabled?"var(--fg)":"var(--muted)"}}>{c.name}{!effEnabled&&slotDisabled.has(c.name)?" (已关闭)":""}</span><span style={{fontSize:".7em",color:"var(--dim)",marginLeft:8}}>v{c.version}</span></div>
            <span style={{display:"flex",gap:6,alignItems:"center"}}>
              <span style={{fontSize:".7em",color:effEnabled?"var(--green)":"var(--dim)"}}>{effEnabled?"🟢":"⚫"}</span>
              <button className="btn btn-outline" style={{fontSize:".75em",padding:"3px 10px"}} onClick={e=>{e.stopPropagation();doToggle(c.name);}}>{effEnabled?"关闭":"开启"}</button>
              <button className="btn btn-outline" style={{fontSize:".75em",padding:"3px 10px"}} onClick={e=>{e.stopPropagation();doEject(c.name);}}>弹出</button>
            </span>
          </div>
          );
        })}
        {hubConn.map(c=>{
          const subs = hubChildren[c.name]||[];
          return (
            <div key={c.name} style={{margin:"3px 0"}}>
              <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"8px 10px",borderRadius:8,background:"rgba(69,217,193,.08)",border:"2px solid rgba(69,217,193,.25)"}}>
                <span><span style={{fontWeight:600,fontSize:".88em"}}>{c.name}</span><span style={{fontSize:".7em",color:"var(--accent2)",marginLeft:6}}>扩展坞</span></span>
                {subs.length===0&&<button className="btn btn-outline" style={{fontSize:".75em",padding:"3px 10px"}} onClick={e=>{e.stopPropagation();doEject(c.name);}}>弹出</button>}
              </div>
              {subs.map(sn=>{
                const sp = pByName(sn);
                const subBlink = isBlink;
                return (
                  <div key={sn} style={{
                    marginLeft:16, padding:"6px 10px", margin:"3px 0", borderRadius:7,
                    border:subBlink?"2px solid rgba(108,140,255,.5)":"2px solid rgba(108,140,255,.15)",
                    background:"var(--bg)", display:"flex", alignItems:"center", justifyContent:"space-between",
                    ...(subBlink?{animation:"blinkPulse .8s ease-in-out infinite", cursor:"pointer"}:{})
                  }} onClick={(e) => {
                    e.stopPropagation();
                    if(!subBlink||!selRight) return;
                    setConfirmSlot({plugName:selRight, slotType:slot, subOf:c.name});
                  }}>
                    <span style={{fontSize:".82em"}}>🔵 {sn}</span>
                    {subBlink && <span style={{fontSize:".65em",color:"var(--yellow)"}}>← 点击连接</span>}
                    <span style={{display:"flex",gap:6}}>
                      <button className="btn btn-outline" style={{fontSize:".72em",padding:"2px 8px"}} onClick={e=>{e.stopPropagation();doToggle(sn);}}>{sp?.enabled?"关闭":"开启"}</button>
                      <button className="btn btn-outline" style={{fontSize:".72em",padding:"2px 8px"}} onClick={e=>{e.stopPropagation();doEject(sn,c.name);}}>弹出</button>
                    </span>
                  </div>
                );
              })}
              {/* Empty sub-slot for new connections */}
              <div key={"empty-"+c.name} style={{
                marginLeft:16, padding:"6px 10px", margin:"3px 0", borderRadius:7,
                border:isBlink?"2px dashed rgba(108,140,255,.4)":"2px dashed var(--border)",
                background:isBlink?"rgba(108,140,255,.04)":"transparent", textAlign:"center",
                ...(isBlink?{animation:"blinkPulse .8s ease-in-out infinite", cursor:"pointer"}:{})
              }} onClick={(e) => {
                e.stopPropagation();
                if(!isBlink||!selRight) return;
                setConfirmSlot({plugName:selRight, slotType:slot, subOf:c.name});
              }}>
                <span style={{fontSize:".72em",color:isBlink?"var(--accent)":"var(--dim)"}}>
                  {isBlink ? "点击连接子接口" : "+ 空子接口"}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div style={{display:"flex",flexDirection:"column",gap:12,height:"100%"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",flexShrink:0}}>
        <span style={{fontWeight:700,fontSize:"1.05em"}}>🔌 插件接线面板</span>
        <span style={{display:"flex",gap:8}}>
          <button className="btn btn-outline" style={{fontSize:".8em"}} onClick={refresh}>🔄 刷新</button>
          <button className="btn btn-outline" style={{fontSize:".8em"}} onClick={()=>api?.openPluginDir()}>📂 目录</button>
        </span>
      </div>
      {loading&&<div className="card" style={{textAlign:"center",padding:24,color:"var(--muted)"}}>加载中...</div>}
      <div style={{display:"flex",gap:14,flex:1,minHeight:0}}>
        <div style={{flex:1,overflowY:"auto",paddingRight:6}}>
          <div style={{fontSize:".78em",color:"var(--dim)",marginBottom:6,fontWeight:600}}>🔴 系统接口 ({SYSTEM_SLOTS.length})</div>
          {SYSTEM_SLOTS.map(s=>renderSlot(s,true))}
          <div style={{fontSize:".78em",color:"var(--dim)",margin:"16px 0 6px",fontWeight:600}}>🔵 普通接口 ({PIPELINE_SLOTS.length})</div>
          {PIPELINE_SLOTS.map(s=>renderSlot(s,false))}
        </div>
        <div style={{width:270,overflowY:"auto",borderLeft:"1px solid var(--border)",paddingLeft:12,flexShrink:0}}>
          <div style={{fontSize:".78em",color:"var(--dim)",marginBottom:8,fontWeight:600}}>🟢 可用插件 ({rightPlugins.length})</div>
          {rightPlugins.length===0&&<div style={{fontSize:".8em",color:"var(--muted)",textAlign:"center",padding:20}}>全部已连接 ✓</div>}
          {rightPlugins.map(p=>(
            <div key={p.id} className={"card "+(selRight===p.name?"plugin-card-selected":"")+(selRight&&selRight!==p.name?"plugin-card-dim":"")} style={{padding:"12px",margin:"8px 0",cursor:selRight===p.name?"default":"pointer",borderRadius:10}}
              onClick={()=>{setSelRight(selRight===p.name?null:p.name);}}>
              <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:4}}>
                <span style={{fontSize:"1.1em"}}>{p.isHub?"🔌":(p.type==="hook"?"🔴":"🔵")}</span>
                <span style={{fontWeight:600,fontSize:".85em"}}>{p.name}</span>
                <span style={{fontSize:".68em",color:"var(--dim)"}}>v{p.version}</span>
              </div>
              <div style={{fontSize:".72em",color:"var(--muted)",marginBottom:4}}>{p.type} · {p.author||"社区"}</div>
              {p.description&&<div style={{fontSize:".72em",color:"var(--muted)",marginBottom:6}}>{p.description.slice(0,45)}</div>}
            </div>
          ))}
        </div>
      </div>
      {confirmSlot && (confirmSlot.action === "createHub" ? (
        <div className="modal-overlay" onClick={()=>{setConfirmSlot(null);setSelRight(null);}}><div className="modal" style={{maxWidth:440}} onClick={e=>e.stopPropagation()}>
          <div style={{fontWeight:700,fontSize:"1.15em",marginBottom:12}}>🔌 创建扩展坞</div>
          <div style={{fontSize:".88em",color:"var(--muted)",marginBottom:16}}>
            {SLOT_LABELS[confirmSlot.slotType]} 单槽已满。创建扩展坞，将 <strong>{confirmSlot.existingName}</strong> 和 <strong>{confirmSlot.plugName}</strong> 同时接入？
          </div>
          <div style={{display:"flex",gap:10,justifyContent:"flex-end"}}>
            <button className="btn btn-outline" onClick={()=>{setConfirmSlot(null);setSelRight(null);}}>取消</button>
            <button className="btn btn-primary" onClick={()=>doCreateHub(confirmSlot.plugName,confirmSlot.existingName!,confirmSlot.slotType)}>创建扩展坞并接入</button>
          </div>
        </div></div>
      ) : (
        <div className="modal-overlay" onClick={()=>{setConfirmSlot(null);setSelRight(null);}}><div className="modal" style={{maxWidth:420}} onClick={e=>e.stopPropagation()}>
          <div style={{fontWeight:700,fontSize:"1.15em",marginBottom:12}}>{confirmSlot.subOf?("连接至 "+confirmSlot.subOf+" 子接口"):("连接至 "+SLOT_LABELS[confirmSlot.slotType])}</div>
          <div style={{fontSize:".88em",color:"var(--muted)",marginBottom:16}}>将 <strong>{confirmSlot.plugName}</strong> 接入 <strong>{SLOT_LABELS[confirmSlot.slotType]}</strong> 接口</div>
          <div style={{display:"flex",gap:10,justifyContent:"flex-end"}}>
            <button className="btn btn-outline" onClick={()=>{setConfirmSlot(null);setSelRight(null);}}>取消</button>
            <button className="btn btn-primary" onClick={()=>doConnect(confirmSlot.plugName,confirmSlot.slotType,confirmSlot.subOf)}>确认连接</button>
          </div>
        </div></div>
      ))}
      {toast&&(<div style={{position:"fixed",bottom:28,right:28,zIndex:300,background:"var(--card)",border:"1px solid var(--accent)",borderRadius:12,padding:"16px 24px",boxShadow:"var(--shadow)",fontSize:".9em",animation:"slideUp .3s ease-out"}}>{toast}</div>)}
    </div>
  );
}

/* ── Backend bridge ── */
const api = (window as any).hcompress || null;

/* ── App ── */
export default function App() {
  const { mode, setMode } = useTheme();
  const [nav, setNav] = useState("compress");
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const [compressing, setCompressing] = useState(false);
  const [toast, setToast] = useState("");
  const [nextId, setNextId] = useState(1);
  const [outputDir, setOutputDir] = useState("");
  const [pluginCount, setPluginCount] = useState(3);
  const [subCount, setSubCount] = useState(0);
  const [pluginKey, setPluginKey] = useState(0);

  // Auto-refresh plugin panel when navigating to plugins page
  useEffect(() => {
    if (nav === "plugins") setPluginKey(k => k + 1);
  }, [nav]);

  // Fetch plugin count on mount and on page nav
  const refreshPluginCount = useCallback(() => {
    if (!api?.listPlugins) return;
    api.listPlugins().then((r: any) => {
      if (r?.plugins) {
        setPluginCount(r.plugins.filter((p: any) => p.enabled && !p.is_hub).length);
        setSubCount(r.plugins.reduce((s: number, p: any) => s + (p.sub_count || 0), 0));
      }
    }).catch(() => {});
  }, []);

  useState(() => { refreshPluginCount(); });

  // Timeout watchdog listener
  const [timeoutWarning, setTimeoutWarning] = useState<{ reqId: number; action: string; file: string; timeout: number } | null>(null);
  useState(() => {
    if (api?.onTimeoutWarning && api?.respondTimeout) {
      api.onTimeoutWarning((info: any) => {
        setTimeoutWarning(info);
      });
    }
  });

  const onAddFiles = useCallback(async () => {
    if (!api) { alert("未连接到后端。请通过 Electron 运行此应用。"); return; }
    const paths: string[] = await api.openFile();
    for (const p of paths) {
      const id = nextId; setNextId(n => n + 1); setNextId(prev => { const nid = prev; return nid; });
      setFiles(prev => [...prev, { id, name: p.split(/[\\/]/).pop()!, path: p, size: 0, isDir: false, ext: p.slice(p.lastIndexOf(".")) || "" }]);
    }
  }, []);

  const onDropFiles = useCallback((paths: string[]) => {
    let nid = nextId;
    const newFiles: FileEntry[] = [];
    for (const p of paths) {
      newFiles.push({ id: nid++, name: p.split(/[\\/]/).pop()!, path: p, size: 0, isDir: false, ext: p.slice(p.lastIndexOf(".")) || "" });
    }
    setNextId(nid);
    setFiles(prev => [...prev, ...newFiles]);
  }, [nextId]);

  const onAddFolder = useCallback(async () => {
    if (!api) return;
    const paths: string[] = await api.openDirectory();
    for (const p of paths) {
      const id = nextId; setNextId(id + 1);
      setFiles(prev => [...prev, { id, name: p.split(/[\\/]/).pop()! + "/", path: p, size: 0, isDir: true, ext: "folder" }]);
    }
  }, [nextId]);

  const onRemove = useCallback((id: number) => setFiles(p => p.filter(f => f.id !== id)), []);

  const onCompress = useCallback(async () => {
    if (!api || files.length === 0) return;
    setCompressing(true); setToast("");
    const dir = outputDir || files[0].path.replace(/[\\/][^\\/]+$/, "");
    for (const f of files) {
      const out = dir + "\\" + (f.isDir ? f.name.replace(/\/$/, "") : f.name) + ".hcf";
      try {
        const r = await api.compress(f.path, out, 6);
        if (!r.success) { setToast("压缩失败: " + (r.stderr || r.stdout)); break; }
      } catch (e: any) { setToast("压缩出错: " + e.message); break; }
    }
    setCompressing(false); setToast("压缩完成！ → " + dir);
    setFiles([]);
  }, [files, outputDir]);

  const [bombAlert, setBombAlert] = useState<{ file: string; msg: string } | null>(null);

  const onDecompress = useCallback(async () => {
    if (!api || files.length === 0) return;
    setCompressing(true); setToast(""); setBombAlert(null);
    const dir = outputDir || files[0].path.replace(/[\\/][^\\/]+$/, "");
    let gotBomb = false;
    for (const f of files) {
      let outName: string;
      const extPat = /\.(hcf|gz|bz2|xz|zip|7z|rar|zst|zstd|br|lz4|tar(\.(gz|bz2|xz|zst))?)$/i;
      if (extPat.test(f.name))
        outName = f.name.replace(extPat, "");
      else outName = f.name + ".out";
      const out = dir + "\\" + outName;
      try {
        const r = await api.decompress(f.path, out);
        if (!r.success) {
          if (r.bombDetected) {
            setBombAlert({ file: f.name, msg: r.stderr }); gotBomb = true;
          } else {
            setToast("解压失败: " + (r.stderr || r.stdout));
          }
          break;
        }
      } catch (e: any) { setToast("解压出错: " + e.message); break; }
    }
    setCompressing(false);
    if (!gotBomb) { setToast("解压完成！ → " + dir); setFiles([]); }
  }, [files, outputDir]);

  const isDecomp = nav === "decompress";
  const actionLabel = isDecomp ? "⚡ 开始解压" : "⚡ 开始压缩";
  const actionFn = isDecomp ? onDecompress : onCompress;

  const showToolbar = nav === "compress" || nav === "decompress";

  return (
    <>
      <Sidebar active={nav} onNav={setNav} pluginCount={pluginCount} subCount={subCount} onRefreshPlugins={refreshPluginCount} />
      <main className="main">
        {showToolbar && (
          <div className="toolbar">
            <div className="path" style={{ cursor: "pointer" }} onClick={async () => {
              if (api) { const dirs = await api.openDirectory(); if (dirs.length) setOutputDir(dirs[0]); }
            }} title="点击选择输出目录">
              {outputDir ? `📂 输出到: ${outputDir}` : "📂 点击选择输出目录（默认同源文件目录）"}
            </div>
            <button className="btn btn-outline" onClick={onAddFiles}>📄 添加文件</button>
            <button className="btn btn-outline" onClick={onAddFolder}>📁 添加文件夹</button>
            <button className="btn btn-primary" onClick={actionFn} disabled={files.length === 0}>
              {actionLabel}
            </button>
            <button className="btn btn-ghost" onClick={() => setShowSettings(true)} title="设置">⚙️</button>
          </div>
        )}
        <div className="content">
          {nav === "compress" || nav === "decompress" ? (
            <>
              <DropZone onAdd={onAddFiles} onDropFiles={onDropFiles} />
              <FileTable files={files} onRemove={onRemove} />
              {compressing && <Prog pct={50} isDecomp={isDecomp} />}
            </>
          ) : nav === "browser" ? (
            <ArchiveBrowser />
          ) : nav === "store" ? (
            <PluginStore />
          ) : nav === "plugins" ? (
            <PluginManager key={pluginKey} />
          ) : null}
        </div>
      </main>
      {showSettings && <SettingsModal mode={mode} setMode={setMode} onClose={() => setShowSettings(false)} />}
      {timeoutWarning && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 440, borderColor: "rgba(229,179,60,.4)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <span style={{ fontSize: "2em" }}>⏳</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: "1.1em", color: "var(--yellow)" }}>{timeoutWarning.action}超时警告</div>
                <div style={{ fontSize: ".85em", color: "var(--muted)" }}>
                  文件: {timeoutWarning.file.split(/[\\/]/).pop()} &nbsp;·&nbsp;
                  已超过 {Math.round(timeoutWarning.timeout / 1000)}s 阈值
                </div>
              </div>
            </div>
            <div style={{ fontSize: ".85em", color: "var(--muted)", lineHeight: 1.6, marginBottom: 16 }}>
              {timeoutWarning.action}操作响应时间异常。<br />
              请选择继续等待或终止操作。
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-outline" onClick={() => {
                api.respondTimeout(timeoutWarning.reqId, "abort");
                setTimeoutWarning(null);
              }} style={{ color: "var(--red)" }}>终止操作</button>
              <button className="btn btn-primary" onClick={() => {
                api.respondTimeout(timeoutWarning.reqId, "continue");
                setTimeoutWarning(null);
              }}>继续等待</button>
            </div>
          </div>
        </div>
      )}
      {bombAlert && (
        <div className="modal-overlay" onClick={() => setBombAlert(null)}>
          <div className="modal" style={{ maxWidth: 500, borderColor: "rgba(229,83,91,.4)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <span style={{ fontSize: "2em" }}>🛡️</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: "1.1em", color: "var(--red)" }}>插件拦截 — 操作被阻止</div>
                <div style={{ fontSize: ".85em", color: "var(--muted)" }}>
                  文件: {bombAlert.file} &nbsp;·&nbsp;
                  在「🔌 插件」面板中可管理拦截规则
                </div>
              </div>
            </div>
            <div style={{ fontSize: ".82em", color: "var(--muted)", lineHeight: 1.6, whiteSpace: "pre-wrap", maxHeight: 200, overflowY: "auto", background: "var(--bg)", padding: 10, borderRadius: 8 }}>
              {bombAlert.msg}
            </div>
            <div style={{ marginTop: 16, display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-outline" onClick={() => setBombAlert(null)}>知道了</button>
              <button className="btn btn-outline" onClick={() => { setBombAlert(null); setNav("plugins"); }}>🔌 管理插件</button>
            </div>
          </div>
        </div>
      )}
      <Toast msg={toast} />
    </>
  );
}
