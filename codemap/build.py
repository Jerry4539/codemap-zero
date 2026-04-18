"""Build a directed NetworkX graph from extraction results."""

from __future__ import annotations

from typing import Any

import networkx as nx

# Standard library modules to filter out of the graph
_STDLIB_MODULES: set[str] = {
    "os", "sys", "re", "json", "math", "time", "datetime", "pathlib",
    "typing", "collections", "functools", "itertools", "hashlib", "io",
    "copy", "abc", "enum", "dataclasses", "contextlib", "logging",
    "argparse", "subprocess", "shutil", "tempfile", "textwrap",
    "importlib", "inspect", "ast", "dis", "traceback", "warnings",
    "unittest", "http", "urllib", "socket", "threading", "multiprocessing",
    "pickle", "struct", "csv", "xml", "html", "string", "pprint",
    "statistics", "random", "secrets", "uuid", "platform", "signal",
    "fnmatch", "glob", "os.path",
}

# Common third-party libs to also filter
_THIRDPARTY_MODULES: set[str] = {
    "networkx", "click", "flask", "django", "fastapi", "numpy", "pandas",
    "requests", "pytest", "setuptools", "wheel", "pip", "tree_sitter",
    "graspologic", "matplotlib", "scipy", "sklearn", "torch", "tensorflow",
}


def _is_stdlib_or_thirdparty(node_id: str) -> bool:
    """Check if a node ID corresponds to a stdlib/third-party import."""
    if not node_id.startswith("import_"):
        return False
    mod_name = node_id[len("import_"):]
    return mod_name in _STDLIB_MODULES or mod_name in _THIRDPARTY_MODULES


def build_graph(extraction: dict[str, Any]) -> nx.DiGraph:
    """Build a directed NetworkX graph from the merged extraction dict.

    Uses DiGraph so import direction, call direction, and containment
    are preserved for accurate analysis.
    """
    G = nx.DiGraph()

    for node in extraction.get("nodes", []):
        node_id = node["id"]
        if _is_stdlib_or_thirdparty(node_id):
            continue
        G.add_node(node_id, **node)

    for edge in extraction.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        # Skip edges pointing to stdlib/third-party
        if _is_stdlib_or_thirdparty(target) or _is_stdlib_or_thirdparty(source):
            continue
        # Add target node if it doesn't exist (unresolved project imports)
        if target not in G:
            G.add_node(target, id=target, label=target, type="external")
        if source not in G:
            G.add_node(source, id=source, label=source, type="external")
        G.add_edge(source, target, **edge)

    return G
