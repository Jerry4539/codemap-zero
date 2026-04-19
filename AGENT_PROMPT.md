# Agent Prompt — Copy & Paste This to Any AI Agent

> Copy the prompt below and give it to any AI coding agent (Copilot, Cursor, Claude, ChatGPT, Windsurf, etc.) at the start of your session. The agent will scan your project first and use the compact map as memory, drastically reducing token usage while giving it full codebase awareness.

---

## The Prompt

````markdown
Before you start working on my codebase, run the following steps to build a project map so you have full context with minimal tokens:

### Step 1 — Install codemap-zero (one-time)

```bash
pip install codemap-zero
```

### Step 2 — Scan the project

```bash
codemap scan .
```

This generates three files in the current directory:
- `PROJECT_MAP.md` — a compact, token-optimized summary of the entire codebase (~3K tokens instead of 50K+)
- `codemap.json` — the full dependency graph as structured data
- `codemap.html` — an interactive visualization (open in browser)

### Step 3 — Read the project map

Read the `PROJECT_MAP.md` file and use it as your codebase context. It contains:
- Project structure with all files, classes, functions, and their relationships
- Import/call dependency graph between modules
- Auto-detected logical clusters (e.g. "auth", "database", "api", "ui")
- Architecture analysis: entry points, god nodes, circular dependencies, dead code
- Complexity and coupling metrics per file

### How to use this context

- **Before editing any file**, check PROJECT_MAP.md to understand where that file sits in the dependency graph and which other files depend on it.
- **Before adding a new feature**, check which cluster/module it belongs to and follow the existing patterns in that cluster.
- **Before refactoring**, review the circular dependencies and god nodes sections to prioritize what to fix.
- **When answering questions** about the codebase, refer to the project map instead of reading every file individually.

### Re-scan after major changes

If you make significant structural changes (new files, moved modules, changed imports), re-run:

```bash
codemap scan .
```

Then re-read `PROJECT_MAP.md` to update your context.

### Quick reference

| Command | What it does |
|---|---|
| `codemap scan .` | Full scan → .md + .json + .html |
| `codemap scan . --no-html` | Skip HTML visualization |
| `codemap serve .` | Launch interactive web dashboard at localhost:8787 |
| `codemap menu .` | Interactive CLI menu |

The project map is generated using **zero LLM tokens** — it's pure static analysis via tree-sitter AST parsing across 20+ languages. This means the map is deterministic, fast, and free.
````

---

## Why This Works

Traditional approach: The AI reads files one by one, burning 50K–100K+ tokens just to understand project structure.

With codemap-zero: The AI reads a single ~3K token file and immediately knows:
- Every file, class, and function in the project
- How they connect (imports, calls, inheritance)
- Which logical modules exist and what they do
- Where the problems are (god nodes, circular deps, dead code)

**Result: 50–100x fewer tokens, faster responses, better code suggestions.**

---

## Install

```bash
pip install codemap-zero
```

GitHub: [https://github.com/Jerry4539/codemap-zero](https://github.com/Jerry4539/codemap-zero)
PyPI: [https://pypi.org/project/codemap-zero/](https://pypi.org/project/codemap-zero/)
