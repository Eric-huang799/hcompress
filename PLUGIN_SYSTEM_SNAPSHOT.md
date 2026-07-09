# 插件系统改造前快照

> 生成时间: 2026-07-08
> 目的: 记录改造前的完整状态，改坏了可以从此文档恢复

---

## 涉及文件清单（改造范围）

| 文件 | 类型 | 说明 |
|------|------|------|
| `hcompress/plugins/registry.py` | 修改 | PluginRegistry — 核心注册中心 |
| `hcompress/plugins/sdk/base.py` | 修改 | 10个 Base* 无操作基类 |
| `hcompress/plugins/sdk/scaffold.py` | 修改 | 脚手架生成器 |
| `hcompress/plugins/builtin/bomb_guard.py` | 修改 | BombGuardPlugin |
| `hcompress/plugins/builtin/parallel_compress.py` | 修改 | ParallelCompressPlugin |
| `hcompress/plugins/builtin/hello_plugin.py` | 修改 | HelloPlugin |
| `hcompress/engine.py` | 修改 | 引擎层（_safe_call + 字符串匹配） |
| `hcompress/cli.py` | 修改 | CLI plugin list 命令 |
| `hcompress/plugins/manifest.py` | **新建** | PluginMeta 元信息数据类 |

## 不改动的文件

| 文件 | 原因 |
|------|------|
| `hcompress/interfaces/*.py` (10个ABC) | 接口层保持不变，向前兼容 |
| `hcompress/format.py` | HCF 格式不变，extension JSON 逻辑不变 |
| `hcompress/plugins/builtin/formats/__init__.py` | 13种格式解压不变 |
| `hcompress/plugins/__init__.py` | 只导出 PluginRegistry，不变 |
| `tests/*.py` | 测试文件，最后运行验证 |
| `hcompress-v2/*` | v2 Electron 端，IPC 调用方式微调 |
| `hcompress-android/*` | 不管 |

---

## 当前状态详细记录

### 1. registry.py 当前行为

```
_init_:_plugins = {cat: [] for cat in 11 categories}
_init_:_loaded_paths = set()
discover(paths): 扫描目录 → _load_file → _scan_module → 返回 count
discover_builtin(): 加载 builtin/ 下的 .py 文件
register(instance): 手动注册，isinstance 匹配
get_codecs/transforms/filters/...: 返回 list 浅拷贝
get_all(): 返回 {cat: list(instances)}  — 不能直接 JSON 序列化

_load_file(path):
  1. 去重检查 _loaded_paths
  2. importlib.util.spec_from_file_location(module_name, path)
  3. spec.loader.exec_module(module)
  4. _scan_module(module)
  5. 异常 → traceback.print_exc()

_scan_module(module):
  1. for name in dir(module):
  2. obj = getattr(module, name)
  3. 跳过非 type
  4. 跳过 obj.__module__ != module.__name__ (防止导入类重复注册)
  5. for iface_cls, category in _INTERFACE_MAP.values():
  6. issubclass(obj, iface_cls) and obj is not iface_cls → obj() → append
  7. 构造失败 → pass (静默跳过)
```

### 2. 引擎层当前行为

```
_merge_registry(config):
  - 取出 config.registry (PluginRegistry)
  - CompressConfig: 注入 entropy_coder, checksum, transforms, filters,
    block_splitter, io_backend, hooks(compress_hook), observers, extensions
  - DecompressConfig: 注入 checksum, io_backend, hooks(decompress_hook),
    observers, extensions
  - 显式配置的优先，registry 的追加

引擎中的硬编码字符串匹配 (需要干掉):
  engine.py:218: type(hook).__name__ == "ParallelCompressPlugin"
  engine.py:232: type(hook).__name__ == "ParallelCompressPlugin"

_safe_call: 吞掉除 RuntimeError/ValueError 外的所有异常，打印到 stderr
_safe_call_data: 同上，返回 fallback
_safe_call_bool: 同上，返回 True
```

### 3. SDK base.py 当前行为

```
10个Base类，每个对应一个接口:
  BaseCodec(IEntropyCodec)
  BaseTransform(ITransform) — forward/reverse pass-through
  BaseFilter(IFilter) — apply/revert pass-through
  BaseMatchFinder(IMatchFinder) — 返回空列表
  BaseChecksum(IChecksum) — compute 抛 NotImplementedError
  BaseIOBackend(IIOBackend) — open/read/write 默认文件操作
  BaseBlockSplitter(IBlockSplitter) — 单块
  BaseCompressHook(ICompressHook) — 全部 pass
  BaseDecompressHook(IDecompressHook) — on_header_read 返回 True
  BaseObserver(IObserver) — 全部 pass
  BaseExtension(IExtension) — 全部 no-op, extension_id="com.example.unnamed"

所有类都是无参构造器（构造器不需要参数）
```

### 4. 内置插件当前行为

BombGuardPlugin(IDecompressHook):
  - __init__(self, max_ratio=100, max_depth=5)
  - on_start: 嵌套深度计数+1，超限抛 BombDetectedError
  - on_header_read: 膨胀比 > max_ratio → 抛异常
  - on_done/on_error: 深度计数器恢复
  - 类级变量 _depth 跨实例共享

ParallelCompressPlugin(BaseCompressHook):
  - on_start: 文件>256KB → ctx._parallel_enabled=True, ctx._parallel_workers=4
  - on_done: 打印完成信息

HelloPlugin(BaseDecompressHook):
  - on_start: print 开始信息
  - on_done: print 完成信息

### 5. scaffold.py 当前行为

支持5种类型模板:
  decompress-hook → BaseDecompressHook
  compress-hook → BaseCompressHook
  extension → BaseExtension
  checksum → BaseChecksum
  transform → BaseTransform

不支持:
  codec, filter, matchfinder, io_backend, block_splitter, observer

scaffold(name, type, output_dir):
  1. kebab-case name → PascalCase ClassName
  2. 根据 type 选模板
  3. 生成 .py 文件

### 6. cli.py plugin list 当前行为

```
hcompress plugin list:
  1. 显示5种插件类型表格
  2. PluginRegistry().discover_builtin()
  3. 遍历 get_all()，打印 type(p).__name__
```

### 7. v2 main.cjs listPlugins 当前行为

```
内联 Python 脚本:
  reg = PluginRegistry()
  reg.discover_builtin()
  all_p = reg.get_all()
  for cat, lst in all_p.items():
      for p in lst:
          name = type(p).__name__
          result[name] = {"type": cat, "enabled": True}
  print(json.dumps(result))
```
这是把 Python 对象的 type name 手动包装成 JSON

---

## 改造后的目标行为

1. **PluginMeta** 数据类: name, version, author, description, priority, enabled, plugin_type
2. **registry**: enable/disable 按 name 查找, get_all() 返回可序列化 dict, reload() 热重载
3. **base**: 每个 Base 类有 `meta: ClassVar[PluginMeta]` 默认值
4. **engine**: 用 hasattr 检查接口方法代替 type().__name__ 字符串; _safe_call 加 verbose 参数
5. **builtins**: 加上 meta 属性
6. **scaffold**: 补齐 10 种类型; 生成带 meta 的代码
7. **cli**: plugin list 用新的 get_all() 序列化输出
