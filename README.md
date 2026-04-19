# codemap-zero

**Zero-LLM project scanner for AI agents.** Scan any codebase and get a compact project map so AI uses 50-100x fewer tokens to understand your code.

[![PyPI](https://img.shields.io/pypi/v/codemap-zero)](https://pypi.org/project/codemap-zero/)
[![Python](https://img.shields.io/pypi/pyversions/codemap-zero)](https://pypi.org/project/codemap-zero/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub](https://img.shields.io/github/stars/Jerry4539/codemap?style=social)](https://github.com/Jerry4539/codemap)

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

## Development

```bash
git clone https://github.com/Jerry4539/codemap.git
cd codemap
pip install -e ".[dev]"
codemap scan .
```

## Contributing

Contributions are welcome! Please open an issue or pull request on [GitHub](https://github.com/Jerry4539/codemap).

> **Note:** The PyPI package name is `codemap-zero` (`pip install codemap-zero`), but the CLI command is `codemap`.

## License

MIT — see [LICENSE](LICENSE) for details.

---

Developed by **Jerry4539**
