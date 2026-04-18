"""Graph analysis — god nodes, entry points, complexity, patterns, dead code.

All analysis is deterministic — zero LLM calls. Uses directed graph
topology, degree centrality, and heuristic pattern matching.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import networkx as nx


# ---------------------------------------------------------------------------
# God nodes — highest-degree concepts
# ---------------------------------------------------------------------------


def god_nodes(G: nx.DiGraph, top_n: int = 10) -> list[dict[str, Any]]:
    """Find the most-connected nodes (by total degree)."""
    if G.number_of_nodes() == 0:
        return []

    gods: list[dict[str, Any]] = []
    for node_id, data in G.nodes(data=True):
        in_d = G.in_degree(node_id)
        out_d = G.out_degree(node_id)
        total = in_d + out_d
        if total > 0:
            gods.append({
                "id": node_id,
                "label": data.get("label", node_id),
                "type": data.get("type", "unknown"),
                "degree": total,
                "in_degree": in_d,
                "out_degree": out_d,
                "source_file": data.get("source_file", ""),
            })

    gods.sort(key=lambda x: x["degree"], reverse=True)
    return gods[:top_n]


# ---------------------------------------------------------------------------
# Entry points — files that import many but are imported by few
# ---------------------------------------------------------------------------


def find_entry_points(G: nx.DiGraph) -> list[dict[str, Any]]:
    """Find entry point files (high import out-degree, low import in-degree)."""
    # Pre-build in-degree index for import edges
    import_in: Counter[str] = Counter()
    import_out: Counter[str] = Counter()

    for u, v, data in G.edges(data=True):
        if data.get("relation") == "imports":
            import_out[u] += 1
            import_in[v] += 1

    entries: list[dict[str, Any]] = []
    for node_id, data in G.nodes(data=True):
        if data.get("type") != "file":
            continue
        out_deg = import_out.get(node_id, 0)
        in_deg = import_in.get(node_id, 0)

        if out_deg > 0 and in_deg <= 1:
            entries.append({
                "id": node_id,
                "label": data.get("label", node_id),
                "imports": out_deg,
                "imported_by": in_deg,
            })

    entries.sort(key=lambda x: x["imports"], reverse=True)
    return entries[:5]


# ---------------------------------------------------------------------------
# Architecture pattern detection
# ---------------------------------------------------------------------------

_PATTERN_INDICATORS: dict[str, list[str]] = {
    "mvc": ["controller", "model", "view", "template"],
    "api_rest": ["route", "endpoint", "handler", "middleware", "api"],
    "microservices": ["service", "gateway", "broker", "consumer", "producer"],
    "cli": ["command", "cli", "arg", "parser"],
    "event_driven": ["event", "listener", "handler", "subscriber", "publisher"],
    "layered": ["repository", "service", "controller", "domain", "entity"],
    "plugin": ["plugin", "extension", "addon", "hook"],
}


def detect_architecture(G: nx.DiGraph) -> list[str]:
    """Detect architectural patterns from file/directory names."""
    labels = [data.get("label", "").lower() for _, data in G.nodes(data=True)]
    all_text = " ".join(labels)

    patterns_found: list[str] = []
    for pattern, indicators in _PATTERN_INDICATORS.items():
        matches = sum(1 for ind in indicators if ind in all_text)
        if matches >= 2:
            patterns_found.append(pattern)

    return patterns_found


# ---------------------------------------------------------------------------
# Circular dependency detection
# ---------------------------------------------------------------------------


def find_circular_deps(G: nx.DiGraph) -> list[list[str]]:
    """Find circular dependencies in the import graph."""
    # Build import-only subgraph (already directed)
    import_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("relation") == "imports"]
    DG = nx.DiGraph(import_edges)

    cycles: list[list[str]] = []
    try:
        for cycle in nx.simple_cycles(DG):
            if len(cycle) <= 5:
                labels = [G.nodes.get(n, {}).get("label", n) for n in cycle]
                cycles.append(labels)
    except nx.NetworkXError:
        pass

    return cycles[:10]


# ---------------------------------------------------------------------------
# Dead code detection
# ---------------------------------------------------------------------------


def find_dead_exports(G: nx.DiGraph) -> list[dict[str, Any]]:
    """Find symbols defined but never referenced by another file."""
    dead: list[dict[str, Any]] = []

    for node_id, data in G.nodes(data=True):
        if data.get("type") not in ("function", "class"):
            continue
        label = data.get("label", "")
        if label.startswith("_"):
            continue

        # Check if anything from a different file points to this node
        has_external_ref = False
        for pred in G.predecessors(node_id):
            pred_data = G.nodes.get(pred, {})
            pred_file = pred_data.get("source_file", "")
            if pred_file and pred_file != data.get("source_file", ""):
                has_external_ref = True
                break

        if not has_external_ref:
            # Also check successors for edges from other files
            for succ in G.successors(node_id):
                succ_data = G.nodes.get(succ, {})
                succ_file = succ_data.get("source_file", "")
                if succ_file and succ_file != data.get("source_file", ""):
                    has_external_ref = True
                    break

        if not has_external_ref:
            dead.append({
                "id": node_id,
                "label": label,
                "source_file": data.get("source_file", ""),
            })

    return dead[:20]


# ---------------------------------------------------------------------------
# Test coverage mapping
# ---------------------------------------------------------------------------


def test_coverage_map(
    code_files: list[str],
    test_files: list[str],
) -> dict[str, str | None]:
    """Map source files to their test files (heuristic name matching)."""
    coverage: dict[str, str | None] = {}
    test_lookup: dict[str, str] = {}

    for tf in test_files:
        stem = Path(tf).stem.lower()
        clean = stem.replace("test_", "").replace("_test", "").replace(".test", "").replace(".spec", "")
        test_lookup[clean] = tf

    for cf in code_files:
        stem = Path(cf).stem.lower()
        coverage[cf] = test_lookup.get(stem)

    return coverage


# ---------------------------------------------------------------------------
# Complexity metrics
# ---------------------------------------------------------------------------


def file_complexity(G: nx.DiGraph) -> list[dict[str, Any]]:
    """Rank files by complexity (symbols × connections)."""
    file_scores: list[dict[str, Any]] = []

    for node_id, data in G.nodes(data=True):
        if data.get("type") != "file":
            continue

        symbols = sum(
            1 for _, _, ed in G.out_edges(node_id, data=True)
            if ed.get("relation") == "contains"
        )
        connections = G.in_degree(node_id) + G.out_degree(node_id)
        score = symbols * max(connections, 1)

        file_scores.append({
            "id": node_id,
            "label": data.get("label", node_id),
            "symbols": symbols,
            "connections": connections,
            "complexity_score": score,
            "lines": data.get("lines", 0),
        })

    file_scores.sort(key=lambda x: x["complexity_score"], reverse=True)
    return file_scores


# ---------------------------------------------------------------------------
# Layer detection
# ---------------------------------------------------------------------------

_LAYER_KEYWORDS: dict[str, list[str]] = {
    "api": ["route", "endpoint", "handler", "controller", "api", "view", "resource"],
    "service": ["service", "usecase", "interactor", "business"],
    "data": ["model", "entity", "schema", "repository", "dao", "orm", "database", "db", "migration"],
    "infra": ["config", "setting", "middleware", "util", "helper", "common", "shared", "lib"],
    "test": ["test", "spec", "fixture", "mock", "conftest"],
    "ui": ["component", "page", "layout", "template", "widget", "screen"],
}


def detect_layers(G: nx.DiGraph) -> dict[str, list[str]]:
    """Group files into architectural layers."""
    layers: dict[str, list[str]] = {k: [] for k in _LAYER_KEYWORDS}

    for node_id, data in G.nodes(data=True):
        if data.get("type") != "file":
            continue
        source = data.get("source_file", "").lower()

        for layer, keywords in _LAYER_KEYWORDS.items():
            if any(kw in source for kw in keywords):
                layers[layer].append(data.get("label", node_id))
                break

    return {k: v for k, v in layers.items() if v}


# ---------------------------------------------------------------------------
# Surprising connections (cross-community edges)
# ---------------------------------------------------------------------------


def surprising_connections(
    G: nx.DiGraph,
    communities: dict[int, list[str]],
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Find edges that cross community boundaries."""
    node_to_community: dict[str, int] = {}
    for cid, members in communities.items():
        for m in members:
            node_to_community[m] = cid

    surprises: list[dict[str, Any]] = []
    for u, v, data in G.edges(data=True):
        cu = node_to_community.get(u)
        cv = node_to_community.get(v)
        if cu is not None and cv is not None and cu != cv:
            relation = data.get("relation", "")
            # Skip internal structural edges
            if relation in ("contains", "method", "rationale_for"):
                continue
            surprises.append({
                "source": G.nodes.get(u, {}).get("label", u),
                "target": G.nodes.get(v, {}).get("label", v),
                "relation": relation,
                "source_community": cu,
                "target_community": cv,
                "source_file": data.get("source_file", ""),
            })

    priority = {"imports": 3, "calls": 2}
    surprises.sort(key=lambda x: priority.get(x["relation"], 1), reverse=True)
    return surprises[:top_n]
