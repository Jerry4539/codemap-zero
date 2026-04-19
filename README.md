# codemap-zero

**Zero-LLM project scanner for AI agents.** Scan any codebase and get a compact project map so AI uses 50-100x fewer tokens to understand your code.

[![PyPI](https://img.shields.io/pypi/v/codemap-zero)](https://pypi.org/project/codemap-zero/)
[![Python](https://img.shields.io/pypi/pyversions/codemap-zero)](https://pypi.org/project/codemap-zero/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub](https://img.shields.io/github/stars/Jerry4539/codemap-zero?style=social)](https://github.com/Jerry4539/codemap-zero)

## What it does

```
Your Project (50,000+ lines)  →  codemap-zero  →  PROJECT_MAP.md (~3K tokens)
                                                →  codemap.json (full graph)
                                                →  codemap.html (interactive viz)
```

- **AST-level extraction** — parses 20+ languages via tree-sitter
- **Dependency graph** — imports, calls, class hierarchies as a directed graph
- **Community detection** — auto-discovers logical modules (Louvain/Leiden)
- **Architecture analysis** — god nodes, circular deps, dead code, layers
- **Zero LLM tokens** — everything is deterministic static analysis

## Install

```bash
pip install codemap-zero
```

With extras:

```bash
pip install codemap-zero[web]   # web dashboard (Flask)
pip install codemap-zero[ai]    # AI assistant (vedaslab.in API)
pip install codemap-zero[all]   # everything
```

## Quick Start

### Scan a project

```bash
codemap scan .
```

Generates `PROJECT_MAP.md`, `codemap.json`, and `codemap.html` in the current directory.

### Interactive menu

```bash
codemap menu .
```

Choose actions by number — scan, launch dashboard, AI assistant, stats.

### Web dashboard

```bash
codemap serve .
```

Opens a professional web dashboard at `http://localhost:8787` with interactive graph visualization, module explorer, and complexity analysis.

### AI assistant

```bash
export VEDASLAB_API_KEY=your-key
codemap ai .
```

Chat with AI about your project using multiple providers (Vedaslab.in, OpenAI, Google Gemini, Anthropic Claude). The AI gets full project context from the scan.

## CLI Reference

```
codemap scan [TARGET] [OPTIONS]    Scan project and generate maps
  -o, --output DIR                 Output directory (default: .)
  --no-html                        Skip HTML generation
  --no-json                        Skip JSON export

codemap serve [TARGET] [OPTIONS]   Launch web dashboard
  -p, --port PORT                  Port (default: 8787)
  --host HOST                      Host (default: 127.0.0.1)

codemap ai [TARGET] [OPTIONS]      Interactive AI assistant
  --api-key KEY                    API key (supports vedaslab, openai, gemini, claude)
  --model MODEL                    Model name (e.g. gpt-4o, gemini-2.5-pro)

codemap menu [TARGET]              Interactive menu mode
```

## Supported Languages

Python, JavaScript, TypeScript, TSX, Go, Rust, Java, C, C++, C#, Ruby, Kotlin, Scala, PHP, Swift, Lua, Zig, PowerShell, Elixir, Julia — plus Markdown, JSON, YAML, TOML configs.

## How It Works

1. **Detect** — finds project type, frameworks, entry points, file structure
2. **Extract** — parses every source file into AST nodes (files, classes, functions, imports)
3. **Build** — constructs a directed graph with import/call/containment edges
4. **Cluster** — detects communities using Louvain algorithm, auto-labels them
5. **Analyze** — finds god nodes, entry points, circular deps, dead code, architecture patterns
6. **Report** — generates a token-optimized Markdown summary
7. **Export** — outputs JSON graph data and interactive HTML visualization

## 🤖 Agent Prompt — Copy & Paste to Any AI Agent

Give any AI coding agent (GitHub Copilot, Cursor, Claude, ChatGPT, Windsurf, Cline, etc.) instant full-project awareness. Just copy the prompt below and paste it at the start of your chat session.

### Step 1 — Install codemap-zero

**Windows (PowerShell):**
```powershell
pip install codemap-zero
```

**Mac / Linux (Terminal):**
```bash
pip install codemap-zero
```

### Step 2 — Scan your project

**Windows:**
```powershell
cd C:\path\to\your\project
codemap scan .
```

**Mac / Linux:**
```bash
cd /path/to/your/project
codemap scan .
```

This creates three files:
| File | What it contains |
|---|---|
| `PROJECT_MAP.md` | Compact codebase summary (~3K tokens instead of 50K+) |
| `codemap.json` | Full dependency graph as structured data |
| `codemap.html` | Interactive visualization (open in browser) |

### Step 3 — Copy this prompt and paste it to your AI agent

<table><tr><td>

**📋 Copy the entire prompt below:**

</td></tr></table>

<details open>
<summary><strong>Click to expand the prompt</strong></summary>

<textarea readonly rows="42" cols="100" style="width:100%; font-family:monospace; font-size:13px; padding:12px; background:#0d1117; color:#e6edf3; border:1px solid #30363d; border-radius:8px;" onclick="this.select()">
You have access to a project that has been scanned with codemap-zero. Before doing anything else, read the file PROJECT_MAP.md in the project root. This file is your primary codebase context.

PROJECT_MAP.md contains:
- Complete project structure with every file, class, function, and their relationships
- Import and call dependency graph between all modules
- Auto-detected logical clusters/modules (e.g. "auth", "database", "api", "ui")
- Architecture analysis: entry points, god nodes, circular dependencies, dead code
- Complexity and coupling metrics per file
- Framework and language detection

USE THIS FOR SMART TOKEN MANAGEMENT:
- Do NOT read every file to understand the project. PROJECT_MAP.md already has a compressed summary of the entire codebase in ~3K tokens instead of 50K+.
- When you need to edit a file, check PROJECT_MAP.md first to see what depends on that file and what it depends on. This avoids breaking changes.
- When adding features, check which cluster/module it belongs to and follow existing patterns.
- When answering questions about the codebase, refer to PROJECT_MAP.md first. Only read individual files when you need exact implementation details.

USE THIS FOR MEMORY MANAGEMENT:
- Treat PROJECT_MAP.md as your persistent project memory. It captures the full architecture in a compact format that fits in your context window.
- If you have a memory/notes system, store the key architectural insights from PROJECT_MAP.md there: the main clusters, entry points, critical dependencies, and known issues (god nodes, circular deps).
- When the conversation gets long, you don't need to re-read source files. PROJECT_MAP.md has the structural truth.
- After making significant changes (new files, moved modules, renamed things), ask the user to re-run "codemap scan ." and re-read the updated PROJECT_MAP.md.

RULES:
1. Always read PROJECT_MAP.md FIRST before starting any task.
2. Use the dependency graph to understand impact before editing any file.
3. Never read files one-by-one to "explore" — the map already tells you the structure.
4. If PROJECT_MAP.md shows circular dependencies or god nodes, flag them to the user.
5. When suggesting refactors, reference the cluster/module structure from the map.
6. If codemap.json exists, you can parse it for programmatic access to the full graph data.

This approach saves 50-100x tokens compared to reading every file individually.
</textarea>

</details>

> **Tip:** Click inside the text box and press `Ctrl+A` (Windows) or `Cmd+A` (Mac) to select all, then copy.

### Why this works

| Without codemap-zero | With codemap-zero |
|---|---|
| AI reads files one-by-one | AI reads one 3K-token map |
| Burns 50K–100K+ tokens exploring | Full context in seconds |
| Misses dependencies, breaks things | Sees the full dependency graph |
| Forgets project structure mid-chat | Compact map fits in context window |
| No architecture awareness | Knows clusters, god nodes, dead code |

## Development

```bash
git clone https://github.com/Jerry4539/codemap-zero.git
cd codemap-zero
pip install -e ".[dev]"
codemap scan .
```

## Contributing

Contributions are welcome! Please open an issue or pull request on [GitHub](https://github.com/Jerry4539/codemap-zero).

> **Note:** The PyPI package name is `codemap-zero` (`pip install codemap-zero`), but the CLI command is `codemap`.

## License

MIT — see [LICENSE](LICENSE) for details.

---

Developed by **Jerry4539**
