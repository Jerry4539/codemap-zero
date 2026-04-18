"""Deterministic document and config file extraction (no LLM).

Parses markdown headings, README descriptions, package.json / pyproject.toml
metadata, and config key names. Pure text parsing — no semantic understanding.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _extract_markdown(file_path: Path, rel_path: str) -> dict[str, Any]:
    """Extract structure from a Markdown file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"headings": [], "links": [], "description": ""}

    headings: list[dict[str, Any]] = []
    links: list[str] = []
    description = ""

    lines = text.splitlines()
    first_para: list[str] = []
    in_first_para = False

    for i, line in enumerate(lines):
        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            headings.append({"level": level, "title": title, "line": i + 1})
            if level == 1 and not description:
                in_first_para = True
            continue

        # First paragraph after first heading = description
        if in_first_para:
            stripped = line.strip()
            if stripped:
                first_para.append(stripped)
            elif first_para:
                in_first_para = False
                description = " ".join(first_para)[:300]

        # Links
        for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", line):
            links.append(match.group(2))

    if in_first_para and first_para:
        description = " ".join(first_para)[:300]

    return {
        "headings": headings,
        "links": links[:20],  # Cap
        "description": description,
    }


def _extract_rst(file_path: Path, rel_path: str) -> dict[str, Any]:
    """Extract structure from an RST file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"headings": [], "description": ""}

    headings: list[dict[str, Any]] = []
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line and all(c == next_line[0] for c in next_line) and next_line[0] in "=-~^\"":
                headings.append({"level": "=-~^\"".index(next_line[0]) + 1, "title": line.strip(), "line": i + 1})

    return {"headings": headings, "description": ""}


def _extract_config_keys(file_path: Path, rel_path: str) -> dict[str, Any]:
    """Extract key names from config files (no values — security)."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"keys": []}

    ext = file_path.suffix.lower()
    keys: list[str] = []

    if ext in (".json",):
        # JSON: extract top-level keys
        for match in re.finditer(r'"(\w[\w.-]*)"(?=\s*:)', text):
            key = match.group(1)
            if key not in keys:
                keys.append(key)
    elif ext in (".yaml", ".yml"):
        # YAML: extract top-level keys
        for line in text.splitlines():
            match = re.match(r"^(\w[\w.-]*):", line)
            if match:
                keys.append(match.group(1))
    elif ext in (".toml",):
        # TOML: section headers and keys
        for line in text.splitlines():
            section = re.match(r"^\[([^\]]+)\]", line)
            if section:
                keys.append(f"[{section.group(1)}]")
                continue
            kv = re.match(r"^(\w[\w.-]*)\s*=", line)
            if kv:
                keys.append(kv.group(1))
    elif ext in (".ini", ".cfg"):
        for line in text.splitlines():
            section = re.match(r"^\[([^\]]+)\]", line)
            if section:
                keys.append(f"[{section.group(1)}]")
                continue
            kv = re.match(r"^(\w[\w.-]*)\s*[=:]", line)
            if kv:
                keys.append(kv.group(1))
    elif ext == ".env":
        # .env: variable names only (never values)
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                kv = re.match(r"^(\w+)=", line)
                if kv:
                    keys.append(kv.group(1))
    elif ext in (".xml",):
        # XML: extract tag names
        for match in re.finditer(r"<(\w[\w.-]*)", text):
            tag = match.group(1)
            if tag not in keys and tag.lower() not in ("xml", "version"):
                keys.append(tag)

    return {"keys": keys[:50]}  # Cap at 50


def extract_docs(
    doc_files: list[str],
    config_files: list[str],
    root: Path,
) -> dict[str, Any]:
    """Extract structural information from docs and config files.

    Args:
        doc_files: Relative paths to doc files.
        config_files: Relative paths to config files.
        root: Project root.

    Returns:
        Dict with 'nodes' and 'edges'.
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for rel_path in doc_files:
        file_path = root / rel_path
        ext = file_path.suffix.lower()
        file_id = f"doc_{re.sub(r'[^a-zA-Z0-9_]', '_', rel_path)}".lower()

        if ext in (".md", ".mdx"):
            info = _extract_markdown(file_path, rel_path)
        elif ext in (".rst",):
            info = _extract_rst(file_path, rel_path)
        else:
            info = {"headings": [], "description": ""}

        nodes.append({
            "id": file_id,
            "label": rel_path,
            "type": "document",
            "file_type": "document",
            "source_file": rel_path,
            "description": info.get("description", ""),
            "headings": [h["title"] for h in info.get("headings", [])],
        })

        # Create heading nodes for important sections
        for h in info.get("headings", []):
            if h["level"] <= 2:  # Only H1/H2
                h_id = f"{file_id}_h{h['line']}"
                nodes.append({
                    "id": h_id,
                    "label": h["title"],
                    "type": "section",
                    "file_type": "document",
                    "source_file": rel_path,
                    "source_location": f"L{h['line']}",
                })
                edges.append({
                    "source": file_id,
                    "target": h_id,
                    "relation": "contains",
                    "confidence": "EXTRACTED",
                    "confidence_score": 1.0,
                    "source_file": rel_path,
                })

    for rel_path in config_files:
        file_path = root / rel_path
        file_id = f"config_{re.sub(r'[^a-zA-Z0-9_]', '_', rel_path)}".lower()
        info = _extract_config_keys(file_path, rel_path)

        nodes.append({
            "id": file_id,
            "label": rel_path,
            "type": "config",
            "file_type": "config",
            "source_file": rel_path,
            "keys": info.get("keys", []),
        })

    return {"nodes": nodes, "edges": edges}
