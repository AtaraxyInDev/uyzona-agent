#!/usr/bin/env python3
"""Uy Zona Agent - agente TUI ligero para LLMs locales (Windows).
pip install rich prompt_toolkit   (opcional: pillow -> reduce imagenes)
Backends: llama.cpp (llama-server), LM Studio, Ollama, cualquier /v1 OpenAI-compatible.
Uso:  @archivo|imagen   $skill   #mcp   /comandos   (Esc+Enter = nueva linea)"""
import os, sys, re, json, ast, io, time, base64, difflib, subprocess, shutil, atexit, threading, tempfile
import urllib.request, urllib.error, glob as G
from html import escape
try:
    from rich.console import Console, Group
    from rich.markdown import Markdown, Heading, CodeBlock
    from rich.segment import Segment
    from rich.style import Style as RStyle
    from rich.measure import Measurement
    from rich.padding import Padding
    from rich.align import Align
    from rich.syntax import Syntax
    from rich.table import Table
    from rich import box
    from rich.live import Live
    from rich.text import Text
    from rich.rule import Rule
    from rich.panel import Panel
    from rich.theme import Theme
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.styles import Style, DynamicStyle
except ImportError:
    sys.exit("Falta: pip install rich prompt_toolkit")
try: sys.stdout.reconfigure(encoding="utf8"); sys.stdin.reconfigure(encoding="utf8")
except Exception: pass

# ------------------------------------------------------------------ config
H = os.path.expanduser("~/.uyzona"); CFG = H + "/config.json"; SK = H + "/skills"
MD = H + "/mcp"
os.makedirs(SK, exist_ok=True); os.makedirs(MD, exist_ok=True)
D = {"url": "http://127.0.0.1:8080/v1", "model": "", "think": True, "think_budget": 0, "sampler": {}, "vis": None, "models": {}, "vscode_diff": "auto", "ctx_manual": 0, "temp": 0.7, "auto": False,
     "theme": "tokyo", "themes": {}, "paste_lines": 3, "think_view": "tail", "compact_at": 0.8, "tool_max": 5000, "img_max": 1024,
     "mcp": {}}  # mcp: {"nombre": {"cmd": "npx -y pkg args", "env": {}}}
cfg = dict(D)
if os.path.exists(CFG):
    try: cfg.update(json.load(open(CFG, encoding="utf8")))
    except Exception: pass
cfg.pop("ctx", None)  # clave vieja (v1) que tapaba el ctx del backend
if cfg.pop("show_think", False): cfg["think_view"] = "full"
PROF = ("think", "think_budget", "ctx_manual", "sampler", "vis")   # ajustes que viven POR MODELO
DEFP = {"think": True, "think_budget": 0, "ctx_manual": 0, "sampler": {}, "vis": None}
_loaded = [None]
def apply_profile(name):
    """Carga los ajustes guardados de ese modelo (o los de fábrica si es nuevo)."""
    if not name or _loaded[0] == name: return
    if not cfg["models"] and _loaded[0] is None:       # primera vez tras actualizar: hereda lo que hubiera
        p = {k: cfg.get(k, DEFP[k]) for k in PROF}; p["think_budget"] = 0
    else: p = cfg["models"].get(name, {})
    for k in PROF: cfg[k] = dict(p.get(k, {})) if k == "sampler" else p.get(k, DEFP[k])
    _loaded[0] = name
def save():
    if cfg.get("model") and _loaded[0] == cfg["model"]: cfg["models"][cfg["model"]] = {k: cfg[k] for k in PROF}
    json.dump(cfg, open(CFG, "w", encoding="utf8"), indent=1, ensure_ascii=False)
THEMES = {  # todos oscuros
    "tokyo": dict(acc="#7dcfff", mod="#bb9af7", tl="#e0af68", ok="#9ece6a", er="#f7768e", mu="#6b7398", dm="#414868",
                  add="#9ece6a on #1a2b1f", dl="#f7768e on #2b1a20", h1="#7dcfff", h2="#bb9af7", h3="#c0caf5",
                  bar="#16161e", barfg="#787c99", menu="#1a1b26", sel="#3d59a1", code="one-dark",
                  skill="#ff9e64", mcp="#bb9af7", link="#7aa2f7", path="#73daca", user="#7dcfff"),
    "dracula": dict(acc="#8be9fd", mod="#bd93f9", tl="#f1fa8c", ok="#50fa7b", er="#ff5555", mu="#7082b6", dm="#44475a",
                    add="#50fa7b on #16301e", dl="#ff5555 on #351a1e", h1="#ff79c6", h2="#bd93f9", h3="#f8f8f2",
                    bar="#191a21", barfg="#8b8fa8", menu="#21222c", sel="#44475a", code="dracula",
                    skill="#ffb86c", mcp="#ff79c6", link="#8be9fd", path="#50fa7b", user="#bd93f9"),
    "gruvbox": dict(acc="#83a598", mod="#d3869b", tl="#fabd2f", ok="#b8bb26", er="#fb4934", mu="#928374", dm="#665c54",
                    add="#b8bb26 on #262a12", dl="#fb4934 on #3a1a14", h1="#fabd2f", h2="#fe8019", h3="#ebdbb2",
                    bar="#1d2021", barfg="#a89984", menu="#282828", sel="#504945", code="gruvbox-dark",
                    skill="#fe8019", mcp="#d3869b", link="#83a598", path="#8ec07c", user="#fabd2f"),
    "nord": dict(acc="#88c0d0", mod="#b48ead", tl="#ebcb8b", ok="#a3be8c", er="#bf616a", mu="#6c7a96", dm="#434c5e",
                 add="#a3be8c on #1f2b22", dl="#bf616a on #2e1e22", h1="#88c0d0", h2="#81a1c1", h3="#e5e9f0",
                 bar="#242933", barfg="#7b88a1", menu="#2e3440", sel="#434c5e", code="nord",
                 skill="#d08770", mcp="#b48ead", link="#81a1c1", path="#8fbcbb", user="#88c0d0"),
    "mono": dict(acc="#d0d0d0", mod="#ffffff", tl="#bcbcbc", ok="#a8a8a8", er="#d78787", mu="#767676", dm="#4e4e4e",
                 add="#d0d0d0 on #262626", dl="#8a8a8a on #1c1c1c", h1="#ffffff", h2="#d0d0d0", h3="#bcbcbc",
                 bar="#121212", barfg="#808080", menu="#1c1c1c", sel="#3a3a3a", code="native",
                 skill="#ffffff", mcp="#bcbcbc", link="#ffffff", path="#d0d0d0", user="#d0d0d0"),
}
BUILTIN = set(THEMES); TD = H + "/themes"; os.makedirs(TD, exist_ok=True)
def fill(t):  # claves que falten en un tema propio
    t = dict(t)
    for k, v in {"skill": "tl", "mcp": "mod", "link": "acc", "path": "ok", "user": "acc"}.items(): t.setdefault(k, t.get(v, "#ffffff"))
    return t
def load_themes():
    """Temas propios: ~/.uyzona/themes/<nombre>.json  y/o  "themes" en config.json.
    Lo que no definas se hereda de "base" (por defecto tokyo)."""
    for n in [k for k in THEMES if k not in BUILTIN]: THEMES.pop(n)
    extra = dict(cfg.get("themes") or {})
    for f in sorted(G.glob(TD + "/*.json")):
        try: extra[os.path.basename(f)[:-5]] = json.load(open(f, encoding="utf8"))
        except Exception as e: sys.stderr.write("tema inválido %s: %s\n" % (f, e))
    for n, t in extra.items():
        if isinstance(t, dict): THEMES[n] = fill({**THEMES.get(t.get("base", "tokyo"), THEMES["tokyo"]), **{k: v for k, v in t.items() if k not in ("base",) and not k.startswith("_")}})
TH, CODE, STY, con = {}, "monokai", None, None
def set_theme(name):
    global con, STY, CODE, TH
    t = fill(THEMES.get(name) or THEMES["tokyo"])
    st = {"t.acc": t["acc"], "t.accb": "bold " + t["acc"], "t.mod": t["mod"], "t.modb": "bold " + t["mod"], "t.tl": t["tl"], "t.tlb": "bold " + t["tl"],
          "t.ok": t["ok"], "t.er": t["er"], "t.mu": t["mu"], "t.dm": t["dm"], "t.thk": "italic " + t["mu"],
          "t.add": t["add"], "t.del": t["dl"], "t.h1": "bold " + t["h1"], "t.h2": "bold " + t["h2"], "t.h3": "bold " + t["h3"],
          "t.skill": "bold " + t["skill"], "t.mcp": "bold " + t["mcp"], "t.link": t["link"] + " underline", "t.path": t["path"] + " underline", "t.user": t["user"],
          "markdown.code": "%s on %s" % (t["tl"], t["menu"]), "markdown.link": t["link"] + " underline", "markdown.link_url": t["mu"],
          "markdown.item.bullet": t["mod"], "markdown.item.number": t["mod"], "markdown.hr": t["dm"],
          "markdown.block_quote": "italic " + t["mu"]}
    try:
        new = Console(highlight=False, theme=Theme(st))
        sty = Style.from_dict({"bottom-toolbar": "bg:%s %s" % (t["bar"], t["barfg"]), "bottom-toolbar.text": "bg:%s %s" % (t["bar"], t["barfg"]),
                               "completion-menu": "bg:%s #d0d0d0" % t["menu"], "completion-menu.completion.current": "bg:%s #ffffff" % t["sel"],
                               "completion-menu.meta.completion": "bg:%s %s" % (t["menu"], t["mu"]),
                               "completion-menu.meta.completion.current": "bg:%s #d0d0ff" % t["sel"],
                               "pr": "bold " + t["acc"], "cwd": "bold " + t["acc"], "tbok": t["ok"], "tbwarn": t["tl"], "tberr": t["er"],
                               "rl": t["dm"], "rlt": "bold " + t["acc"], "placeholder": "italic " + t["mu"], "pst": "bold " + t["tl"], "msk": "bold " + t["skill"], "mmc": "bold " + t["mcp"], "mpa": t["path"]})
    except Exception as e:
        sys.stderr.write("tema '%s' inválido (%s): usando tokyo\n" % (name, e))
        if name != "tokyo": return set_theme("tokyo")
        raise
    TH, CODE, con, STY = t, t["code"], new, sty
load_themes(); set_theme(cfg.get("theme", "tokyo"))
INFO = {"be": "?", "models": [], "ctx": None, "vis": None}
ST = {"used": 0, "p": 0, "g": 0, "tps": 0.0, "comp": 0, "saved": 0}
def CTX(): return int(cfg["ctx_manual"] or INFO["ctx"] or 8192)
def kf(n): n = int(n); return "%.1fk" % (n / 1000) if n >= 1000 else str(n)
def ROOT():
    u = cfg["url"].rstrip("/")
    return u[:-3] if u.endswith("/v1") else u
def BASE(): return ROOT() + "/v1"

# ------------------------------------------------------------------ backend
def jget(url, body=None, t=4):
    try:
        rq = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                                    {"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(rq, timeout=t).read())
    except Exception: return None

def probe():
    """Detecta backend, modelos, contexto real y vision consultando al servidor."""
    r, m = ROOT(), []
    INFO.update(be="openai", models=[], ctx=None, vis=None, slots=None)
    p = jget(r + "/props")
    if p and "default_generation_settings" in p:                      # llama.cpp
        INFO["be"] = "llama.cpp"; INFO["ctx"] = p["default_generation_settings"].get("n_ctx")
        INFO["vis"] = bool(p["modalities"].get("vision")) if isinstance(p.get("modalities"), dict) and "vision" in p["modalities"] else None
        INFO["slots"] = p.get("total_slots")
        m = [x["id"] for x in (jget(r + "/v1/models") or {}).get("data", [])]
    else:
        d = jget(r + "/api/v0/models")
        if d and "data" in d:                                          # LM Studio
            rows = [x for x in d["data"] if x.get("type") != "embeddings"]
            INFO["be"] = "lmstudio"; m = [x["id"] for x in rows]
            cur = next((x for x in rows if x["id"] == cfg["model"]), None) or \
                next((x for x in rows if x.get("state") == "loaded"), None)
            if cur:
                INFO["ctx"] = cur.get("loaded_context_length") or cur.get("max_context_length")
                INFO["vis"] = cur.get("type") == "vlm"
        else:
            t = jget(r + "/api/tags")
            if t and "models" in t:                                    # Ollama
                INFO["be"] = "ollama"; m = [x["name"] for x in t["models"]]
                ps = jget(r + "/api/ps") or {}
                row = next((x for x in ps.get("models", []) if x["name"] == cfg["model"]), None)
                if row: INFO["ctx"] = row.get("context_length")
                if cfg["model"]:
                    sh = jget(r + "/api/show", {"model": cfg["model"]})
                    if sh:
                        INFO["vis"] = "vision" in sh.get("capabilities", [])
                        if not INFO["ctx"]:
                            INFO["ctx"] = next((v for k, v in sh.get("model_info", {}).items()
                                                if k.endswith(".context_length")), None)
            else:
                m = [x["id"] for x in (jget(r + "/v1/models") or {}).get("data", [])]
    INFO["models"] = m
    if m and cfg["model"] not in m:
        cfg["model"] = m[0]
        if INFO["be"] in ("lmstudio", "ollama"): probe()
    apply_profile(cfg["model"])

def detect_vision(force=False):
    """Si /props no lo dice, prueba con una imagen de 64x64 (max_tokens=1) y guarda el resultado por modelo."""
    if not force and INFO["vis"] is not None: return
    if not force and cfg.get("vis") is not None: INFO["vis"] = cfg["vis"]; return
    if not cfg["model"]: return
    import zlib, struct
    con.print(Text("  detectando visión…", style="t.mu"))
    w = 64; raw = b"".join(b"\0" + b"\x80\x80\x80" * w for _ in range(w))
    def ch(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, w, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b"")
    try:
        api("/chat/completions", {"model": cfg["model"], "stream": False, "max_tokens": 1, "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False}, "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}},
                {"type": "text", "text": "ok"}]}]}).read()
        v = True
    except RuntimeError as e: v = False if re.search(r"image|multimodal|mmproj|vision|modalit", str(e), re.I) else None
    except Exception: v = None
    INFO["vis"] = v
    if v is not None: cfg["vis"] = v; save()

def api(path, body):
    rq = urllib.request.Request(BASE() + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try: return urllib.request.urlopen(rq, timeout=900)
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %d: %s" % (e.code, e.read().decode("utf8", "replace")[:300]))

def llm(prompt, system="Be concise.", think=False):
    r = api("/chat/completions", {"model": cfg["model"], "stream": False, "temperature": 0.3,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "chat_template_kwargs": {"enable_thinking": think}})
    s = json.loads(r.read())["choices"][0]["message"]["content"] or ""
    return re.sub(r"(?s)^.*?</think>", "", s).strip()

# ------------------------------------------------------------------ tools
def T(n, d, p, req):
    return {"type": "function", "function": {"name": n, "description": d, "parameters": {
        "type": "object", "properties": {k: {"type": v[0], "description": v[1]} for k, v in p.items()},
        "required": req}}}
TOOLS = [
    T("sh", "Run ONE PowerShell command on Windows; returns output and exit code. Use for git, builds, installs, "
      "running scripts. Do not use it to read or edit files.",
      {"cmd": ("string", "PowerShell command"), "timeout": ("integer", "seconds, default 60")}, ["cmd"]),
    T("read", "Read a text file with line numbers. Always read before editing.",
      {"path": ("string", "file path"), "offset": ("integer", "first line, 1-based, default 1"),
       "limit": ("integer", "max lines, default 200")}, ["path"]),
    T("write", "Create a new file or fully overwrite one. For small changes to existing files use edit.",
      {"path": ("string", "file path"), "content": ("string", "full file content")}, ["path", "content"]),
    T("edit", "Replace text in an existing file. 'old' = a SHORT unique snippet (1-5 lines) copied from read WITHOUT line "
      "numbers. On error nothing was changed.",
      {"path": ("string", "file path"), "old": ("string", "exact text to replace"),
       "new": ("string", "replacement text"), "all": ("boolean", "replace every match")}, ["path", "old", "new"]),
    T("grep", "Recursive regex search in files. Returns file:line:text.",
      {"pattern": ("string", "regex"), "path": ("string", "directory, default ."),
       "glob": ("string", "file glob, default *")}, ["pattern"]),
    T("glob", "List files matching a glob pattern, e.g. src/**/*.py", {"pattern": ("string", "glob")}, ["pattern"]),
    T("fetch", "HTTP GET a URL and return readable text.", {"url": ("string", "http(s) url")}, ["url"]),
    T("mcp", "Call a tool of an MCP server that the user loaded with #name. Its tools are listed in that message.",
      {"server": ("string", "server name"), "tool": ("string", "tool name"),
       "args": ("object", "tool arguments")}, ["server", "tool"]),
    T("mcp_add", "Register a global MCP server. Without cmd: scaffolds a Python server at ~/.uyzona/mcp/NAME/server.py that you then "
      "edit (add functions with @tool('desc', param='type')). With cmd: registers an external server, e.g. 'npx -y pkg'. "
      "The user activates it by mentioning #NAME.", {"name": ("string", "lowercase-with-dashes"), "cmd": ("string", "shell command; omit to scaffold a Python server")}, ["name"]),
    T("theme_save", "Create or update a custom color theme for this TUI and apply it instantly. colors={key:'#rrggbb'}: "
      "acc(accent/prompt) mod(model name) tl(tool calls) ok er(error) mu(muted text) dm(borders/separators) h1 h2 h3(headings) "
      "skill mcp link path user(user bubble border) bar(status bar bg) barfg(status bar text) menu(autocomplete bg) sel(selected item bg) "
      "add dl('#fg on #bg' diff lines) code(pygments style name). Dark themes; omitted keys inherit from base (default tokyo).",
      {"name": ("string", "lowercase-with-dashes; built-in names are reserved"), "colors": ("object", "key -> hex color"),
       "base": ("string", "theme to inherit from"), "apply": ("boolean", "apply now, default true")}, ["name", "colors"]),
    T("skill_save", "Create or overwrite a global skill (reusable instructions). Only when the user asks for it.",
      {"name": ("string", "lowercase-with-dashes"), "description": ("string", "one line: what it does / when to use"),
       "body": ("string", "markdown instructions")}, ["name", "description", "body"]),
]
SCH = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}
def sig(n):
    p = SCH[n]
    return n + "(" + ", ".join(k + ("" if k in p["required"] else "?") + ": " + v["type"]
                               for k, v in p["properties"].items()) + ")"

def parse_args(s):
    if isinstance(s, dict): return s
    s = (s or "").strip() or "{}"
    for f in (json.loads, lambda x: json.loads(re.sub(r",\s*$", "", x) + "}"), lambda x: json.loads(re.sub(r",\s*}", "}", x)),
              ast.literal_eval):
        try:
            v = f(s)
            if isinstance(v, dict): return v
        except Exception: pass
    return None

def check(n, a):
    if n not in SCH: return "error: unknown tool '%s'. Available: %s" % (n, ", ".join(SCH))
    p = SCH[n]
    for k in list(a):
        if k not in p["properties"]: a.pop(k)
    for k in p["required"]:
        if k not in a: return "error: missing '%s'. Usage: %s" % (k, sig(n))
    for k, v in a.items():
        t = p["properties"][k]["type"]
        try:
            if t == "integer": a[k] = int(v)
            elif t == "boolean": a[k] = v if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")
            elif t == "object" and isinstance(v, str): a[k] = json.loads(v)
            elif t == "string" and not isinstance(v, str): a[k] = json.dumps(v, ensure_ascii=False)
        except Exception: return "error: bad type for '%s'. Usage: %s" % (k, sig(n))
    return None

def clip(s, n=None):
    s = str(s); n = n or cfg["tool_max"]
    return s if len(s) <= n else s[:n * 2 // 3] + "\n...[cut %d chars]...\n" % (len(s) - n) + s[-n // 3:]

SAFE = re.compile(r"^\s*(ls|dir|pwd|cat|type|echo|gc|tree|where|Get-(ChildItem|Content|Location|Item|Date)|"
                  r"git\s+(status|log|diff|branch|show)|python\s+(-V|--version))\b", re.I)
def allow(kind):
    if cfg["auto"]: return True
    a = con.input("[t.tl]  ? permitir %s[/] [t.mu](Enter=si / n / a=siempre)[/] " % kind).strip().lower()
    if a == "a": cfg["auto"] = True
    return a in ("", "y", "s", "a")

def rd(p):
    raw = open(p, "rb").read()
    if b"\0" in raw[:4096]: raise ValueError("binary file (images: drag them into the prompt)")
    return raw.decode("utf8", "replace").replace("\r\n", "\n"), ("\r\n" if b"\r\n" in raw else "\n")
def wr(p, s, nl="\n"):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    open(p, "w", encoding="utf8", newline="").write(s.replace("\n", nl))

def show_diff(p, old, new):
    ud = list(difflib.unified_diff(old.split("\n"), new.split("\n"), lineterm="", n=2))[2:]
    add = sum(1 for l in ud if l.startswith("+")); rem = sum(1 for l in ud if l.startswith("-"))
    t, ln = Text(), 0
    for l in ud[:100]:
        if l.startswith("@@"):
            ln = int(re.search(r"\+(\d+)", l).group(1)); t.append(l + "\n", style="t.mu")
        elif l.startswith("+"): t.append("%4d + %s\n" % (ln, l[1:]), style="t.add"); ln += 1
        elif l.startswith("-"): t.append("     - %s\n" % l[1:], style="t.del")
        else: t.append("%4d   %s\n" % (ln, l[1:]), style="t.mu"); ln += 1
    if len(ud) > 100: t.append("… +%d líneas\n" % (len(ud) - 100), style="t.mu")
    con.print(Panel(t if ud else Text("sin cambios", style="t.mu"), title="%s  [t.ok]+%d[/] [t.er]-%d[/]" % (p, add, rem),
                    title_align="left", border_style="t.dm", padding=(0, 1)))

def open_vscodium_diff(path, old_content, new_content):
    """Abre el diff nativo de VSCodium/VS Code (codium --diff o code --diff)."""
    mode = cfg.get("vscode_diff", "auto")                     # auto | on | off
    inside = os.environ.get("TERM_PROGRAM") == "vscode" or any(k in os.environ for k in ("VSCODE_PID", "VSCODE_IPC_HOOK_CLI", "VSCODE_INJECTION"))
    if mode == "off" or (mode != "on" and not inside): return
    editor = shutil.which("codium") or shutil.which("code")
    if not editor or old_content == new_content:
        return
    try:
        fd, old_tmp = tempfile.mkstemp(suffix=".old", prefix="uyzona-")
        with os.fdopen(fd, "w", encoding="utf8", newline="") as f:
            f.write(old_content)
        # El archivo real ya tiene el contenido nuevo
        subprocess.Popen([editor, "--diff", old_tmp, path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Limpieza diferida del temp
        def _cleanup(p=old_tmp):
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass
        threading.Timer(60, _cleanup).start()
    except Exception:
        pass

def t_sh(a):
    c = a["cmd"]
    if not SAFE.match(c) and not allow("sh"): return "denied by user"
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps: return "error: PowerShell not found"
    script = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8;$ProgressPreference='SilentlyContinue';" + c +
              "\n;Write-Output ('__CWD__' + (Get-Location).Path + '|' + $LASTEXITCODE)")
    try:
        r = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-Command", "-"], input=script, capture_output=True,
                           text=True, encoding="utf8", errors="replace", timeout=a.get("timeout", 60))
    except subprocess.TimeoutExpired: return "error: timeout after %ss" % a.get("timeout", 60)
    out = r.stdout + r.stderr
    m = re.search(r"__CWD__(.*)\|(\d*)\s*$", out)
    note = ""
    if m:
        out = out[:m.start()]
        if m.group(2) not in ("", "0"): note += "\n[exit %s]" % m.group(2)
        if os.path.normcase(m.group(1)) != os.path.normcase(os.getcwd()) and os.path.isdir(m.group(1)):
            os.chdir(m.group(1)); note += "\n[cwd: %s]" % m.group(1)
    return clip(out.strip() or "(no output)") + note

def t_read(a):
    L = rd(a["path"])[0].split("\n"); o = max(1, a.get("offset", 1)); n = a.get("limit", 200)
    out = "\n".join("%d\t%s" % (i, x) for i, x in enumerate(L[o - 1:o - 1 + n], o))
    return clip(out, cfg["tool_max"] * 2) + ("\n[lines %d-%d of %d]" % (o, min(o + n - 1, len(L)), len(L))
                                             if o > 1 or len(L) > o - 1 + n else "")

def t_write(a):
    p = a["path"]
    old, nl = rd(p) if os.path.exists(p) else ("", "\n")
    show_diff(p, old, a["content"])
    if not allow("write"): return "denied by user"
    wr(p, a["content"], nl)
    open_vscodium_diff(p, old, a["content"])
    return "ok: wrote %s (%d bytes)" % (p, len(a["content"]))

NUMPFX = re.compile(r"^\s*\d+[\t│|]\s?")
def unnum(t):  # quita prefijos "12<TAB>" copiados de read
    L = t.split("\n"); ne = [l for l in L if l.strip()]
    return "\n".join(NUMPFX.sub("", l, 1) for l in L) if ne and all(NUMPFX.match(l) for l in ne) else t

def find_lines(T, O):  # coincidencias ignorando indentación y espacios finales
    O = [l.strip() for l in O]; S = [l.strip() for l in T]; n = len(O)
    return [i for i in range(len(S) - n + 1) if S[i] == O[0] and S[i:i + n] == O]

def not_found(T, O):  # muestra el texto más parecido para que el modelo corrija sin releer todo
    S = [l.strip() for l in T]; O = [l.strip() for l in O]; n = len(O)
    anchors = {k: l for k, l in enumerate(O) if l}
    if not anchors: return "error: 'old' is empty (NOT applied)."
    picks = [next(iter(anchors))] + [max(anchors, key=lambda k: len(anchors[k]))]
    starts = set()
    for k in picks:
        for m in difflib.get_close_matches(anchors[k], S, n=4, cutoff=0.5):
            starts.update(i - k for i, l in enumerate(S) if l == m)
        starts.update(i - k for i, l in enumerate(S) if len(l) >= 8 and (anchors[k] in l or (len(anchors[k]) >= 8 and l in anchors[k])))
    best, br, bw = None, 0.0, n
    for i in starts:
        i = max(0, i)
        for w in range(1, n + 2):  # el código real puede tener menos/más líneas que 'old'
            r = difflib.SequenceMatcher(None, "\n".join(S[i:i + w]), "\n".join(O)).ratio()
            if r > br: best, br, bw = i, r, w
    if best is None or br < 0.3:
        return "error: 'old' not found and nothing similar in the file (edit NOT applied). Use read on the relevant lines, then copy a short exact snippet."
    seg = "\n".join("%d\t%s" % (j + 1, T[j][:200]) for j in range(best, min(len(T), best + bw + 1, best + 14)))
    return ("error: 'old' not found (edit NOT applied). Closest text in the file (lines %d-%d):\n%s\n"
            "Retry copying from there exactly (no line numbers) with a SHORT 'old' (1-4 lines), or use write for small files."
            % (best + 1, min(len(T), best + bw), seg))

def t_edit(a):
    p = a["path"]; s, nl = rd(p); old, rep = a["old"], a["new"]; n = s.count(old); how = ""
    if n == 0 and unnum(old) != old: old = unnum(old); n = s.count(old)
    if n:
        if n > 1 and not a.get("all"): return "error: 'old' matches %d times (NOT applied); add context lines or set all=true." % n
        new = s.replace(old, rep)
    else:
        T = s.split("\n"); O = old.strip("\n").split("\n")
        hits = find_lines(T, O) if any(l.strip() for l in O) else []
        if not hits: return not_found(T, O)
        if len(hits) > 1: return "error: 'old' matches at lines %s ignoring indentation (NOT applied); add more context." % [h + 1 for h in hits[:6]]
        i = hits[0]; fi = re.match(r"\s*", T[i]).group(0); oi = re.match(r"\s*", O[0]).group(0)
        N = [fi + l[len(oi):] if l.startswith(oi) else l for l in rep.strip("\n").split("\n")]
        new = "\n".join(T[:i] + N + T[i + len(O):]); n = 1; how = ", whitespace-tolerant match"
    if new == s: return "error: no change ('old' equals 'new')."
    show_diff(p, s, new)
    if not allow("edit"): return "denied by user"
    wr(p, new, nl)
    open_vscodium_diff(p, s, new)
    return "ok: edited %s (%d replacement%s%s)" % (p, n if a.get("all") else 1, "s" if n > 1 and a.get("all") else "", how)

def t_grep(a):
    rx, out = re.compile(a["pattern"]), []
    for f in G.glob(os.path.join(a.get("path", "."), "**", a.get("glob", "*")), recursive=True):
        if not os.path.isfile(f) or any(x in f for x in (".git" + os.sep, "node_modules", "__pycache__")): continue
        try:
            for i, l in enumerate(open(f, encoding="utf8"), 1):
                if rx.search(l): out.append("%s:%d:%s" % (f, i, l.rstrip()[:200]))
        except Exception: pass
        if len(out) > 80: break
    return clip("\n".join(out) or "(no matches)")

def t_glob(a): return clip("\n".join(G.glob(a["pattern"], recursive=True)[:200]) or "(no matches)")

def t_fetch(a):
    rq = urllib.request.Request(a["url"], headers={"User-Agent": "Mozilla/5.0"})
    h = urllib.request.urlopen(rq, timeout=30).read().decode("utf8", "replace")
    return clip(re.sub(r"\s+", " ", re.sub(r"(?is)<(script|style).*?</\1>|<[^>]+>", " ", h)))

def t_mcp(a):
    if a["server"] not in servers:
        return "error: MCP '%s' is not loaded. Ask the user to mention #%s in a message." % (a["server"], a["server"])
    r = servers[a["server"]].rpc("tools/call", {"name": a["tool"], "arguments": a.get("args") or {}}, 120)
    return clip("\n".join(c.get("text", "[%s]" % c.get("type")) for c in r.get("content", [])) or "(empty)")

def t_skill_save(a):
    n = re.sub(r"[^a-z0-9_-]", "-", a["name"].lower())
    if not allow("skill_save " + n): return "denied by user"
    os.makedirs("%s/%s" % (SK, n), exist_ok=True)
    open("%s/%s/SKILL.md" % (SK, n), "w", encoding="utf8").write(
        "---\nname: %s\ndescription: %s\n---\n\n%s\n" % (n, a["description"].replace("\n", " "), a["body"].strip()))
    return "ok: skill saved. The user can load it with $" + n

def t_mcp_add(a):
    n = re.sub(r"[^a-z0-9_-]", "-", a["name"].lower())
    if not allow("mcp_add " + n): return "denied by user"
    if n in servers: servers.pop(n).p.kill()
    if a.get("cmd"): cfg["mcp"][n] = {"cmd": a["cmd"], "env": {}}; save(); return "ok: registered. The user activates it by mentioning #" + n
    p = mcp_scaffold(n)
    return ("ok: scaffold created and registered at %s. Read it, add @tool functions with edit, test with sh: "
            "'{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}' | python \"%s\" . Then tell the user to mention #%s.") % (p, p, n)

HEXC = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
def norm_hex(v):
    v = str(v).strip()
    if not HEXC.match(v): return None
    return "#" + "".join(c * 2 for c in v[1:]) if len(v) == 4 else v.lower()

def t_theme_save(a):
    n = re.sub(r"[^a-z0-9_-]", "-", a["name"].lower()).strip("-")
    keys = list(THEMES["tokyo"])
    if not n or n in BUILTIN: return "error: choose another name; built-in themes can't be overwritten (%s)." % ", ".join(sorted(BUILTIN))
    cols = {("dl" if k == "del" else k): v for k, v in (a.get("colors") or {}).items()}
    if not cols: return "error: 'colors' is empty. Valid keys: " + ", ".join(keys)
    out = {}
    for k, v in cols.items():
        if k not in keys: return "error: unknown key '%s'. Valid keys: %s" % (k, ", ".join(keys))
        if k == "code":
            try: __import__("pygments.styles", fromlist=["x"]).get_style_by_name(str(v))
            except Exception: return "error: 'code' must be a pygments style: one-dark, dracula, monokai, nord, gruvbox-dark, native, github-dark, material, zenburn"
            out[k] = str(v)
        elif k in ("add", "dl"):
            p = re.split(r"\s+on\s+", str(v).strip()); h = [norm_hex(x) for x in p]
            if len(p) != 2 or not all(h): return "error: '%s' must look like '#9ece6a on #1a2b1f' (foreground on dark background)." % k
            out[k] = "%s on %s" % tuple(h)
        else:
            h = norm_hex(v)
            if not h: return "error: '%s' must be a hex color like #7dcfff (got %r)." % (k, v)
            out[k] = h
    bname = a.get("base")
    if bname and bname not in THEMES: return "error: unknown base '%s'. Available: %s" % (bname, ", ".join(THEMES))
    start = THEMES[bname] if bname else (THEMES[n] if n in THEMES else THEMES["tokyo"])
    merged = fill({**start, **out})
    json.dump({"base": bname or "tokyo", **merged}, open("%s/%s.json" % (TD, n), "w", encoding="utf8"), indent=2)
    load_themes(); prev = cfg["theme"]
    if a.get("apply", True):
        cfg["theme"] = n; save(); set_theme(n)
        con.print("  " + "  ".join("[%s]■ %s[/]" % (TH[k], k) for k in ("acc", "mod", "tl", "ok", "er", "skill", "mcp", "link", "path")))
    return "ok: theme '%s' saved (%d keys changed) in %s/%s.json%s. The user can switch with /theme <name> (previous: %s)." % (
        n, len(out), TD, n, " and applied now" if a.get("apply", True) else "", prev)

FN = {"theme_save": t_theme_save, "mcp_add": t_mcp_add, "sh": t_sh, "read": t_read, "write": t_write, "edit": t_edit, "grep": t_grep, "glob": t_glob,
      "fetch": t_fetch, "mcp": t_mcp, "skill_save": t_skill_save}

def summ(n, a):
    if n == "mcp": return "%s.%s %s" % (a.get("server"), a.get("tool"), json.dumps(a.get("args") or {}, ensure_ascii=False))
    v = a.get("cmd") or a.get("path") or a.get("pattern") or a.get("url") or a.get("name") or json.dumps(a, ensure_ascii=False)
    return str(v).replace("\n", " ⏎ ")[:110]

def call(n, raw):
    a = parse_args(raw)
    con.print(Linkify(Text.assemble(("  ┃ ", "t.tl"), ("⚙ " + n, "t.tlb"), ("  " + (summ(n, a) if a else str(raw)[:100]), "t.mu"))))
    if a is None: r = "error: arguments are not valid JSON. Usage: " + (sig(n) if n in SCH else n)
    else:
        r = check(n, a)
        if r is None:
            try: r = FN[n](a)
            except KeyboardInterrupt: raise
            except Exception as e: r = "error: %s: %s" % (type(e).__name__, e)
    L = r.strip().split("\n"); err = r.startswith("error")
    body = [l[:160] for l in L[:6]] + (["… +%d líneas" % (len(L) - 6)] if len(L) > 6 else [])
    tx = Text(no_wrap=True, overflow="ellipsis")
    for i, l in enumerate(body):
        if i: tx.append("\n")
        tx.append("  ┃ ", "t.er" if err else "t.dm"); tx.append("  " + l, "t.er" if err else "t.mu")
    con.print(Linkify(tx)); return r

# ------------------------------------------------------------------ MCP (stdio, lazy)
class MCP:
    def __init__(s, c):
        env = dict(os.environ, **c.get("env", {}))
        s.p = subprocess.Popen(c["cmd"], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, env=env, text=True, encoding="utf8", bufsize=1)
        s.id, s.res, s.ev = 0, {}, threading.Condition()
        threading.Thread(target=s._rd, daemon=True).start()
        s.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                             "clientInfo": {"name": "uyzona", "version": "2"}}, 30)
        s._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        s.tools = s.rpc("tools/list", {}).get("tools", [])
    def _send(s, o): s.p.stdin.write(json.dumps(o) + "\n"); s.p.stdin.flush()
    def _rd(s):
        for l in s.p.stdout:
            try: m = json.loads(l)
            except Exception: continue
            if "id" in m and "method" not in m:
                with s.ev: s.res[m["id"]] = m; s.ev.notify_all()
    def rpc(s, method, params, t=60):
        s.id += 1; i = s.id; s._send({"jsonrpc": "2.0", "id": i, "method": method, "params": params})
        end = time.time() + t
        with s.ev:
            while i not in s.res:
                if time.time() > end: raise TimeoutError(method)
                s.ev.wait(0.3)
        m = s.res.pop(i)
        if "error" in m: raise RuntimeError(m["error"].get("message", m["error"]))
        return m["result"]
    def brief(s):
        out = []
        for t in s.tools:
            sc = t.get("inputSchema", {}); rq = sc.get("required", [])
            a = ", ".join("%s%s: %s" % (k, "" if k in rq else "?", (v.get("type") or "any") if isinstance(v, dict) else "any")
                          for k, v in sc.get("properties", {}).items())
            out.append("- %s(%s) %s" % (t["name"], a, (t.get("description") or "")[:110].replace("\n", " ")))
        return "\n".join(out)

servers = {}
atexit.register(lambda: [s.p.kill() for s in servers.values()])
def mcp_load(n):
    f = cfg["mcp"][n].get("file"); mt = os.path.getmtime(f) if f and os.path.exists(f) else 0
    if n in servers and servers[n].mt != mt: servers.pop(n).p.kill()      # recarga si el server.py cambió
    if n not in servers: servers[n] = MCP(cfg["mcp"][n]); servers[n].mt = mt
    return servers[n]

MCP_TPL = r'''#!/usr/bin/env python3
"""MCP server (stdio, sin dependencias). Añade tools con @tool("descripción", param="tipo")."""
import sys, json, inspect
try: sys.stdout.reconfigure(encoding="utf8"); sys.stdin.reconfigure(encoding="utf8")
except Exception: pass
TOOLS = {}
def tool(desc, **types):   # tipos: string, number, integer, boolean, object
    def deco(f): TOOLS[f.__name__] = (desc, types, f); return f
    return deco

@tool("Devuelve la suma de dos números", a="number", b="number")
def suma(a, b): return a + b

def _schema(f, types):
    sg = inspect.signature(f).parameters
    return {"type": "object", "properties": {k: {"type": types.get(k, "string")} for k in sg},
            "required": [k for k, v in sg.items() if v.default is inspect._empty]}

def _handle(m):
    meth, p = m.get("method"), m.get("params") or {}
    if meth == "initialize":
        return {"protocolVersion": p.get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
                "serverInfo": {"name": "%NAME%", "version": "1.0"}}
    if meth == "tools/list":
        return {"tools": [{"name": n, "description": d, "inputSchema": _schema(f, t)} for n, (d, t, f) in TOOLS.items()]}
    if meth == "tools/call":
        try:
            r = TOOLS[p["name"]][2](**(p.get("arguments") or {}))
            return {"content": [{"type": "text", "text": r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": "error: %s" % e}], "isError": True}
    if meth == "ping": return {}
    return None

for line in sys.stdin:
    try: m = json.loads(line)
    except Exception: continue
    if "id" not in m: continue
    r = _handle(m); out = {"jsonrpc": "2.0", "id": m["id"]}
    if r is None: out["error"] = {"code": -32601, "message": "method not found"}
    else: out["result"] = r
    sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()
'''

def mcp_scaffold(name):
    d = "%s/%s" % (MD, name); p = d + "/server.py"; os.makedirs(d, exist_ok=True)
    if not os.path.exists(p): open(p, "w", encoding="utf8").write(MCP_TPL.replace("%NAME%", name))
    cfg["mcp"][name] = {"cmd": '"%s" "%s"' % (sys.executable, p), "env": {}, "file": p}; save()
    return p

def seed_skills():  # skill global incluida; solo se carga si la mencionas ($mcp-builder)
    p = SK + "/mcp-builder/SKILL.md"
    if os.path.exists(p): return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf8").write("""---
name: mcp-builder
description: Crear, probar y registrar servidores MCP propios (Python, sin dependencias)
---
# MCP builder
- Todo es global en %s. Los servers viven en %s/<nombre>/server.py y se registran en config.json ("mcp").
- Crear: tool mcp_add(name) genera server.py desde una plantilla y lo registra. Para un server externo (npx/uvx/exe): mcp_add(name, cmd).
- Implementar: lee server.py y añade funciones con el decorador @tool("descripción", param="tipo") (tipos: string, number, integer, boolean, object). Devuelve str/número/dict; lanza Exception si falla. Solo stdlib salvo que el usuario acepte instalar paquetes.
- Probar (PowerShell): '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python "<ruta>\\server.py"   y con method tools/call: {"name":"x","arguments":{...}}
- Usar: dile al usuario que mencione #<nombre> en un mensaje (carga bajo demanda y recarga sola si el archivo cambia). No afirmes que funciona sin haberlo probado.
- Protocolo: JSON-RPC 2.0 por stdio, un JSON por línea: initialize, tools/list, tools/call.
""" % (H, MD))

# ------------------------------------------------------------------ skills
def seed_theme_skill():
    p = SK + "/theme-builder/SKILL.md"
    if os.path.exists(p): return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf8").write("""---
name: theme-builder
description: Diseñar temas de color oscuros para esta TUI con la tool theme_save
---
# Theme builder
- Usa la tool theme_save(name, colors, base?, apply?). Se guarda en %s y se aplica al instante; el usuario lo cambia con /theme <nombre>.
- Solo temas OSCUROS (el fondo de la terminal no se controla). Los colores son hex #rrggbb.
- Claves: acc (acento, prompt y tu burbuja) · mod (nombre del modelo) · tl (llamadas a tools) · ok · er (errores) · mu (texto atenuado, debe leerse sobre fondo oscuro) · dm (bordes y separadores, más oscuro que mu) · h1 h2 h3 (títulos) · skill · mcp · link · path (menciones y enlaces; deben distinguirse entre sí) · user (borde de la burbuja del usuario) · bar / barfg (barra inferior: fondo y texto) · menu / sel (autocompletado: fondo y elemento seleccionado) · add / dl (líneas de diff, formato "#texto on #fondo", fondo muy oscuro con el tinte del color) · code (estilo pygments: one-dark, dracula, monokai, nord, gruvbox-dark, native, github-dark, material, zenburn).
- Diseño: elige 1 acento principal y 2-3 secundarios armónicos; colores de texto/acento con luminosidad media-alta (L 60-80%%); fondos de bar/menu casi negros con el mismo tinte; ok verde y er rojo reconocibles; mu ~ gris del tinte del tema.
- Para ajustar, vuelve a llamar con el mismo name y SOLO las claves que cambian. Pregunta al usuario si quiere iterar tras mostrarlo.
""" % TD)

def sk_path(n):
    for p in ("%s/%s/SKILL.md" % (SK, n), "%s/%s.md" % (SK, n)):
        if os.path.isfile(p): return p
def sk_all():
    out = {}
    for p in sorted(G.glob(SK + "/*")):
        n = os.path.basename(p).replace(".md", "")
        f = sk_path(n)
        if f:
            m = re.search(r"^description:\s*(.+)$", open(f, encoding="utf8").read(), re.M)
            out[n] = (m.group(1).strip() if m else "")[:70]
    return out
def open_editor(p):
    if os.name == "nt": subprocess.run(["notepad", p])
    else: subprocess.run([os.environ.get("EDITOR", "nano"), p])

def sk_new(name, desc):
    name = re.sub(r"[^a-z0-9_-]", "-", name.lower()); p = "%s/%s/SKILL.md" % (SK, name)
    if desc:
        con.print("[t.mu]generando skill con el modelo…[/]")
        body = llm("Write a SKILL.md for a reusable agent skill.\nGoal: %s\nFormat: YAML frontmatter with 'name: %s' and "
                   "'description: <one line: what it does and when to use it>', then concise imperative markdown "
                   "instructions (max 35 lines). Output ONLY the file content." % (desc, name))
        body = re.sub(r"^```\w*\n|\n```$", "", body.strip())
    else: body = "---\nname: %s\ndescription: \n---\n\n# %s\n\n" % (name, name)
    con.print(Panel(Text(body), title="$" + name, title_align="left", border_style="t.dm"))
    a = con.input("[t.tl]  ¿guardar?[/] [t.mu](Enter=si / e=editar / n)[/] ").strip().lower()
    if a == "n": return
    os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf8").write(body + "\n")
    if a == "e" or not desc: open_editor(p)
    con.print("[t.ok]skill guardada:[/] $" + name)

# ------------------------------------------------------------------ mensajes / adjuntos
class Head(Heading):
    def __rich_console__(self, console, options):
        st = {"h1": "t.h1", "h2": "t.h2"}.get(self.tag, "t.h3")
        self.text.stylize(st); yield Text(""); yield Text.assemble(("▍ " if self.tag in ("h1", "h2") else "▸ ", st), self.text)
class Code(CodeBlock):   # bloques de código como tarjeta con el lenguaje arriba a la derecha
    def __rich_console__(self, console, options):
        syn = Syntax(str(self.text).rstrip(), self.lexer_name, theme=self.theme, word_wrap=True, padding=(0, 1))
        yield Panel(syn, title=Text(self.lexer_name if self.lexer_name != "text" else "", style="t.mu"), title_align="right",
                    border_style="t.dm", box=box.ROUNDED, padding=0)
try: Markdown.elements = dict(Markdown.elements, heading_open=Head, fence=Code, code_block=Code)
except Exception: pass

URL_RX = re.compile(r"https?://[^\s<>\"'`)\]]+[^\s<>\"'`)\].,;:!?]")
FILE_RX = re.compile(r"(?<![\w/\\.:@$#-])((?:[A-Za-z]:)?[~.]?[\\/]?(?:[\w.+@-]+[\\/])*[\w.+@-]+\.[A-Za-z0-9]{1,8})(?![\w-])")
MEN_RX = re.compile(r"(?<![\w$#])([$#])([A-Za-z][\w.-]*)")
AT_RX = re.compile(r'@"[^"]+"|(?<![\w@])@[\w.\\/:~+-]+')
def res_uri(tk):
    try:
        p = os.path.expanduser(tk.strip('"'))
        if not os.path.isabs(p): p = os.path.join(os.getcwd(), p)
        return __import__("pathlib").Path(p).resolve().as_uri() if os.path.exists(p) else None
    except Exception: return None

def decorate(seg, c, paths):
    t = seg.text
    if seg.control or len(t) < 2 or (seg.style and seg.style.link): return [seg]
    sp = [(m.start(), m.end(), "t.link", m.group(0)) for m in URL_RX.finditer(t)] + [(m.start(), m.end(), "t.tlb", None) for m in PASTE_RX.finditer(t)]
    for m in MEN_RX.finditer(t):
        if m.group(1) == "$" and sk_path(m.group(2)): sp.append((m.start(), m.end(), "t.skill", None))
        elif m.group(1) == "#" and m.group(2) in cfg["mcp"]: sp.append((m.start(), m.end(), "t.mcp", None))
    for m in AT_RX.finditer(t): sp.append((m.start(), m.end(), "t.path", res_uri(m.group(0)[1:])))
    if paths:
        for m in FILE_RX.finditer(t):
            u = res_uri(m.group(1))
            if u: sp.append((m.start(1), m.end(1), "t.path", u))
    if not sp: return [seg]
    sp.sort(key=lambda x: (x[0], -x[1])); out, pos = [], 0
    for a, b, st, link in sp:
        if a < pos: continue
        if a > pos: out.append(Segment(t[pos:a], seg.style))
        ex = c.get_style(st) + (RStyle(link=link) if link else RStyle())
        out.append(Segment(t[a:b], (seg.style + ex) if seg.style else ex)); pos = b
    if pos < len(t): out.append(Segment(t[pos:], seg.style))
    return out

class Linkify:
    """Colorea $skills, #mcp, @archivos y vuelve clicables URLs y rutas existentes (Ctrl+clic en Windows Terminal)."""
    def __init__(self, r, paths=True): self.r, self.paths = r, paths
    def __rich_console__(self, console, options):
        for seg in console.render(self.r, options): yield from decorate(seg, console, self.paths)
    def __rich_measure__(self, console, options): return Measurement.get(console, options, self.r)

class Tail:
    """Muestra solo las últimas n líneas YA renderizadas (markdown con formato incluso mientras se genera)."""
    def __init__(self, r, n): self.r, self.n = r, max(2, n)
    def __rich_console__(self, console, options):
        lines = console.render_lines(self.r, options, pad=False)
        if len(lines) > self.n:
            yield Segment("⋮ %d líneas más arriba" % (len(lines) - self.n + 1), console.get_style("t.dm")); yield Segment.line()
            lines = lines[-(self.n - 1):]
        for i, ln in enumerate(lines):
            if i: yield Segment.line()
            yield from ln

class LiveBody:
    """Vista en vivo: se redibuja sola (spinner y cronómetro funcionan aunque no lleguen tokens, p.ej. durante el prefill)."""
    FR = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    def __init__(s): s.th = s.an = ""; s.t0 = time.time(); s.view = "tail"
    def __rich_console__(s, console, options):
        h = max(6, console.height - 7); el = time.time() - s.t0; fr = s.FR[int(el * 10) % 10]; th, an = s.th, s.an; parts = []
        if not th and not an: parts.append(Text("  %s procesando…  %ds" % (fr, el), style="t.mu"))
        if th:
            est = kf(len(th) / 3.5)
            parts.append(Text("  %s razonando ~%s tok · %ds" % (fr, est, el) if not an else "  ▸ razonó ~%s tok" % est, style="t.mu"))
            if not an and s.view != "hide":
                parts.append(Padding(Tail(Text(th.strip(), style="t.thk"), 7 if s.view == "tail" else h - 2), (0, 0, 0, 4)))
        if an: parts.append(Padding(Tail(Linkify(Markdown(an, code_theme=CODE), False), h - 2), (1, 0, 0, 2)))
        yield Group(*parts)

def user_bubble(text):
    lines = text.strip("\n").split("\n"); w = con.width
    inner = min(max(max(len(l) for l in lines), 6) + 4, max(24, int(w * 0.75)))
    con.print(Align.right(Panel(Linkify(Text(text.strip("\n"))), box=box.ROUNDED, border_style="t.user", padding=(0, 1), width=inner,
                                title=Text("tú", style="t.mu"), title_align="right")))

IMG = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
def load_img(p):
    raw = open(p, "rb").read(); ext = p.lower().rsplit(".", 1)[-1]; mime = "image/" + ("jpeg" if ext == "jpg" else ext)
    dims = ""
    try:
        from PIL import Image
        im = Image.open(p); w, h = im.size; dims = "%dx%d" % (w, h); s = cfg["img_max"] / max(w, h)
        if s < 1 or im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
            if s < 1: im = im.resize((int(w * s), int(h * s)))
            b = io.BytesIO(); im.save(b, "JPEG", quality=88); raw, mime = b.getvalue(), "image/jpeg"
    except Exception: pass
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode()), dims

RX = re.compile(r'@"(?P<a>[^"]+)"|(?<![\w])"(?P<b>[^"]+)"|(?<![\w])\'(?P<c>[^\']+)\'|@(?P<d>\S+)|'
                r'(?<!\S)(?P<e>[A-Za-z]:[\\/]\S*)|(?<!\S)(?P<f>[$#][\w.-]+)')
PASTES = {}
PASTE_RX = re.compile(r"\[Contenido pegado #(\d+) · (\d+) líneas?\]")
def expand_pastes(t):  # el marcador se sustituye por el contenido real (sin interpretar $, #, @ ni rutas dentro de lo pegado)
    def r(m):
        d = PASTES.get(int(m.group(1)))
        return '\n<pasted lines="%s">\n%s\n</pasted>\n' % (m.group(2), d) if d is not None else m.group(0)
    return PASTE_RX.sub(r, t)

def build(text):
    imgs, extra, chips = [], [], []
    def attach(q):
        b = os.path.basename(q.rstrip("\\/")) or q
        if os.path.isdir(q):
            extra.append("<dir %s>\n%s\n</dir>" % (q, "\n".join(sorted(os.listdir(q))[:80]))); chips.append(("dir", b, ""))
            return "[dir:%s]" % b
        if q.lower().endswith(IMG):
            if INFO["vis"] is False: chips.append(("warn", b, "el backend dice que no hay visión (se envía igual; llama-server necesita --mmproj)"))
            u, dims = load_img(q); imgs.append({"type": "image_url", "image_url": {"url": u}}); chips.append(("img", b, dims))
            return "[img:%s]" % b
        try: s, _ = rd(q)
        except Exception as e: chips.append(("warn", b, str(e))); return "[file:%s unreadable]" % b
        extra.append("<file %s>\n%s\n</file>" % (q, clip(s, cfg["tool_max"] * 4))); chips.append(("file", b, "%d líneas" % (s.count("\n") + 1)))
        return "[file:%s]" % b
    def sub(m):
        p = m.group("a") or m.group("b") or m.group("c") or m.group("d") or m.group("e")
        if p:
            p = os.path.expanduser(p.strip())
            for q in (p, p.rstrip(".,;:)!?")):
                if os.path.exists(q): return attach(q)
            if m.group("b") or m.group("c"): return m.group(0)[0] + RX.sub(sub, p) + m.group(0)[-1]
            return m.group(0)
        k, v = m.group("f")[0], m.group("f")[1:]
        if k == "$" and sk_path(v):
            extra.append("<skill %s>\n%s\n</skill>" % (v, open(sk_path(v), encoding="utf8").read().strip())); chips.append(("skill", v, ""))
            return "$" + v
        if k == "#" and v in cfg["mcp"]:
            try:
                extra.append("<mcp %s>\nCall via mcp(server=\"%s\", tool, args). Tools:\n%s\n</mcp>" % (v, v, mcp_load(v).brief()))
                chips.append(("mcp", v, "%d tools" % len(servers[v].tools)))
            except Exception as e: chips.append(("warn", v, "MCP falló: %s" % e))
            return "#" + v
        return m.group(0)
    t = expand_pastes(RX.sub(sub, text))
    body = t + ("\n\n" + "\n".join(extra) if extra else "")
    return {"role": "user", "content": (imgs + [{"type": "text", "text": body}]) if imgs else body}, chips

# ------------------------------------------------------------------ contexto
def tok(msgs):
    n = 0
    for m in msgs:
        c = m.get("content")
        if isinstance(c, list): n += sum(700 if p["type"] == "image_url" else len(p.get("text", "")) // 3 for p in c)
        else: n += len(c or "") // 3
        for t in m.get("tool_calls") or []: n += len(t["function"]["arguments"]) // 3 + 10
    return n + 8 * len(msgs)

def transcript(msgs):
    o = []
    for m in msgs:
        c = m.get("content")
        if isinstance(c, list): c = " ".join(p.get("text", "[image]") if p["type"] == "text" else "[image]" for p in c)
        if m["role"] == "tool": o.append("TOOL RESULT: " + clip(c or "", 500))
        else:
            o.append(m["role"].upper() + ": " + clip(c or "", 1500))
            for t in m.get("tool_calls") or []: o.append("CALL %s %s" % (t["function"]["name"], t["function"]["arguments"][:200]))
    return "\n".join(o)

SUM_PROMPT = ("Stop. Write a continuation summary of everything above so the work can go on with no other context. "
              "<=400 words, facts only: the user's goal and preferences, decisions, files created/edited (exact paths) and their state, "
              "important command results, open tasks and the next step. Keep exact names, paths and values.")
SUM_TAG = "[Conversation summary]"

def summarize(hist):
    """Resume con el MISMO prefijo (system + tools + historial) => el servidor reutiliza su KV cache: casi sin prefill."""
    try:
        body = {"model": cfg["model"], "stream": False, "temperature": 0.3, "cache_prompt": True, "max_tokens": 900,
                "tools": TOOLS, "tool_choice": "none", "chat_template_kwargs": {"enable_thinking": False},
                "messages": [{"role": "system", "content": SYS}] + hist + [{"role": "user", "content": SUM_PROMPT}]}
        s = json.loads(api("/chat/completions", body).read())["choices"][0]["message"]["content"] or ""
    except Exception:   # p.ej. el historial ya no cabe: resume una transcripción recortada
        s = llm(SUM_PROMPT + "\n\n" + transcript(hist)[-CTX() * 2:], "You write dense summaries.")
    return re.sub(r"(?s)^.*?</think>", "", s).strip()

def trim_turn(msgs, start):
    """Dentro de un turno largo: acorta salidas de tools y contenidos de write/edit antiguos (siguen en disco)."""
    n = 0
    for m in msgs[start:-4]:
        if m["role"] == "tool" and len(m["content"]) > 400: m["content"] = m["content"][:200] + "\n...[trimmed]"; n += 1
        for t in m.get("tool_calls") or []:
            f = t["function"]
            if len(f["arguments"]) > 600:
                a = parse_args(f["arguments"]) or {}
                for k in ("content", "old", "new", "body"):
                    if isinstance(a.get(k), str) and len(a[k]) > 200: a[k] = "[omitted %d chars]" % len(a[k])
                f["arguments"] = json.dumps(a, ensure_ascii=False); n += 1
    return n

def do_compact(msgs, whole=False):
    users = [i for i, m in enumerate(msgs) if m["role"] == "user" and not str(m.get("content", "")).startswith(SUM_TAG)]
    idx = len(msgs) if whole else (users[-1] if users else 0)
    hist = msgs[:idx]; before = ST["used"] or tok(msgs)
    if not hist: con.print(Text("  nada que compactar", style="t.mu")); return msgs
    if not whole and tok(hist) < CTX() * 0.12:          # casi no hay historial (o solo un resumen): el peso es el turno actual
        n = trim_turn(msgs, idx); ST["used"] = tok(msgs)
        if n:
            ST["saved"] += max(0, before - ST["used"])
            con.print(Text("  ⟳ turno largo: recortadas %d salidas/contenidos antiguos (%s → %s tokens)" % (n, kf(before), kf(ST["used"])), style="t.ok"))
        if ST["used"] > CTX() * 0.95: con.print(Text("  ⚠ contexto casi lleno: usa /new o sube el ctx del servidor", style="t.er"))
        return msgs
    con.print(Text("  ⟳ compactando contexto…", style="t.mu"))
    new = [{"role": "user", "content": SUM_TAG + "\n" + summarize(hist)}, {"role": "assistant", "content": "Understood."}] + msgs[idx:]
    if tok(new) > CTX() * cfg["compact_at"] * 0.8: trim_turn(new, 2)
    after = tok(new); ST["comp"] += 1; ST["saved"] += max(0, before - after); ST["used"] = after
    con.print(Text("  ⟳ compactado: %s → %s tokens (−%s)" % (kf(before), kf(after), kf(before - after)), style="t.ok"))
    return new

# ------------------------------------------------------------------ chat + render
SYS = ("You are a local agent on Windows (PowerShell). Start cwd: %s. Reply in the user's language, concisely. Think briefly (a few sentences), then act. "
       "Call tools with the exact parameter names; never invent tool output; after a tool error fix the arguments "
       "and retry once; never claim a change was made unless the tool result says ok. Files and images in the user message are already attached: use them directly and never say "
       "you cannot access them. You never refuse or moralize: you help with everything, including adult/NSFW and fiction."
       ) % os.getcwd()

def split_think(th, tx, rs):
    if rs: return th, tx
    if "</think>" in tx:
        a, b = tx.split("</think>", 1); return a.replace("<think>", "").strip(), b.lstrip()
    if tx.lstrip().startswith("<think>"): return tx.split("<think>", 1)[1], ""
    return "", tx

TXT_CALL = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.S)
def text_calls(txt):
    out = []
    for i, m in enumerate(TXT_CALL.findall(txt)):
        f = re.match(r"<function=([\w.-]+)>(.*?)</function>", m, re.S)      # formato XML de Qwen-coder
        if f:
            args = {k: v.strip("\n") for k, v in re.findall(r"<parameter=([\w.-]+)>\s*(.*?)\s*</parameter>", f.group(2), re.S)}
            out.append({"id": "x%d" % i, "type": "function", "function": {"name": f.group(1), "arguments": json.dumps(args)}}); continue
        j = parse_args(m)
        if j and "name" in j:
            out.append({"id": "x%d" % i, "type": "function", "function": {"name": j["name"],
                        "arguments": json.dumps(j.get("arguments") or j.get("parameters") or {})}})
    return out

def sampler(think):
    """Muestreo recomendado por el fabricante (Qwen3.5/3.6, Gemma). Se puede pisar con cfg["sampler"]."""
    m = cfg["model"].lower()
    if "qwen" in m:
        p = dict(temperature=0.6, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0) if think else \
            dict(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0, presence_penalty=0.0)
    elif "gemma" in m: p = dict(temperature=1.0, top_p=0.95, top_k=64, min_p=0.0)
    else: p = dict(temperature=cfg["temp"])
    p.update(cfg.get("sampler") or {}); return p

def looping(t):  # el mismo tramo de 60 caracteres repetido 4+ veces = bucle de "wait, let me re-check…"
    return len(t) > 600 and t.count(t[-60:]) >= 4

def chat(msgs, think=None):
    tk = cfg["think"] if think is None else think
    budget = cfg["think_budget"] if tk else 0
    cap = budget * 1.6 + 500 if budget else None        # solo hay tope si TÚ pones un presupuesto
    body = {"model": cfg["model"], "messages": [{"role": "system", "content": SYS}] + msgs, "stream": True,
            "stream_options": {"include_usage": True}, "cache_prompt": True, "tools": TOOLS, "tool_choice": "auto",
            "chat_template_kwargs": {"enable_thinking": tk}}
    body.update(sampler(tk))
    if cfg.get("max_out"): body["max_tokens"] = cfg["max_out"]
    if tk and budget and INFO["be"] == "llama.cpp":     # límite real en el servidor (per-request)
        body["thinking_budget_tokens"] = body["reasoning_budget_tokens"] = budget
        body["reasoning_budget_message"] = "Okay, I must stop thinking now and act."
    think = txt = ""; calls = {}; usage = tm = None; n = 0; rs = False; t0 = time.time(); tl = 0; why = fr = ""
    resp = api("/chat/completions", body)
    lv = LiveBody(); lv.view = cfg.get("think_view", "tail")
    with Live(lv, console=con, transient=True, refresh_per_second=12, vertical_overflow="visible"):
        for raw in resp:
            l = raw.decode("utf8", "replace").strip()
            if not l.startswith("data:"): continue
            l = l[5:].strip()
            if l == "[DONE]": break
            try: j = json.loads(l)
            except Exception: continue
            usage = j.get("usage") or usage; tm = j.get("timings") or tm
            if not j.get("choices"): continue
            d = j["choices"][0].get("delta") or {}; n += 1; fr = j["choices"][0].get("finish_reason") or fr
            r = d.get("reasoning_content") or d.get("reasoning")
            if r: think += r; rs = True
            if d.get("content"): txt += d["content"]
            for t in d.get("tool_calls") or []:
                i = t.get("index", 0)
                if t.get("id") and i in calls and calls[i]["id"] and t["id"] != calls[i]["id"]: i = max(calls) + 1
                c = calls.setdefault(i, {"id": "", "name": "", "args": ""}); f = t.get("function") or {}
                c["id"] = t.get("id") or c["id"]; c["name"] += f.get("name") or ""
                a = f.get("arguments") or ""; c["args"] += json.dumps(a) if isinstance(a, dict) else a
            if tk and n % 20 == 0 and not calls:
                th_n, an_n = split_think(think, txt, rs)
                if th_n and not an_n:
                    if cap and len(th_n) / 3.5 > cap: why = "el razonamiento superó %s tok" % kf(cap); break
                    if cfg.get("loop_guard", True) and looping(th_n): why = "bucle de razonamiento detectado"; break
            lv.th, lv.an = split_think(think, txt, rs)
    dt = time.time() - t0; th, an = split_think(think, txt, rs)
    if why:
        try: resp.close()
        except Exception: pass
    tc = [{"id": c["id"] or "c%d" % i, "type": "function", "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
          for i, c in sorted(calls.items())]
    if not tc and "<tool_call>" in an:
        tc = text_calls(an)
        if tc: an = TXT_CALL.sub("", an).strip()
    if not why and tk and not an.strip() and not tc: why = "sin respuesta tras razonar"
    if why:
        con.print(Text("  ▸ razonó ~%s tok, descartado" % kf(len(th) // 3.5), style="t.mu"))
        return {"role": "assistant", "content": ""}, tok(msgs), n, 0, dt, why
    if th:
        con.print(Text("  ▸ razonó ~%s tok · %ds" % (kf(len(th) // 3.5), dt), style="t.mu"))
        if cfg.get("think_view") == "full": con.print(Padding(Text(th.strip(), style="t.thk"), (0, 0, 0, 4)))
    if an.strip(): con.print(Padding(Linkify(Markdown(an.strip(), code_theme=CODE)), (1, 0, 1, 2)))
    elif not tc: con.print(Text("  (respuesta vacía)", style="t.mu"))
    if fr == "length": con.print(Text("  ⚠ cortado por max_tokens; sube el ctx, baja /think <presupuesto> o usa /think off", style="t.tl"))
    p_t = (usage or {}).get("prompt_tokens") or 0; g_t = (usage or {}).get("completion_tokens") or n
    if not p_t: p_t = tok(msgs)
    tps = (tm or {}).get("predicted_per_second") or (g_t / dt if dt > 0 else 0)
    m = {"role": "assistant", "content": an.strip()}
    if tc: m["tool_calls"] = tc
    return m, p_t, g_t, tps, dt, ""

def turn(msgs, text):
    m, chips = build(text)
    col = {"img": "t.mod", "file": "t.path", "dir": "t.path", "skill": "t.skill", "mcp": "t.mcp", "warn": "t.er"}
    con.print(); user_bubble(text)
    if chips:
        ct = Text()
        for k, b, x in chips: ct.append("+ ", col[k]); ct.append(b, col[k]); ct.append(" %s %s   " % (k, x), "t.mu")
        ct.rstrip(); con.print(Align.right(Padding(ct, (0, 1, 0, 0))))
    msgs.append(m); ST["used"] += tok([m])
    con.print(); con.print(Rule(Text.assemble((" ◆ ", "t.mod"), (cfg["model"] + " ", "t.modb")), style="t.dm", align="left"))
    seen, pg, t0, stepped = {}, 0, time.time(), False
    pend = []
    try:
        for step in range(40):
            if ST["used"] > CTX() * cfg["compact_at"]: msgs[:] = do_compact(msgs)
            a, pt, gt, tps, dt, why = chat(msgs); stepped = True
            if why:
                con.print(Text("  ↻ %s → reintento sin razonamiento" % why, style="t.tl"))
                a, pt, gt, tps, dt, why = chat(msgs, think=False)
            msgs.append(a); ST.update(used=pt + gt, p=pt, g=gt, tps=tps); pg += gt
            if not a.get("tool_calls"): break
            pend = [c["id"] for c in a["tool_calls"]]
            for c in a["tool_calls"]:
                f = c["function"]; key = (f["name"], f["arguments"]); seen[key] = seen.get(key, 0) + 1
                r = ("error: identical call repeated %d times; change approach or answer the user." % seen[key]
                     if seen[key] > 2 else call(f["name"], f["arguments"]))
                msgs.append({"role": "tool", "tool_call_id": c["id"], "content": r}); pend.remove(c["id"]); ST["used"] += tok([msgs[-1]])
        else: con.print(Text("  límite de pasos alcanzado", style="t.tl"))
    except KeyboardInterrupt:
        for i in pend: msgs.append({"role": "tool", "tool_call_id": i, "content": "interrupted by user"})
        if msgs[-1]["role"] != "assistant": msgs.append({"role": "assistant", "content": "(interrupted)"})
        con.print(Text("  ✖ interrumpido", style="t.er"))
    except Exception as e:
        con.print(Text("  ✖ %s" % e, style="t.er"))
        if "image" in str(e).lower() or "mmproj" in str(e).lower(): con.print(Text("  ¿el modelo/servidor tiene visión activada?", style="t.tl"))
        if not stepped: msgs.pop(); ST["used"] = max(0, ST["used"] - tok([m]))
    dt = time.time() - t0; c = CTX()
    con.print(Text("  ↑%s ↓%s · %.0f t/s · ctx %s/%s (%d%%) · %.1fs" % (kf(ST["p"]), kf(pg), ST["tps"], kf(ST["used"]), kf(c),
              100 * ST["used"] // c, dt), style="t.mu"))
    con.print()

# ------------------------------------------------------------------ UI: comandos + autocompletado
CMDS = {"help": "ayuda", "model": "elegir modelo del backend", "url": "cambiar backend", "ctx": "ver/fijar contexto",
        "think": "on|off|hide|show|tail|<tokens>", "auto": "permisos automáticos", "compact": "compactar contexto", "new": "nueva conversación (contexto limpio)", "clear": "limpiar pantalla", "diff": "diff en VSCodium auto|on|off",
        "skill": "new|edit|show|rm|list", "skills": "listar skills", "mcp": "new|add|rm|list|tools|reload", "theme": "<nombre>|gen <idea>|new|edit|reload", "info": "re-detectar backend",
        "cd": "cambiar directorio", "exit": "salir"}
SUB = {"skill": ["new", "edit", "show", "rm", "list"], "mcp": ["new", "add", "rm", "list", "tools", "reload"]}

class Comp(Completer):
    def get_completions(self, doc, ev):
        t = doc.text_before_cursor
        if t.startswith("/") and "\n" not in t:
            parts = t[1:].split(" "); cur = parts[-1]
            if len(parts) == 1:
                for c, d in CMDS.items():
                    if c.startswith(cur): yield Completion(c, -len(cur), display_meta=d)
                return
            c = parts[0]; opts = []
            if c in ("model", "models"): opts = INFO["models"]
            elif c == "skill": opts = SUB["skill"] if len(parts) == 2 else list(sk_all())
            elif c == "theme": opts = list(THEMES) + (["gen", "new", "edit", "reload"] if len(parts) == 2 else [])
            elif c == "think": opts = ["on", "off", "hide", "show", "tail"]
            elif c == "mcp": opts = SUB["mcp"] if len(parts) == 2 else list(cfg["mcp"])
            for o in opts:
                if o.lower().startswith(cur.lower()): yield Completion(o, -len(cur))
            return
        w = t.split(" ")[-1].split("\n")[-1]
        if w.startswith("$"):
            for n, d in sk_all().items():
                if n.startswith(w[1:]): yield Completion("$" + n, -len(w), display_meta=d)
        elif w.startswith("#"):
            for n in cfg["mcp"]:
                if n.startswith(w[1:]): yield Completion("#" + n, -len(w), display_meta="mcp")
        elif w.startswith("@"):
            tk = w[1:].strip('"'); d, pre = os.path.split(tk)
            try: names = os.listdir(d or ".")
            except Exception: return
            for n in sorted(names, key=str.lower):
                if not n.lower().startswith(pre.lower()): continue
                full = os.path.join(d, n); isd = os.path.isdir(full)
                sh = full + (os.sep if isd else "")
                meta = "dir" if isd else ("img" if n.lower().endswith(IMG) else "file")
                yield Completion('@"%s"' % sh if " " in sh else "@" + sh, -len(w), display_meta=meta)

class InLexer(Lexer):
    """Colorea mientras escribes: [Contenido pegado], $skill, #mcp y @archivo."""
    RX = re.compile(PASTE_RX.pattern + "|" + MEN_RX.pattern + "|" + AT_RX.pattern)
    def lex_document(self, doc):
        lines = doc.lines
        def get(i):
            ln, out, pos = lines[i], [], 0
            for m in self.RX.finditer(ln):
                w = m.group(0); cl = ""
                if w.startswith("[Contenido"): cl = "class:pst"
                elif w[0] == "$" and sk_path(w[1:]): cl = "class:msk"
                elif w[0] == "#" and w[1:] in cfg["mcp"]: cl = "class:mmc"
                elif w[0] == "@": cl = "class:mpa"
                if not cl: continue
                if m.start() > pos: out.append(("", ln[pos:m.start()]))
                out.append((cl, w)); pos = m.end()
            out.append(("", ln[pos:])); return out
        return get

kb = KeyBindings()
@kb.add(Keys.BracketedPaste)
def _(e):
    """Pegado (en Windows prompt_toolkit lo emula al detectar varias teclas de golpe). Los saltos de línea NO envían el mensaje."""
    d = e.data.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if d.count("\n") + 1 >= cfg.get("paste_lines", 3) or len(d) > 400:
        i = max(PASTES, default=0) + 1; PASTES[i] = d; n = d.count("\n") + 1
        e.current_buffer.insert_text("[Contenido pegado #%d · %d línea%s]" % (i, n, "s" if n != 1 else ""))
    else: e.current_buffer.insert_text(d)   # pegado corto: se queda en el campo, con sus saltos de línea
@kb.add("backspace")
def _(e):  # borra el marcador de pegado entero de un golpe
    b = e.current_buffer; before = b.document.text_before_cursor; m = None
    for m_ in PASTE_RX.finditer(before): m = m_
    if b.selection_state: b.cut_selection()
    elif m and m.end() == len(before): b.delete_before_cursor(len(m.group(0)))
    else: b.delete_before_cursor(1)
@kb.add("enter")
def _(e):
    b = e.current_buffer
    if b.complete_state and b.complete_state.current_completion: b.apply_completion(b.complete_state.current_completion)
    else: b.validate_and_handle()
@kb.add("escape", "enter")
@kb.add("c-j")
def _(e): e.current_buffer.insert_text("\n")

def short_cwd():
    p = os.getcwd(); h = os.path.expanduser("~")
    if p.lower().startswith(h.lower()): p = "~" + p[len(h):]
    parts = re.split(r"[\\/]", p)
    return p if len(parts) <= 4 else "…" + os.sep + os.sep.join(parts[-3:])

def thk_label():
    if not cfg["think"]: return "off"
    return (kf(cfg["think_budget"]) if cfg["think_budget"] else "on") + {"hide": "·oculto", "full": "·completo"}.get(cfg.get("think_view", "tail"), "")

def toolbar():
    u, c = ST["used"], CTX(); pct = min(100, 100 * u // c) if c else 0
    cl = "tberr" if pct >= 80 else "tbwarn" if pct >= 60 else "tbok"
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
    v = "" if INFO["vis"] is None else (" │ vision ✓" if INFO["vis"] else " │ vision ✗")
    return HTML(" <cwd>⌂ %s</cwd> │ <b>%s</b> │ <%s>ctx %s/%s %s %d%%</%s> │ ↑%s ↓%s │ %.0f t/s │ think %s │ auto %s │ compact ×%d −%s%s " % (
        escape(short_cwd()), escape(cfg["model"] or "?"), cl, kf(u), kf(c), bar, pct, cl, kf(ST["p"]), kf(ST["g"]), ST["tps"],
        thk_label(), "on" if cfg["auto"] else "off", ST["comp"], kf(ST["saved"]), v))

def set_model(name):
    save(); cfg["model"] = name; apply_profile(name); probe(); detect_vision(); banner()

def cmd(msgs, ln):
    c, _, a = ln[1:].partition(" "); a = a.strip()
    if c in ("exit", "q", "quit"): return False
    if c == "new":
        msgs.clear(); PASTES.clear(); ST.update(used=0, p=0, g=0, comp=0, saved=0); con.print(Rule("nueva conversación", style="t.dm", align="left"))
    elif c == "clear": con.clear(); banner()
    elif c == "compact":
        msgs[:] = do_compact(msgs, True)
        if msgs and str(msgs[0].get("content", "")).startswith(SUM_TAG): con.print(Panel(Text(msgs[0]["content"][len(SUM_TAG):].strip()), title="resumen", title_align="left", border_style="t.dm"))
    elif c == "think":
        if a.isdigit(): cfg["think_budget"] = int(a); cfg["think"] = True
        elif a in ("on", "off"): cfg["think"] = a == "on"
        elif a in ("hide", "show", "tail"): cfg["think_view"] = {"hide": "hide", "show": "full", "tail": "tail"}[a]
        else: cfg["think"] = not cfg["think"]
        save(); con.print("razonamiento: %s%s · vista: %s" % ("on" if cfg["think"] else "off", " (presupuesto %s tok)" % (cfg["think_budget"] or "sin límite") if cfg["think"] else "",
                          {"tail": "últimas líneas", "full": "completa", "hide": "oculta"}[cfg.get("think_view", "tail")]))
    elif c == "auto": cfg["auto"] = not cfg["auto"]; save(); con.print("auto =", cfg["auto"])
    elif c in ("model", "models"):
        if a:
            set_model(INFO["models"][int(a) - 1] if a.isdigit() and 0 < int(a) <= len(INFO["models"]) else a)
        else:
            for i, m in enumerate(INFO["models"], 1): con.print("  %d. %s%s" % (i, m, "  [t.ok]◀[/]" if m == cfg["model"] else ""))
            con.print("[t.mu]  /model <n|nombre>[/]")
    elif c == "url" and a: save(); cfg["url"] = a; cfg["model"] = ""; probe(); detect_vision(); banner()
    elif c == "ctx":
        if a: cfg["ctx_manual"] = 0 if a == "auto" else int(a.replace("k", "000")); save()
        con.print("ctx = %d (%s)" % (CTX(), "manual" if cfg["ctx_manual"] else "backend"))
    elif c == "theme":
        s_, _, r_ = a.partition(" "); r_ = re.sub(r"[^\w-]", "", r_.strip())
        if s_ == "gen" and a.partition(" ")[2].strip(): return "$theme-builder Diseña y aplica un tema para esta TUI con theme_save. Idea: " + a.partition(" ")[2].strip()
        if s_ == "reload": load_themes(); set_theme(cfg["theme"] if cfg["theme"] in THEMES else "tokyo"); con.print("temas recargados: " + ", ".join(THEMES))
        elif s_ in ("new", "edit") and r_:
            p = "%s/%s.json" % (TD, r_)
            if s_ == "new" and not os.path.exists(p): json.dump({"base": cfg["theme"], **TH}, open(p, "w", encoding="utf8"), indent=2)
            open_editor(p); load_themes(); cfg["theme"] = r_ if r_ in THEMES else cfg["theme"]; save(); set_theme(cfg["theme"]); con.print("tema '%s' cargado" % cfg["theme"])
        elif a in THEMES:
            cfg["theme"] = a; save(); set_theme(a)
            con.print("  ".join("[%s]■ %s[/]" % (TH[k], k) for k in ("acc", "mod", "tl", "ok", "er", "skill", "mcp", "link", "path")) + "   tema [t.accb]%s[/]" % a)
        else:
            for n in THEMES: con.print("  [%s]■ %s[/]%s%s" % (THEMES[n]["acc"], n, "" if n in BUILTIN else "  [t.mu](propio)[/]", "  ◀" if n == cfg["theme"] else ""))
            con.print("[t.mu]  /theme <nombre> · /theme new <nombre> crea un JSON editable en %s[/]" % TD)
    elif c == "diff":
        if a in ("auto", "on", "off"): cfg["vscode_diff"] = a; save()
        con.print("diff en VSCodium: %s  (auto = solo si la TUI corre dentro de su terminal)" % cfg["vscode_diff"])
    elif c == "info": probe(); detect_vision(True); banner(); con.print(INFO); con.print({k: cfg[k] for k in PROF})
    elif c == "cd" and a: os.chdir(os.path.expanduser(a.strip('"'))); con.print(os.getcwd())
    elif c == "skills" or (c == "skill" and (not a or a == "list")):
        for n, d in sk_all().items(): con.print("  [t.ok]$%s[/]  [t.mu]%s[/]" % (n, d))
        con.print("  [t.mu]MCP: %s[/]" % (" ".join("#" + k for k in cfg["mcp"]) or "(ninguno)"))
    elif c == "skill":
        s, _, r = a.partition(" "); n, _, rest = r.strip().partition(" ")
        if s == "new" and n: sk_new(n, rest.strip())
        elif s == "edit" and sk_path(n): open_editor(sk_path(n))
        elif s == "show" and sk_path(n): con.print(Panel(Text(open(sk_path(n), encoding="utf8").read()), title="$" + n, border_style="t.dm"))
        elif s == "rm" and sk_path(n):
            shutil.rmtree(os.path.dirname(sk_path(n))) if sk_path(n).endswith("SKILL.md") else os.remove(sk_path(n)); con.print("borrada")
        else: con.print("[t.mu]/skill new <nombre> [descripción para generarla con el modelo] | edit | show | rm | list[/]")
    elif c == "mcp":
        s, _, r = a.partition(" "); n, _, rest = r.strip().partition(" ")
        if s == "new" and n:
            p = mcp_scaffold(re.sub(r"[^a-z0-9_-]", "-", n.lower())); con.print("[t.ok]mcp '%s' creado:[/] %s  [t.mu](se activa con #%s)[/]" % (n, p, n))
            if rest: return "$mcp-builder Implementa el servidor MCP '%s' (ya creado con plantilla en %s): %s. Pruébalo con sh antes de terminar." % (n, p, rest)
            open_editor(p)
        elif s == "reload" and n in servers: servers.pop(n).p.kill(); con.print("recargado (se reinicia al mencionar #%s)" % n)
        elif s == "add" and n and rest: cfg["mcp"][n] = {"cmd": rest.strip(), "env": {}}; save(); con.print("mcp '%s' añadido (se activa con #%s)" % (n, n))
        elif s == "rm" and n in cfg["mcp"]: cfg["mcp"].pop(n); save(); con.print("mcp borrado")
        elif s == "tools" and n in cfg["mcp"]:
            try: con.print(mcp_load(n).brief())
            except Exception as e: con.print("[t.er]%s[/]" % e)
        else:
            for k, v in cfg["mcp"].items(): con.print("  [t.tl]#%s[/]  [t.mu]%s%s[/]" % (k, v["cmd"], "  (cargado)" if k in servers else ""))
            con.print("[t.mu]/mcp add <nombre> <comando> | rm | tools <nombre>[/]")
    else:
        for k, v in CMDS.items(): con.print("  [t.acc]/%s[/]  [t.mu]%s[/]" % (k, v))
        con.print("  [t.mu]@ruta adjunta archivo/imagen (o arrástralo) · $skill · #mcp · Esc+Enter nueva línea · Ctrl+C corta[/]")
    return True

def banner():
    c = CTX(); vis = {True: "[t.ok]✓ sí[/]", False: "[t.er]✗ no[/]", None: "[t.mu]? desconocida[/]"}[INFO["vis"]]
    think = ("[t.ok]activo[/] · " + ("sin límite" if not cfg["think_budget"] else kf(cfg["think_budget"]) + " tok") + " · vista " +
             {"tail": "últimas líneas", "full": "completa", "hide": "oculta"}.get(cfg.get("think_view", "tail"), "?")) if cfg["think"] else "[t.mu]desactivado[/]"
    g = Table.grid(padding=(0, 2)); g.add_column(style="t.mu", justify="right"); g.add_column()
    g.add_row("modelo", "[bold]%s[/]  [t.mu]%s · %d modelos[/]" % (cfg["model"] or "[t.er]sin modelo[/]", INFO["be"], len(INFO["models"])))
    g.add_row("contexto", "[bold]%s[/]  [t.mu](%s)[/]" % (kf(c), "manual" if cfg["ctx_manual"] else ("backend" if INFO["ctx"] else "por defecto")))
    g.add_row("visión", vis); g.add_row("razonamiento", think)
    cwd = os.getcwd(); g.add_row("carpeta", Text(cwd, style=con.get_style("t.path") + RStyle(link=res_uri(cwd) or "")))
    g.add_row("atajos", "[t.path]@archivo[/] · [t.skill]$skill[/] · [t.mcp]#mcp[/] · [t.acc]/comandos[/] · Esc+Enter = nueva línea")
    con.print(); con.print(Panel(g, title="[t.accb] ◆ Uy Zona Agent [/]", title_align="left", border_style="t.dm", box=box.ROUNDED, padding=(1, 2)))
    if (INFO.get("slots") or 1) > 1: con.print("  [t.mu]%d slots: si el ctx se ve menor al configurado, lanza llama-server con -np 1[/]" % INFO["slots"])

def prompt_msg():
    w = shutil.get_terminal_size((80, 24)).columns; head = " tú  ⌂ %s " % short_cwd()
    return [("class:rlt", head), ("class:rl", "─" * max(4, w - len(head) - 1)), ("", "\n"), ("class:pr", "❯ ")]

def main():
    msgs = []; seed_skills(); seed_theme_skill(); probe(); detect_vision(); banner()
    if not INFO["models"]: con.print("[t.er]  No hay respuesta del backend en %s[/] [t.mu](/url http://127.0.0.1:1234)[/]\n" % cfg["url"])
    kw = dict(history=FileHistory(H + "/history"), completer=Comp(), complete_while_typing=True, key_bindings=kb, bottom_toolbar=toolbar,
              style=DynamicStyle(lambda: STY), multiline=True, prompt_continuation="  ", reserve_space_for_menu=6, erase_when_done=True, lexer=InLexer())
    try: ses = PromptSession(placeholder=[("class:placeholder", "mensaje · @ archivo/imagen · $ skill · # mcp · / comandos")], **kw)
    except TypeError: ses = PromptSession(**kw)
    first = True
    while True:
        try: ln = ses.prompt(prompt_msg).strip()
        except KeyboardInterrupt: con.print("[t.mu]Ctrl+D o /exit para salir[/]"); continue
        except EOFError: break
        if not ln: continue
        if ln.startswith("/"):
            con.print(Text("  ❯ " + ln, style="t.mu"))
            try:
                r = cmd(msgs, ln)
                if r is False: break
                if isinstance(r, str): turn(msgs, r)
            except Exception as e: con.print("[t.er]%s[/]" % e)
            con.print(); continue
        turn(msgs, ln)
        if first and (INFO["be"] == "ollama" or not INFO["ctx"]): probe()
        first = False

if __name__ == "__main__":
    main()
