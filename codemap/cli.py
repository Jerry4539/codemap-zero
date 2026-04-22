"""codemap-zero CLI — zero-LLM project scanner for AI agents.

Provides:
  codemap scan  — full project scan → .md / .json / .html
  codemap serve — launch web dashboard
  codemap ai    — interactive AI Q&A about the project
  codemap menu  — interactive numbered menu
"""

from __future__ import annotations

import os
import sys
import json
import time
from pathlib import Path
from typing import Any

import click

# ── Colour helpers ──────────────────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"


def _c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def _banner() -> None:
    click.echo()
    click.echo(_c("  ╔═══════════════════════════════════════╗", CYAN))
    click.echo(_c("  ║", CYAN) + _c("   codemap-zero", BOLD + GREEN) + _c(" — zero-LLM project scanner  ", DIM) + _c("║", CYAN))
    click.echo(_c("  ╚═══════════════════════════════════════╝", CYAN))
    click.echo()


# ── Pipeline helpers ────────────────────────────────────────────────────────

def _resolve_output(target: str, output: str) -> Path:
    """Resolve output directory relative to target project dir.

    If output is the default 'codemap-zero', make it a subfolder of target.
    Otherwise treat it as user-specified (could be absolute or relative to CWD).
    """
    target_path = Path(target).resolve()
    out = Path(output)
    if not out.is_absolute():
        # Relative path → put it inside the target project directory
        out = target_path / output
    return out.resolve()


def _find_existing_scan(target: str, output_dir: str) -> Path | None:
    """Look for existing PROJECT_MAP.md in codemap-zero/ folder or project root."""
    target_path = Path(target).resolve()
    out_path = _resolve_output(target, output_dir)

    # Check preferred location first (codemap-zero/ subfolder)
    preferred = out_path / "PROJECT_MAP.md"
    if preferred.exists():
        return out_path

    # Fallback: check project root (from older scans)
    root_map = target_path / "PROJECT_MAP.md"
    if root_map.exists():
        return target_path

    return None


def _run_scan(
    target: str,
    output_dir: str,
    no_html: bool = False,
    no_json: bool = False,
    include_ignored: bool = False,
) -> dict[str, Any]:
    """Run the full scan pipeline and return results dict."""
    from codemap import detect, extract, build, cluster, analyze, report, export, viz, docs

    target_path = Path(target).resolve()
    out_path = _resolve_output(target, output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    click.echo(_c("  [1/7]", DIM) + " Detecting project structure...")
    t0 = time.time()
    detection_result = detect.detect(target_path, include_ignored=include_ignored)
    detection = detection_result.to_dict()

    docs_result = docs.extract_docs(
        detection["files"].get("docs", []),
        detection["files"].get("config", []),
        target_path,
    )
    document_nodes = [n for n in docs_result.get("nodes", []) if n.get("type") == "document"]
    section_nodes = [n for n in docs_result.get("nodes", []) if n.get("type") == "section"]
    config_nodes = [n for n in docs_result.get("nodes", []) if n.get("type") == "config"]
    config_keys: list[str] = []
    for cfg in config_nodes:
        for key in cfg.get("keys", []):
            if key not in config_keys:
                config_keys.append(key)
    detection["docs_summary"] = {
        "documents": len(document_nodes),
        "sections": [n.get("label", "") for n in section_nodes[:30]],
        "config_keys": config_keys[:80],
    }
    click.echo(_c(f"         → {detection.get('project_name', '?')} "
                   f"({detection.get('total_files', 0)} files, "
                   f"{detection.get('total_lines', 0):,} lines)", DIM))
    click.echo(_c(f"         → scanned {detection.get('total_dirs_scanned', 0)} dirs, "
                   f"seen {detection.get('total_files_seen', 0)} files, "
                   f"ignored {detection.get('skipped_ignored', 0)}", DIM))

    click.echo(_c("  [2/7]", DIM) + " Extracting AST nodes...")
    code_files = detection["files"].get("code", [])
    ast_result = extract.extract(code_files, target_path)
    node_count = len(ast_result.get("nodes", []))
    edge_count = len(ast_result.get("edges", []))
    click.echo(_c(f"         → {node_count} nodes, {edge_count} edges", DIM))

    click.echo(_c("  [3/7]", DIM) + " Building dependency graph...")
    G = build.build_graph(ast_result)
    click.echo(_c(f"         → {G.number_of_nodes()} nodes, {G.number_of_edges()} edges (stdlib filtered)", DIM))

    click.echo(_c("  [4/7]", DIM) + " Detecting communities...")
    communities, labels, cohesion = cluster.cluster_and_label(G)
    click.echo(_c(f"         → {len(communities)} communities", DIM))

    click.echo(_c("  [5/7]", DIM) + " Analyzing architecture...")
    gods = analyze.god_nodes(G)
    entry_points = analyze.find_entry_points(G)
    architecture = analyze.detect_architecture(G)
    layers = analyze.detect_layers(G)
    circular = analyze.find_circular_deps(G)
    dead = analyze.find_dead_exports(G)
    test_cov = analyze.test_coverage_map(
        detection["files"].get("code", []),
        detection["files"].get("tests", []),
    )
    complexity = analyze.file_complexity(G)
    surprises = analyze.surprising_connections(G, communities)

    click.echo(_c("  [6/7]", DIM) + " Generating report...")
    md_text = report.generate(
        G=G, detection=detection, communities=communities, labels=labels,
        cohesion=cohesion, gods=gods, entry_points=entry_points,
        architecture=architecture, layers=layers, circular_deps=circular,
        dead_exports=dead, test_coverage=test_cov, complexity=complexity,
        surprises=surprises,
    )
    md_path = out_path / "PROJECT_MAP.md"
    md_path.write_text(md_text, encoding="utf-8")
    click.echo(_c(f"         → {md_path}", GREEN))

    click.echo(_c("  [7/7]", DIM) + " Exporting artifacts...")
    if not no_json:
        json_path = str(out_path / "codemap.json")
        json_meta = {
            "project": {
                "name": detection.get("project_name", ""),
                "type": detection.get("project_type", ""),
                "description": detection.get("project_description", ""),
                "languages": detection.get("languages", {}),
                "frameworks": detection.get("frameworks", []),
                "frameworks_by_language": detection.get("frameworks_by_language", {}),
                "dependencies_by_ecosystem": detection.get("dependencies_by_ecosystem", {}),
                "manifests": detection.get("manifest_files", []),
            },
            "scan": {
                "total_files": detection.get("total_files", 0),
                "total_lines": detection.get("total_lines", 0),
                "total_dirs_scanned": detection.get("total_dirs_scanned", 0),
                "total_files_seen": detection.get("total_files_seen", 0),
                "entry_points": detection.get("entry_points", []),
                "docs_summary": detection.get("docs_summary", {}),
                "largest_files": detection.get("largest_files", []),
                "line_heavy_files": detection.get("line_heavy_files", []),
            },
            "analysis": {
                "architecture": architecture,
                "layers": layers,
                "circular_dependencies": circular,
                "dead_exports": dead,
                "complexity": complexity,
                "surprises": surprises,
                "gods": gods,
                "entry_points": entry_points,
                "cohesion": cohesion,
                "labels": labels,
            },
        }
        export.to_json(G, communities, labels, json_path, metadata=json_meta)
        click.echo(_c(f"         → {json_path}", GREEN))

    if not no_html:
        html_path = str(out_path / "codemap.html")
        scan_data = {
            "G": G, "detection": detection, "communities": communities,
            "labels": labels, "cohesion": cohesion, "gods": gods,
            "entry_points": entry_points, "complexity": complexity,
            "surprises": surprises,
        }
        viz.to_html(G, communities, html_path, labels, scan_results=scan_data)
        click.echo(_c(f"         → {html_path}", GREEN))

    elapsed = time.time() - t0
    click.echo()
    click.echo(_c(f"  ✓ Done in {elapsed:.1f}s", GREEN + BOLD))
    click.echo()

    return {
        "G": G, "detection": detection, "communities": communities,
        "labels": labels, "cohesion": cohesion, "gods": gods,
        "entry_points": entry_points, "architecture": architecture,
        "layers": layers, "circular": circular, "dead": dead,
        "test_coverage": test_cov, "complexity": complexity,
        "surprises": surprises, "md_path": str(md_path),
    }


# ── Click CLI ──────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """codemap-zero — zero-LLM project scanner for AI agents.

    Scan any codebase and generate AI-friendly project maps:
    structured Markdown, JSON graph data, and interactive HTML.

    \b
    Quick start:
      codemap scan .              Scan current directory
      codemap menu                Interactive menu
      codemap serve               Web dashboard
      codemap ai                  AI assistant
    """
    if ctx.invoked_subcommand is None:
        _banner()
        click.echo(ctx.get_help())


@cli.command()
@click.argument("target", default=".")
@click.option("-o", "--output", default="codemap-zero", help="Output directory for generated files.")
@click.option("--no-html", is_flag=True, help="Skip HTML visualization.")
@click.option("--no-json", is_flag=True, help="Skip JSON export.")
@click.option("--include-ignored", is_flag=True, help="Include files matched by .gitignore / .codemapignore.")
def scan(target: str, output: str, no_html: bool, no_json: bool, include_ignored: bool) -> None:
    """Scan a project and generate project map files.

    \b
    Examples:
      codemap scan .                    Scan current directory
      codemap scan ~/myproject -o out/  Scan with custom output dir
      codemap scan . --no-html          Skip HTML generation

    Output files are created in a 'codemap-zero/' folder by default.
    """
    _banner()
    _run_scan(target, output, no_html=no_html, no_json=no_json, include_ignored=include_ignored)


@cli.command()
@click.argument("target", default=".")
@click.option("-o", "--output", default="codemap-zero", help="Output directory for generated files.")
@click.option("-p", "--port", default=8787, help="Port for web server.")
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
def serve(target: str, output: str, port: int, host: str) -> None:
    """Launch web dashboard with interactive project visualization.

    First scans the project, then starts a local web server
    with a professional dashboard UI.

    \b
    Examples:
      codemap serve .                   Serve current directory
      codemap serve . -p 9000          Custom port
    """
    _banner()
    click.echo(_c("  Scanning project before launching server...", YELLOW))
    click.echo()
    results = _run_scan(target, output)

    click.echo(_c(f"  Starting web server on http://{host}:{port}", CYAN + BOLD))
    click.echo(_c("  Press Ctrl+C to stop\n", DIM))

    try:
        from codemap.server import create_app
        out_resolved = str(_resolve_output(target, output))
        app = create_app(results, out_resolved)
        app.run(host=host, port=port, debug=False)
    except ImportError:
        click.echo(_c("  Flask not installed. Install with: pip install codemap-zero[web]", RED))
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo(_c("\n  Server stopped.", YELLOW))


@cli.command()
@click.argument("target", default=".")
@click.option("-o", "--output", default="codemap-zero", help="Output directory.")
@click.option("--api-key", envvar="VEDASLAB_API_KEY", help="vedaslab.in API key (or set VEDASLAB_API_KEY env var).")
@click.option("--model", default="gemini-2.5-pro", help="Model: gemini-2.5-pro or claude-4.5")
def ai(target: str, output: str, api_key: str | None, model: str) -> None:
    """Interactive AI assistant for project Q&A.

    Scans the project and lets you ask questions using
    Gemini 2.5 Pro or Claude 4.5 via vedaslab.in API.

    \b
    Examples:
      codemap ai .                             Use default model
      codemap ai . --model claude-4.5          Use Claude
      codemap ai . --api-key YOUR_KEY          Provide API key
    """
    _banner()

    if not api_key:
        click.echo(_c("  No API key provided.", YELLOW))
        click.echo(_c("  Set VEDASLAB_API_KEY env var or use --api-key flag.", DIM))
        click.echo(_c("  (Paste your key below — it will be visible for easy editing)", DIM))
        api_key = click.prompt("  Enter API key")

    # Smart scan: reuse existing results or scan fresh
    existing = _find_existing_scan(target, output)
    if existing:
        click.echo(_c(f"  Found existing scan at {existing}", GREEN))
        click.echo(_c("  Scanning fresh for full context...", YELLOW))
    else:
        click.echo(_c("  Scanning project for context...", YELLOW))
    click.echo()
    results = _run_scan(target, output)

    click.echo(_c(f"  AI Assistant ready ({model})", GREEN + BOLD))
    click.echo(_c("  Type your questions. 'quit' to exit.\n", DIM))

    from codemap.assistant import AIAssistant
    assistant = AIAssistant(api_key=api_key, model=model, scan_results=results)

    while True:
        try:
            question = click.prompt(_c("  you", CYAN), prompt_suffix=_c(" > ", DIM))
            if question.strip().lower() in ("quit", "exit", "q"):
                click.echo(_c("  Goodbye!\n", YELLOW))
                break
            click.echo()
            answer = assistant.ask(question)
            click.echo(_c("  ai", MAGENTA) + _c(" > ", DIM) + answer)
            click.echo()
        except KeyboardInterrupt:
            click.echo(_c("\n  Goodbye!\n", YELLOW))
            break
        except Exception as e:
            click.echo(_c(f"  Error: {e}", RED))


@cli.command()
@click.argument("target", default=".")
@click.option("-o", "--output", default="codemap-zero", help="Output directory.")
def menu(target: str, output: str) -> None:
    """Interactive menu — choose actions by number.

    \b
    Example:
      codemap menu .
    """
    _banner()

    results: dict[str, Any] | None = None

    while True:
        click.echo(_c("  ┌─────────────────────────────────────┐", CYAN))
        click.echo(_c("  │", CYAN) + _c("  What would you like to do?          ", BOLD) + _c("│", CYAN))
        click.echo(_c("  ├─────────────────────────────────────┤", CYAN))
        click.echo(_c("  │", CYAN) + _c("  1 ", GREEN) + "→ Scan project                  " + _c("│", CYAN))
        click.echo(_c("  │", CYAN) + _c("  2 ", GREEN) + "→ Launch web dashboard           " + _c("│", CYAN))
        click.echo(_c("  │", CYAN) + _c("  3 ", GREEN) + "→ Start AI assistant             " + _c("│", CYAN))
        click.echo(_c("  │", CYAN) + _c("  4 ", GREEN) + "→ Show project stats             " + _c("│", CYAN))
        click.echo(_c("  │", CYAN) + _c("  5 ", GREEN) + "→ Open graph in browser          " + _c("│", CYAN))
        click.echo(_c("  │", CYAN) + _c("  6 ", GREEN) + "→ Re-scan (force refresh)        " + _c("│", CYAN))
        click.echo(_c("  │", CYAN) + _c("  0 ", RED) + "→ Exit                           " + _c("│", CYAN))
        click.echo(_c("  └─────────────────────────────────────┘", CYAN))
        click.echo()

        try:
            choice = click.prompt(_c("  Choose", YELLOW), type=str, default="1")
        except (KeyboardInterrupt, EOFError):
            click.echo(_c("\n  Bye!\n", YELLOW))
            break

        choice = choice.strip()
        click.echo()

        if choice == "0":
            click.echo(_c("  Bye!\n", YELLOW))
            break

        elif choice == "1":
            if results:
                click.echo(_c("  Already scanned. Use option 6 to re-scan.", DIM))
            else:
                results = _run_scan(target, output)

        elif choice == "2":
            if not results:
                click.echo(_c("  Scanning first...\n", YELLOW))
                results = _run_scan(target, output)
            try:
                from codemap.server import create_app
                click.echo(_c("  Starting web dashboard on http://127.0.0.1:8787", CYAN + BOLD))
                click.echo(_c("  Press Ctrl+C to stop\n", DIM))
                out_resolved = str(_resolve_output(target, output))
                app = create_app(results, out_resolved)
                app.run(host="127.0.0.1", port=8787, debug=False)
            except ImportError:
                click.echo(_c("  Flask not installed. Run: pip install codemap-zero[web]", RED))
            except KeyboardInterrupt:
                click.echo(_c("\n  Server stopped.\n", YELLOW))

        elif choice == "3":
            if not results:
                click.echo(_c("  Scanning first...\n", YELLOW))
                results = _run_scan(target, output)
            api_key = os.environ.get("VEDASLAB_API_KEY")
            if not api_key:
                click.echo(_c("  (Paste your key below — it will be visible for easy editing)", DIM))
                api_key = click.prompt("  Enter API key")
            model = click.prompt(_c("  Model", YELLOW), default="gemini-2.5-pro",
                                 type=click.Choice(["gemini-2.5-pro", "claude-4.5"]))
            from codemap.assistant import AIAssistant
            assistant = AIAssistant(api_key=api_key, model=model, scan_results=results)
            click.echo(_c(f"\n  AI Assistant ready ({model}). 'quit' to return.\n", GREEN))
            while True:
                try:
                    q = click.prompt(_c("  you", CYAN), prompt_suffix=_c(" > ", DIM))
                    if q.strip().lower() in ("quit", "exit", "q", "back"):
                        break
                    click.echo()
                    ans = assistant.ask(q)
                    click.echo(_c("  ai", MAGENTA) + _c(" > ", DIM) + ans)
                    click.echo()
                except KeyboardInterrupt:
                    break

        elif choice == "4":
            if not results:
                click.echo(_c("  Scanning first...\n", YELLOW))
                results = _run_scan(target, output)
            _show_stats(results)

        elif choice == "5":
            html_file = _resolve_output(target, output) / "codemap.html"
            if html_file.exists():
                import webbrowser
                webbrowser.open(str(html_file))
                click.echo(_c(f"  Opened {html_file} in browser.\n", GREEN))
            else:
                click.echo(_c("  No codemap.html found. Run a scan first (option 1).\n", RED))

        elif choice == "6":
            results = _run_scan(target, output)

        else:
            click.echo(_c(f"  Unknown option: {choice}\n", RED))


def _show_stats(results: dict[str, Any]) -> None:
    """Print project statistics."""
    det = results["detection"]
    G = results["G"]
    comms = results["communities"]
    labels = results["labels"]
    gods = results["gods"]

    click.echo(_c("  ╔═══════════════════════════════════════╗", BLUE))
    click.echo(_c("  ║", BLUE) + _c("         PROJECT STATISTICS            ", BOLD) + _c("║", BLUE))
    click.echo(_c("  ╠═══════════════════════════════════════╣", BLUE))

    stats = [
        ("Project", det.get("project_name", "?")),
        ("Type", det.get("project_type", "?")),
        ("Files", str(det.get("total_files", 0))),
        ("Lines", f"{det.get('total_lines', 0):,}"),
        ("Graph nodes", str(G.number_of_nodes())),
        ("Graph edges", str(G.number_of_edges())),
        ("Communities", str(len(comms))),
    ]

    for label, value in stats:
        line = f"  {label:<18} {value}"
        click.echo(_c("  ║", BLUE) + f"  {label:<18} " + _c(value, GREEN) + " " * max(0, 37 - len(label) - len(value) - 2) + _c("║", BLUE))

    click.echo(_c("  ╠═══════════════════════════════════════╣", BLUE))
    click.echo(_c("  ║", BLUE) + _c("  Modules:                            ", DIM) + _c("║", BLUE))
    for cid, members in sorted(comms.items(), key=lambda x: len(x[1]), reverse=True)[:8]:
        label_str = labels.get(cid, f"Module {cid}")
        line = f"    {label_str} ({len(members)} nodes)"
        click.echo(_c("  ║", BLUE) + f"  {line:<37}" + _c("║", BLUE))

    click.echo(_c("  ╠═══════════════════════════════════════╣", BLUE))
    click.echo(_c("  ║", BLUE) + _c("  Most Connected:                     ", DIM) + _c("║", BLUE))
    for g in gods[:5]:
        label_str = g.get("label", g["id"])
        line = f"    {label_str} ({g['degree']})"
        click.echo(_c("  ║", BLUE) + f"  {line:<37}" + _c("║", BLUE))

    click.echo(_c("  ╚═══════════════════════════════════════╝", BLUE))
    click.echo()


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
