"""Generate PROJECT_MAP.md — a token-optimized project summary for AI agents.

The output is structured for machine consumption: compact, scannable,
high information density. Target: 2,000-5,000 tokens for a medium project.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx

from codemap import __version__


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
    languages = detection.get("languages", {})
    frameworks_by_language = detection.get("frameworks_by_language", {})
    dependencies_by_ecosystem = detection.get("dependencies_by_ecosystem", {})
    manifest_files = detection.get("manifest_files", [])
    docs_summary = detection.get("docs_summary", {})
    total_files = detection.get("total_files", 0)
    total_lines = detection.get("total_lines", 0)
    estimated_tokens = detection.get("estimated_tokens", 0)
    total_dirs_scanned = detection.get("total_dirs_scanned", 0)
    total_files_seen = detection.get("total_files_seen", 0)
    skipped_ignored = detection.get("skipped_ignored", 0)
    skipped_binary = detection.get("skipped_binary", 0)
    extensionless_included = detection.get("extensionless_included", 0)
    skipped_limit = detection.get("skipped_limit", 0)
    largest_files = detection.get("largest_files", [])
    line_heavy_files = detection.get("line_heavy_files", [])

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
    det_entries = detection.get("entry_points", [])
    file_counts = []
    for cat in ("code", "tests", "docs", "config"):
        count = len(files.get(cat, []))
        if count:
            file_counts.append(f"{cat}: {count}")
    if file_counts:
        lines.append(f"Files: {' · '.join(file_counts)}\n")

    # ── Scan Coverage ──
    lines.append("## Scan Coverage\n")
    lines.append(
        f"Scanned {total_dirs_scanned} directories and visited {total_files_seen} files. "
        f"Included {total_files} files in the map."
    )
    lines.append(
        f"Skipped: ignored={skipped_ignored}, binary/generated={skipped_binary}, "
        f"limit={skipped_limit}. Included extensionless files: {extensionless_included}\n"
    )

    extra_counts = []
    for cat in ("images", "other"):
        count = len(files.get(cat, []))
        if count:
            extra_counts.append(f"{cat}: {count}")
    if extra_counts:
        lines.append(f"Additional coverage: {' · '.join(extra_counts)}\n")

    # ── Languages & Frameworks ──
    if languages or frameworks:
        lines.append("## Languages & Frameworks\n")
        if languages:
            lang_bits = [f"{lang}: {count}" for lang, count in languages.items()]
            lines.append(f"Languages: {' · '.join(lang_bits)}")
        if frameworks:
            lines.append(f"Frameworks: {', '.join(frameworks)}")
        if frameworks_by_language:
            for lang, fws in frameworks_by_language.items():
                if fws:
                    lines.append(f"- **{lang}**: {', '.join(fws)}")
        if manifest_files:
            shown = ", ".join(f"`{m}`" for m in manifest_files[:8])
            extra = f" +{len(manifest_files) - 8} more" if len(manifest_files) > 8 else ""
            lines.append(f"Manifests: {shown}{extra}")
        lines.append("")

    # ── Dependencies Snapshot ──
    if dependencies_by_ecosystem:
        lines.append("## Dependency Snapshot\n")
        for eco, deps in dependencies_by_ecosystem.items():
            if not deps:
                continue
            shown = ", ".join(f"`{d}`" for d in deps[:12])
            extra = f" +{len(deps) - 12} more" if len(deps) > 12 else ""
            lines.append(f"- **{eco}**: {shown}{extra}")
        lines.append("")

    # ── Docs & Config Context ──
    if docs_summary:
        doc_count = docs_summary.get("documents", 0)
        sections = docs_summary.get("sections", [])
        cfg_keys = docs_summary.get("config_keys", [])
        lines.append("## Docs & Config Context\n")
        lines.append(f"Documents parsed: {doc_count}")
        if sections:
            shown = ", ".join(f"`{s}`" for s in sections[:12])
            extra = f" +{len(sections) - 12} more" if len(sections) > 12 else ""
            lines.append(f"Top sections: {shown}{extra}")
        if cfg_keys:
            shown = ", ".join(f"`{k}`" for k in cfg_keys[:15])
            extra = f" +{len(cfg_keys) - 15} more" if len(cfg_keys) > 15 else ""
            lines.append(f"Config keys: {shown}{extra}")
        lines.append("")

    # ── AI Context Pack ──
    lines.append("## AI Context Pack\n")
    lines.append("Use this compact context before opening full files:")
    if det_entries:
        lines.append(f"- Entrypoints: {', '.join(f'`{e}`' for e in det_entries[:6])}")
    if languages:
        lines.append(f"- Primary languages: {', '.join(list(languages.keys())[:5])}")
    if frameworks:
        lines.append(f"- Primary frameworks: {', '.join(frameworks[:8])}")
    lines.append(f"- Graph density: {G.number_of_nodes()} nodes / {G.number_of_edges()} edges")
    lines.append(f"- Modules: {len(communities)} (top cohesion: {max(cohesion.values() or [0]):.2f})")
    if complexity:
        top = complexity[0]
        lines.append(f"- Most complex file: `{top.get('label', '')}` ({top.get('complexity_score', 0):.1f})")
    lines.append("")

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

    # ── Deep File Details ──
    if largest_files or line_heavy_files:
        lines.append("## Deep File Details\n")
        if largest_files:
            lines.append("Largest Files (bytes):")
            for item in largest_files[:8]:
                lines.append(f"- `{item.get('path', '')}` — {item.get('bytes', 0):,} bytes")
            lines.append("")
        if line_heavy_files:
            lines.append("Most Line-Heavy Files:")
            for item in line_heavy_files[:8]:
                lines.append(f"- `{item.get('path', '')}` — {item.get('lines', 0):,} lines")
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
    report += f"*Generated by codemap-zero v{__version__} · {total_files} files scanned · zero LLM tokens used*\n"

    return report
