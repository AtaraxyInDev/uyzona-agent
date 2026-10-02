# Uy Zona Agent

> **Agente TUI ligero para LLMs locales** (Windows · Python)
> Un solo archivo. Sin backend en la nube. Sin suscripciones. Tu modelo, tu máquina.

![status](https://img.shields.io/badge/estado-estable-success) ![python](https://img.shields.io/badge/python-3.9+-blue) ![os](https://img.shields.io/badge/OS-Windows-0078D4)

---

## 🎯 Primicia

**Uy Zona Agent** es un **agente de terminal (TUI)** que conecta tu LLM local —ya sea servido por **llama.cpp / llama-server**, **LM Studio**, **Ollama** o cualquier endpoint **OpenAI-compatible** (`/v1`)— con un set de **tools** que le permiten actuar sobre tu sistema: ejecutar comandos, leer/escribir/editar archivos, buscar en el disco, hacer HTTP, y extenderse con **MCP** (Model Context Protocol) y **skills** reutilizables.

Todo corre **localmente**. Nada sale de tu máquina salvo lo que tú explícitamente le pides que busque/fetchee.

---

## ✨ Características principales

| Área | Detalle |
|---|---|
| **Backends soportados** | llama.cpp (`llama-server`), LM Studio, Ollama, cualquier API OpenAI-compatible |
| **Tool-calling nativo** | El modelo decide cuándo y qué tool invocar (JSON functions) |
| **Visión** | Detecta automáticamente si el modelo soporta imágenes; adjunta PNG/JPEG arrastrando al prompt |
| **Thinking / reasoning** | Toggle por modelo (`think`, `think_budget`) y vista configurable (`hide` / `tail` / `full`) |
| **Contexto manual** | `ctx_manual` por modelo (ej. 64 000 tokens) |
| **Compaction automática** | Resume la conversación cuando el contexto llega a `compact_at` (por defecto 0.8) |
| **Temas** | 5 temas built-in (tokyo, dracula, gruvbox, nord, mono) + temas propios vía `theme_save` |
| **Skills** | Instrucciones reutilizables en Markdown que el modelo aplica bajo demanda (`$skill`) |
| **MCP** | Servidores MCP propios (Python, stdlib) o externos (`npx`, `uvx`, `.exe`), activados con `#nombre` |
| **Historial** | Persistente (`prompt_toolkit FileHistory`) |
| **Diffs** | Vista unificada de cambios + apertura opcional en VS Code (`vscode_diff: auto`) |
| **Aprobación de tools** | Modo interactivo (pregunta antes de cada tool) o `auto: true` (sin preguntas) |
| **Sampler** | Parámetros de muestreo por modelo (temp, top_p, etc.) |

---

## 🧰 Tools integradas

| Tool | Descripción |
|---|---|
| `sh` | Ejecuta **un** comando PowerShell; devuelve salida + exit code |
| `read` | Lee un archivo de texto con números de línea |
| `write` | Crea o sobreescribe un archivo completo |
| `edit` | Reemplaza un snippet exacto dentro de un archivo (diff visual) |
| `grep` | Búsqueda recursiva por regex en archivos |
| `glob` | Lista archivos que matchean un patrón |
| `fetch` | HTTP GET a una URL → texto legible |
| `mcp` | Invoca una tool de un servidor MCP cargado |
| `mcp_add` | Registra un servidor MCP (scaffolding Python o comando externo) |
| `theme_save` | Crea/actualiza un tema de color y lo aplica al instante |
| `skill_save` | Crea/actualiza una skill global |

> Las tools de solo-lectura (`ls`, `cat`, `git status`, …) se aprueban automáticamente; el resto depende de `auto`.

---

## 📁 Estructura

```
.uyzona/
├── uyzona.py          # el agente (único archivo necesario)
├── config.json        # configuración (URL, modelo, perfiles, tema, MCP)
├── uyzona.cmd         # lanzador de Windows (opcional)
├── history            # historial de prompts
├── mcp/              # servidores MCP propios
│   └── <nombre>/server.py
├── skills/           # skills reutilizables
│   └── <nombre>/SKILL.md
└── themes/           # temas propios
    └── <nombre>.json
```

---

## ⚙️ Configuración (`config.json`)

```jsonc
{
  "url": "http://127.0.0.1:8080/v1",   // endpoint del backend
  "model": "Qwen3.8-27b-ISTA",          // modelo activo
  "think": false,                        // reasoning on/off (global)
  "think_budget": 0,
  "sampler": {},
  "vis": true,                           // null = autodetectar
  "ctx_manual": 64000,
  "temp": 0.7,
  "auto": true,                          // no pedir permiso para tools
  "theme": "tokyo",
  "think_view": "hide",                 // hide | tail | full
  "compact_at": 0.8,
  "tool_max": 5000,
  "img_max": 1024,
  "models": {                            // perfiles POR modelo
    "Qwen3.8-27b-ISTA": { "think": false, "ctx_manual": 64000, "vis": true }
  },
  "mcp": {
    "searxng": {
      "cmd": "python C:\\...\\mcp\\searxng\\server.py",
      "env": {}
    }
  }
}
```

Las claves **por modelo** (`think`, `think_budget`, `ctx_manual`, `sampler`, `vis`) se guardan automáticamente al cambiar de modelo.

---

## 🚀 Uso

### Instalación

```powershell
pip install rich prompt_toolkit
# opcional (mejor manejo de imágenes):
pip install pillow
```

### Arranque

```powershell
python uyzona.py
# o, en Windows:
uyzona.cmd
```

> La primera ejecución crea la carpeta `~/.uyzona/` con su `config.json` (defaults).
> Ahí viven tu configuración, skills, MCP y temas propios.

### Atajo global (opcional)

Para poder escribir `uyzona` desde cualquier carpeta del terminal, añade la carpeta donde vive el agente a la **variable de entorno `PATH` del sistema**:

1. `Win + R` → `sysdm.cpl` → **Avanzado** → **Variables de entorno**.
2. Edita `Path` (del sistema) y añade una nueva entrada con la ruta a la carpeta del agente, ej.:
   ```
   C:\Users\Ruta\uyzona
   ```
3. Acepta y **reinicia el terminal**.

Ahora, en cualquier PowerShell:

```powershell
uyzona
```

> `uyzona.cmd` usa `%~dp0` para localizar `uyzona.py` relativo a su propia carpeta, así funciona desde cualquier `cwd`.

### Sintaxis del prompt

| Prefijo | Acción |
|---|---|
| `@archivo` | Adjuntar archivo / imagen |
| `$skill` | Usar una skill |
| `#mcp` | Cargar un servidor MCP |
| `/comando` | Slash-commands internos |
| `Esc + Enter` o `Ctrl + J` | Nueva línea |

### Ejemplo de sesión

```
> resume el repo ./openbor y dime qué ramas hay
  [sh] git -C ./openbor branch -a
  master
  release/1.0
  ...

> edita el README y cambia el título a "OpenBOR 2"
  [read] README.md
  [edit] README.md  (diff)
  + # OpenBOR 2
  - # OpenBOR
```

---

## 🧩 Skills

Instrucciones en Markdown que el modelo aplica cuando las menciona (`$nombre`) o cuando su `trigger: auto` lo indica.

```
skills/
└── html-standard-design/SKILL.md   # ejemplo: paleta + estructura obligatoria
```

Cada skill es un archivo `SKILL.md` con front-matter:

```markdown
---
name: mi-skill
description: una línea de qué hace y cuándo usarla
trigger: auto          # opcional
keywords: [a, b, c]    # opcional
---
# Cuerpo en Markdown
```

---

## 🔌 MCP (Model Context Protocol)

Servidores por **stdio**, JSON-RPC 2.0, un JSON por línea.

- **Propio:** `mcp_add(name)` → scaffolding en `mcp/<nombre>/server.py` (Python, solo stdlib). Añades funciones con `@tool("desc", param="tipo")`.
- **Externo:** `mcp_add(name, cmd="npx -y paquete")`.
- **Activación:** menciona `#nombre` en un mensaje; se carga bajo demanda y se recarga si el archivo cambia.

---

## 🎨 Temas

- **Built-in:** `tokyo`, `dracula`, `gruvbox`, `nord`, `mono`
- **Propios:** `theme_save(name, colors, base?)` → se guarda en `themes/<nombre>.json` y se aplica al instante.
- Todos son **oscuros** (el fondo de la terminal no se controla).
- Cambio en vivo: `/theme <nombre>`

---

## 🔒 Privacidad

- Todo corre en **localhost**.
- No hay telemetría, ni logs en la nube, ni API keys.
- Lo único que sale de tu máquina es lo que tú le pides explícitamente (`fetch`, MCP de búsqueda, etc.).

---

## 📄 Licencia

MIT — haz con él lo que quieras.

---

## 📮 Contacto

Creado por **AtaraxInDev**
