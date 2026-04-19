"""Generate PROJECT_MAP.md — a token-optimized project summary for AI agents.

The output is structured for machine consumption: compact, scannable,
high information density. Target: 2,000-5,000 tokens for a medium project.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text (~1.3 words per token for English/code)."""
    words = len(text.split())
    return int(words * 100 / 75)


def generate(
    G: nx.DiGraph,
    detection: dict[str, Any],
    communities: dict[int, list[str]],
    labels: dict[int, str],
    cohesion: dict[int, float],
    gods: list[dict[str, Any]],
    entry_points: list[dict[str, Any]],
    architecture: list[str],
    layers: dict[str, list[str]],
    circular_deps: list[list[str]],
    dead_exports: list[dict[str, Any]],
    test_coverage: dict[str, str | None],
    complexity: list[dict[str, Any]],
    surprises: list[dict[str, Any]],
) -> str:
    """Generate the PROJECT_MAP.md content."""
    lines: list[str] = []

    project_name = detection.get("project_name", "Project")
    project_type = detection.get("project_type", "unknown")
    project_desc = detection.get("project_description", "")
    frameworks = detection.get("frameworks", [])
    total_files = detection.get("total_files", 0)
    total_lines = detection.get("total_lines", 0)
    estimated_tokens = detection.get("estimated_tokens", 0)

    # ── Header ──
    lines.append(f"# Project Map: {project_name}\n")

    # ── Overview ──
    lines.append("## Overview\n")
    type_str = f"{project_type.title()} project" if project_type != "unknown" else "Project"
    fw_str = f" ({', '.join(frameworks)})" if frameworks else ""
    lines.append(f"{type_str}{fw_str} · {total_files} files · {total_lines:,} lines · "
                 f"{G.number_of_nodes()} nodes · {G.number_of_edges()} edges · "
                 f"{len(communities)} modules\n")
    if project_desc:
        lines.append(f"{project_desc}\n")

    files = detection.get("files", {})
    file_counts = []
    for cat in ("code", "tests", "docs", "config"):
        count = len(files.get(cat, []))
        if count:
            file_counts.append(f"{cat}: {count}")
    if file_counts:
        lines.append(f"Files: {' · '.join(file_counts)}\n")

    # ── Architecture ──
    if architecture or layers:
        lines.append("## Architecture\n")
        if architecture:
            lines.append(f"Patterns: {', '.join(architecture)}\n")
        if layers:
            for layer_name, layer_files in layers.items():
                short = ", ".join(layer_files[:5])
                extra = f" +{len(layer_files) - 5} more" if len(layer_files) > 5 else ""
                lines.append(f"- **{layer_name}**: {short}{extra}")
            lines.append("")

    # ── Entry Points (capped at 5) ──
    det_entries = detection.get("entry_points", [])
    if det_entries or entry_points:
        lines.append("## Entry Points\n")
        seen = set()
        for ep in det_entries[:3]:
            lines.append(f"- `{ep}`")
            seen.add(ep)
        for ep in entry_points[:3]:
            label = ep.get("label", "")
            if label not in seen:
                lines.append(f"- `{label}` (imports {ep.get('imports', 0)} modules)")
                seen.add(label)
        lines.append("")

    # ── Key Components ──
    if gods:
        lines.append("## Key Components (Most Connected)\n")
        for g in gods[:10]:
            label = g.get("label", g["id"])
            ntype = g.get("type", "")
            degree = g.get("degree", 0)
            src = g.get("source_file", "")
            type_tag = f" [{ntype}]" if ntype else ""
            lines.append(f"- **{label}**{type_tag} — {degree} connections"
                         f"{f' ({src})' if src else ''}")
        lines.append("")

    # ── Module Map (Communities) ──
    if communities:
        lines.append("## Module Map\n")
        sorted_comms = sorted(communities.items(), key=lambda x: len(x[1]), reverse=True)
        for cid, members in sorted_comms:
            label = labels.get(cid, f"Module {cid}")
            score = cohesion.get(cid, 0)
            size = len(members)

            file_nodes = []
            symbol_nodes = []
            signatures = []
            for m in members:
                data = G.nodes.get(m, {})
                if data.get("type") == "file":
                    file_label = data.get("label", m)
                    docstring = data.get("docstring", "")
                    if docstring:
                        file_nodes.append(f"`{file_label}` — {docstring[:60]}")
                    else:
                        file_nodes.append(f"`{file_label}`")
                elif data.get("type") in ("class", "function"):
                    sym_label = data.get("label", m)
                    sig = data.get("signature", "")
                    if sig:
                        signatures.append(f"`{sig}`")
                    else:
                        symbol_nodes.append(data.get("label", m))

            lines.append(f"### {label} ({size} nodes, cohesion: {score:.2f})\n")
            if file_nodes:
                lines.append(f"Files: {', '.join(file_nodes[:8])}"
                             f"{f' +{len(file_nodes) - 8} more' if len(file_nodes) > 8 else ''}")
            if signatures:
                lines.append(f"Signatures: {', '.join(signatures[:6])}"
                             f"{f' +{len(signatures) - 6} more' if len(signatures) > 6 else ''}")
            elif symbol_nodes:
                lines.append(f"Key symbols: {', '.join(f'`{s}`' for s in symbol_nodes[:8])}"
                             f"{f' +{len(symbol_nodes) - 8} more' if len(symbol_nodes) > 8 else ''}")
            lines.append("")

    # ── Dependency Flow (cross-community) ──
    if surprises:
        lines.append("## Cross-Module Dependencies\n")
        for s in surprises[:8]:
            arrow = "→"
            lines.append(f"- `{s['source']}` {arrow} `{s['target']}` ({s['relation']})")
        lines.append("")

    # ── Complexity Hotspots ──
    if complexity:
        top_complex = [c for c in complexity if c["complexity_score"] > 0][:5]
        if top_complex:
            lines.append("## Complexity Hotspots\n")
            for c in top_complex:
                lines.append(f"- `{c['label']}` — {c['symbols']} symbols, "
                             f"{c['connections']} connections, {c['lines']} lines")
            lines.append("")

    # ── Warnings ──
    warnings: list[str] = []
    if circular_deps:
        for cycle in circular_deps[:3]:
            warnings.append(f"Circular dep: {' ↔ '.join(cycle)}")
    if dead_exports:
        dead_str = ", ".join(f"`{d['label']}`" for d in dead_exports[:5])
        extra = f" +{len(dead_exports) - 5} more" if len(dead_exports) > 5 else ""
        warnings.append(f"Possibly unused: {dead_str}{extra}")
    untested = [f for f, t in test_coverage.items() if t is None]
    if untested:
        warnings.append(f"No tests for: {', '.join(f'`{Path(f).name}`' for f in untested[:5])}"
                        f"{f' +{len(untested) - 5} more' if len(untested) > 5 else ''}")

    if warnings:
        lines.append("## Warnings\n")
        for w in warnings:
            lines.append(f"⚠ {w}")
        lines.append("")

    # ── Navigation Guide ──
    lines.append("## How to Navigate\n")
    if det_entries:
        lines.append(f"- **Start here**: {', '.join(f'`{e}`' for e in det_entries[:3])}")
    if gods:
        core = [g['label'] for g in gods[:3] if g.get('type') == 'file']
        if core:
            lines.append(f"- **Core logic**: {', '.join(f'`{c}`' for c in core)}")
    lines.append(f"- **Full graph**: see `codemap.json` ({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)")
    lines.append(f"- **Interactive view**: open `codemap.html` in browser")
    lines.append("")

    # Build report text
    report = "\n".join(lines)

    # Dynamic token estimate
    map_tokens = _estimate_tokens(report)
    token_line = f"Raw corpus: ~{estimated_tokens:,} tokens. This map: ~{map_tokens:,} tokens."
    if estimated_tokens > 0:
        ratio = estimated_tokens / max(map_tokens, 1)
        token_line += f" ({ratio:.0f}x reduction)"

    # Insert token info after overview
    report = report.replace(
        f"Files: {' · '.join(file_counts)}\n" if file_counts else f"{len(communities)} modules\n",
        (f"Files: {' · '.join(file_counts)}\n\n{token_line}\n" if file_counts
         else f"{len(communities)} modules\n\n{token_line}\n"),
        1,
    )

    report += "\n---\n"
    report += f"*Generated by codemap-zero v0.1.1 · {total_files} files scanned · zero LLM tokens used*\n"

    return report
