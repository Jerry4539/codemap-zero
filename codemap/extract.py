"""Deterministic AST extraction via tree-sitter.

Extracts classes, functions, imports, call graphs, docstrings,
and rationale comments from source code. Zero LLM — pure static analysis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter

# ---------------------------------------------------------------------------
# Language configuration — data-driven extraction
# ---------------------------------------------------------------------------


@dataclass
class LanguageConfig:
    """Per-language tree-sitter query configuration."""
    ts_module: str
    class_types: list[str]
    function_types: list[str]
    import_types: list[str]
    call_types: list[str] = field(default_factory=lambda: ["call_expression"])
    name_field: str = "name"
    body_field: str = "body"
    string_types: list[str] = field(default_factory=lambda: ["string", "string_literal"])
    comment_types: list[str] = field(default_factory=lambda: ["comment"])
    decorator_types: list[str] = field(default_factory=list)
    import_source_field: str | None = None
    # For ts modules with multiple languages (e.g. tree_sitter_typescript)
    parser_func: str | None = None
    # For languages where classes/functions/imports are all 'call' nodes
    call_name_filters: dict[str, list[str]] | None = None


LANGUAGES: dict[str, LanguageConfig] = {
    ".py": LanguageConfig(
        ts_module="tree_sitter_python",
        class_types=["class_definition"],
        function_types=["function_definition"],
        import_types=["import_statement", "import_from_statement"],
        call_types=["call"],
        decorator_types=["decorator"],
        comment_types=["comment"],
        string_types=["string", "concatenated_string"],
    ),
    ".js": LanguageConfig(
        ts_module="tree_sitter_javascript",
        class_types=["class_declaration"],
        function_types=["function_declaration", "arrow_function", "method_definition"],
        import_types=["import_statement"],
        call_types=["call_expression"],
        comment_types=["comment"],
    ),
    ".jsx": LanguageConfig(
        ts_module="tree_sitter_javascript",
        class_types=["class_declaration"],
        function_types=["function_declaration", "arrow_function", "method_definition"],
        import_types=["import_statement"],
        call_types=["call_expression"],
        comment_types=["comment"],
    ),
    ".mjs": LanguageConfig(
        ts_module="tree_sitter_javascript",
        class_types=["class_declaration"],
        function_types=["function_declaration", "arrow_function", "method_definition"],
        import_types=["import_statement"],
        call_types=["call_expression"],
        comment_types=["comment"],
    ),
    ".ts": LanguageConfig(
        ts_module="tree_sitter_typescript",
        class_types=["class_declaration"],
        function_types=["function_declaration", "arrow_function", "method_definition"],
        import_types=["import_statement"],
        call_types=["call_expression"],
        comment_types=["comment"],
        parser_func="language_typescript",
    ),
    ".tsx": LanguageConfig(
        ts_module="tree_sitter_typescript",
        class_types=["class_declaration"],
        function_types=["function_declaration", "arrow_function", "method_definition"],
        import_types=["import_statement"],
        call_types=["call_expression"],
        comment_types=["comment"],
        parser_func="language_tsx",
    ),
    ".go": LanguageConfig(
        ts_module="tree_sitter_go",
        class_types=["type_declaration"],
        function_types=["function_declaration", "method_declaration"],
        import_types=["import_declaration"],
        call_types=["call_expression"],
        comment_types=["comment"],
    ),
    ".rs": LanguageConfig(
        ts_module="tree_sitter_rust",
        class_types=["struct_item", "enum_item", "trait_item", "impl_item"],
        function_types=["function_item"],
        import_types=["use_declaration"],
        call_types=["call_expression"],
        comment_types=["line_comment", "block_comment"],
    ),
    ".java": LanguageConfig(
        ts_module="tree_sitter_java",
        class_types=["class_declaration", "interface_declaration", "enum_declaration"],
        function_types=["method_declaration", "constructor_declaration"],
        import_types=["import_declaration"],
        call_types=["method_invocation"],
        comment_types=["line_comment", "block_comment"],
        decorator_types=["marker_annotation", "annotation"],
    ),
    ".c": LanguageConfig(
        ts_module="tree_sitter_c",
        class_types=["struct_specifier", "enum_specifier", "union_specifier"],
        function_types=["function_definition"],
        import_types=["preproc_include"],
        call_types=["call_expression"],
        comment_types=["comment"],
    ),
    ".h": LanguageConfig(
        ts_module="tree_sitter_c",
        class_types=["struct_specifier", "enum_specifier", "union_specifier"],
        function_types=["function_definition", "declaration"],
        import_types=["preproc_include"],
        call_types=["call_expression"],
        comment_types=["comment"],
    ),
    ".cpp": LanguageConfig(
        ts_module="tree_sitter_cpp",
        class_types=["class_specifier", "struct_specifier"],
        function_types=["function_definition"],
        import_types=["preproc_include"],
        call_types=["call_expression"],
        comment_types=["comment"],
    ),
    ".cc": LanguageConfig(
        ts_module="tree_sitter_cpp",
        class_types=["class_specifier", "struct_specifier"],
        function_types=["function_definition"],
        import_types=["preproc_include"],
        call_types=["call_expression"],
        comment_types=["comment"],
    ),
    ".hpp": LanguageConfig(
        ts_module="tree_sitter_cpp",
        class_types=["class_specifier", "struct_specifier"],
        function_types=["function_definition", "declaration"],
        import_types=["preproc_include"],
        call_types=["call_expression"],
        comment_types=["comment"],
    ),
    ".rb": LanguageConfig(
        ts_module="tree_sitter_ruby",
        class_types=["class", "module"],
        function_types=["method", "singleton_method"],
        import_types=[],
        call_types=["call", "command_call"],
        comment_types=["comment"],
        call_name_filters={
            "import": ["require", "require_relative", "load", "autoload"],
        },
    ),
    ".cs": LanguageConfig(
        ts_module="tree_sitter_c_sharp",
        class_types=["class_declaration", "interface_declaration", "struct_declaration"],
        function_types=["method_declaration", "constructor_declaration"],
        import_types=["using_directive"],
        call_types=["invocation_expression"],
        comment_types=["comment"],
        decorator_types=["attribute_list"],
    ),
    ".kt": LanguageConfig(
        ts_module="tree_sitter_kotlin",
        class_types=["class_declaration", "object_declaration"],
        function_types=["function_declaration"],
        import_types=["import_header"],
        call_types=["call_expression"],
        comment_types=["line_comment", "multiline_comment"],
    ),
    ".scala": LanguageConfig(
        ts_module="tree_sitter_scala",
        class_types=["class_definition", "object_definition", "trait_definition"],
        function_types=["function_definition"],
        import_types=["import_declaration"],
        call_types=["call_expression"],
        comment_types=["comment"],
    ),
    ".php": LanguageConfig(
        ts_module="tree_sitter_php",
        class_types=["class_declaration", "interface_declaration", "trait_declaration"],
        function_types=["function_definition", "method_declaration"],
        import_types=["namespace_use_declaration"],
        call_types=["function_call_expression", "method_call_expression"],
        comment_types=["comment"],
    ),
    ".swift": LanguageConfig(
        ts_module="tree_sitter_swift",
        class_types=["class_declaration", "struct_declaration", "protocol_declaration"],
        function_types=["function_declaration"],
        import_types=["import_declaration"],
        call_types=["call_expression"],
        comment_types=["comment", "multiline_comment"],
    ),
    ".lua": LanguageConfig(
        ts_module="tree_sitter_lua",
        class_types=[],
        function_types=["function_declaration", "function_definition"],
        import_types=[],
        call_types=["function_call"],
        comment_types=["comment"],
    ),
    ".zig": LanguageConfig(
        ts_module="tree_sitter_zig",
        class_types=["container_declaration"],
        function_types=["fn_proto"],
        import_types=[],
        call_types=["call_expr"],
        comment_types=["line_comment"],
    ),
    ".ps1": LanguageConfig(
        ts_module="tree_sitter_powershell",
        class_types=["class_statement"],
        function_types=["function_statement"],
        import_types=[],
        call_types=["command_expression"],
        comment_types=["comment"],
    ),
    ".ex": LanguageConfig(
        ts_module="tree_sitter_elixir",
        class_types=[],
        function_types=[],
        import_types=[],
        call_types=["call"],
        comment_types=["comment"],
        call_name_filters={
            "class": ["defmodule"],
            "function": ["def", "defp", "defmacro", "defmacrop", "defguard"],
            "import": ["import", "use", "alias", "require"],
        },
    ),
    ".exs": LanguageConfig(
        ts_module="tree_sitter_elixir",
        class_types=[],
        function_types=[],
        import_types=[],
        call_types=["call"],
        comment_types=["comment"],
        call_name_filters={
            "class": ["defmodule"],
            "function": ["def", "defp", "defmacro", "defmacrop", "defguard"],
            "import": ["import", "use", "alias", "require"],
        },
    ),
    ".jl": LanguageConfig(
        ts_module="tree_sitter_julia",
        class_types=["struct_definition", "abstract_definition"],
        function_types=["function_definition", "short_function_definition"],
        import_types=["import_statement", "using_statement"],
        call_types=["call_expression"],
        comment_types=["line_comment", "block_comment"],
    ),
    ".dart": LanguageConfig(
        ts_module="tree_sitter_dart",
        class_types=["class_definition", "mixin_declaration", "extension_declaration"],
        function_types=["function_signature", "method_signature", "function_body"],
        import_types=["import_or_export"],
        call_types=["selector_expression", "function_expression_invocation"],
        comment_types=["comment", "documentation_comment"],
        parser_func="language",
    ),
}

# Aliases
LANGUAGES[".cxx"] = LANGUAGES[".cpp"]
LANGUAGES[".kts"] = LANGUAGES[".kt"]

_RATIONALE_PATTERNS = re.compile(
    r"#\s*(NOTE|HACK|TODO|FIXME|WHY|IMPORTANT|WARN|XXX|BUG)\s*[:\-]?\s*(.+)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# tree-sitter parser cache
# ---------------------------------------------------------------------------

_parser_cache: dict[str, tree_sitter.Parser] = {}


def _get_parser(config: LanguageConfig) -> tree_sitter.Parser | None:
    """Get or create a tree-sitter parser for the given language config."""
    cache_key = f"{config.ts_module}:{config.parser_func or 'language'}"
    if cache_key in _parser_cache:
        return _parser_cache[cache_key]

    try:
        mod = __import__(config.ts_module)
        func_name = config.parser_func or "language"
        lang_func = getattr(mod, func_name, None) or getattr(mod, "language", None)
        if lang_func is None:
            return None
        lang = tree_sitter.Language(lang_func())
        parser = tree_sitter.Parser(lang)
        _parser_cache[cache_key] = parser
        return parser
    except (ImportError, AttributeError, Exception):
        return None


# ---------------------------------------------------------------------------
# Node extraction helpers
# ---------------------------------------------------------------------------


def _node_text(node: tree_sitter.Node) -> str:
    return node.text.decode("utf-8", errors="replace") if node.text else ""


def _find_name(node: tree_sitter.Node, field_name: str = "name") -> str:
    child = node.child_by_field_name(field_name)
    if child:
        return _node_text(child)
    for c in node.children:
        if c.type in ("identifier", "type_identifier", "property_identifier"):
            return _node_text(c)
    return ""


def _find_params(node: tree_sitter.Node) -> list[str]:
    params: list[str] = []
    param_node = node.child_by_field_name("parameters") or node.child_by_field_name("params")
    if not param_node:
        return params
    for child in param_node.children:
        if child.type in ("identifier", "typed_parameter", "typed_default_parameter",
                          "parameter", "simple_parameter", "formal_parameter"):
            name = _find_name(child)
            if name and name not in ("self", "cls"):
                params.append(name)
    return params


def _find_return_type(node: tree_sitter.Node) -> str:
    ret = node.child_by_field_name("return_type")
    if ret:
        text = _node_text(ret).strip()
        if text.startswith("->"):
            text = text[2:].strip()
        return text[:80]
    return ""


def _find_docstring(node: tree_sitter.Node, config: LanguageConfig) -> str:
    body = node.child_by_field_name(config.body_field)
    target = body if body else node
    for child in target.children:
        if child.type == "expression_statement":
            for sc in child.children:
                if sc.type in config.string_types:
                    text = _node_text(sc).strip("\"'").strip()
                    if text:
                        return text[:200] + ("..." if len(text) > 200 else "")
        if child.type in config.comment_types:
            text = _node_text(child).lstrip("/#* ").strip()
            if text:
                return text[:200] + ("..." if len(text) > 200 else "")
        if child.type not in config.comment_types and child.type != "expression_statement":
            break
    return ""


def _extract_imports(node: tree_sitter.Node, config: LanguageConfig) -> list[dict[str, str]]:
    imports: list[dict[str, str]] = []
    text = _node_text(node)
    if not text:
        return imports

    if config.ts_module == "tree_sitter_python":
        if node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            if module_node:
                imports.append({"module": _node_text(module_node), "text": text.strip()})
            else:
                match = re.match(r"from\s+([\w.]+)", text)
                if match:
                    imports.append({"module": match.group(1), "text": text.strip()})
        elif node.type == "import_statement":
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    mod_name = _find_name(child) or _node_text(child).split()[0]
                    imports.append({"module": mod_name, "text": text.strip()})
    elif config.ts_module in ("tree_sitter_javascript", "tree_sitter_typescript"):
        source = node.child_by_field_name("source")
        if source:
            mod = _node_text(source).strip("\"'")
            imports.append({"module": mod, "text": text.strip()})
        else:
            match = re.search(r"""(?:from|require\()\s*['"]([^'"]+)['"]""", text)
            if match:
                imports.append({"module": match.group(1), "text": text.strip()})
    elif config.ts_module == "tree_sitter_go":
        for child in node.children:
            if child.type == "import_spec":
                path_node = child.child_by_field_name("path")
                if path_node:
                    mod = _node_text(path_node).strip('"')
                    imports.append({"module": mod, "text": mod})
            elif child.type == "import_spec_list":
                for spec in child.children:
                    if spec.type == "import_spec":
                        path_node = spec.child_by_field_name("path")
                        if path_node:
                            mod = _node_text(path_node).strip('"')
                            imports.append({"module": mod, "text": mod})
        if not imports:
            imports.append({"module": text.strip(), "text": text.strip()})
    elif config.ts_module == "tree_sitter_rust":
        match = re.search(r"use\s+([\w:]+)", text)
        if match:
            imports.append({"module": match.group(1), "text": text.strip()})
    elif config.ts_module == "tree_sitter_dart":
        # Dart: import 'package:flutter/material.dart'; or import 'src/foo.dart';
        match = re.search(r"""import\s+['"]([^'"]+)['"]""", text)
        if match:
            mod = match.group(1)
            # Normalize: 'package:foo/bar.dart' -> 'foo/bar', 'src/foo.dart' -> 'src/foo'
            if mod.startswith("dart:"):
                pass  # stdlib — skip
            else:
                if mod.startswith("package:"):
                    mod = mod[len("package:"):]
                mod = mod.rstrip("/").removesuffix(".dart")
                imports.append({"module": mod, "text": text.strip()})
    else:
        imports.append({"module": text.strip(), "text": text.strip()})

    return imports


def _extract_calls(node: tree_sitter.Node) -> list[str]:
    calls: list[str] = []

    def _walk(n: tree_sitter.Node) -> None:
        if n.type in ("call", "call_expression", "method_invocation",
                       "function_call_expression", "method_call_expression",
                       "invocation_expression", "command_call", "function_call",
                       "call_expr", "command_expression"):
            func = n.child_by_field_name("function") or n.child_by_field_name("name")
            if func:
                calls.append(_node_text(func))
            elif n.children:
                calls.append(_node_text(n.children[0]))
        for child in n.children:
            _walk(child)

    _walk(node)
    return calls


def _extract_rationale_comments(source: str) -> list[dict[str, Any]]:
    rationale: list[dict[str, Any]] = []
    for i, line in enumerate(source.splitlines(), 1):
        match = _RATIONALE_PATTERNS.search(line)
        if match:
            rationale.append({
                "type": match.group(1).upper(),
                "text": match.group(2).strip(),
                "line": i,
            })
    return rationale


def _extract_decorators(node: tree_sitter.Node, config: LanguageConfig) -> list[str]:
    decorators: list[str] = []
    if not config.decorator_types:
        return decorators
    for child in node.children:
        if child.type in config.decorator_types:
            decorators.append(_node_text(child).strip())
    if node.parent:
        for sibling in node.parent.children:
            if sibling.type in config.decorator_types and sibling.end_point[0] <= node.start_point[0]:
                decorators.append(_node_text(sibling).strip())
    return decorators[:5]


def _get_call_func_name(node: tree_sitter.Node) -> str:
    func = node.child_by_field_name("function") or node.child_by_field_name("name")
    if func:
        return _node_text(func).strip()
    if node.children and node.children[0].type == "identifier":
        return _node_text(node.children[0]).strip()
    return ""


# ---------------------------------------------------------------------------
# Per-file extraction
# ---------------------------------------------------------------------------


@dataclass
class ExtractionResult:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


def _make_node_id(rel_path: str, name: str) -> str:
    """Create a stable node ID using the full relative path to prevent collisions."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", f"{rel_path}_{name}")
    return clean.lower()


def _make_file_node_id(rel_path: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", rel_path.replace("/", "_").replace("\\", "_"))
    return f"file_{clean}".lower()


def _build_signature(name: str, params: list[str], return_type: str) -> str:
    sig = f"{name}({', '.join(params)})"
    if return_type:
        sig += f" -> {return_type}"
    return sig


def extract_file(file_path: Path, root: Path) -> ExtractionResult:
    """Extract structural information from a single code file."""
    result = ExtractionResult()
    rel_path = str(file_path.relative_to(root)).replace("\\", "/")
    ext = file_path.suffix.lower()

    config = LANGUAGES.get(ext)
    if not config:
        return result

    try:
        source = file_path.read_bytes()
        source_text = source.decode("utf-8", errors="replace")
    except OSError:
        return result

    parser = _get_parser(config)
    if not parser:
        return result

    tree = parser.parse(source)
    root_node = tree.root_node

    # File-level node with module docstring
    file_node_id = _make_file_node_id(rel_path)
    module_docstring = ""
    if root_node.children:
        first = root_node.children[0]
        if first.type == "expression_statement":
            for sc in first.children:
                if sc.type in config.string_types:
                    module_docstring = _node_text(sc).strip("\"'").strip()[:200]

    result.nodes.append({
        "id": file_node_id,
        "label": rel_path,
        "type": "file",
        "file_type": "code",
        "source_file": rel_path,
        "source_location": None,
        "lines": source_text.count("\n") + 1,
        "docstring": module_docstring or None,
    })

    symbol_map: dict[str, str] = {}  # name -> node_id
    all_calls: dict[str, list[str]] = {}  # node_id -> [called_func_names]

    def _process_class(node: tree_sitter.Node) -> None:
        name = _find_name(node, config.name_field)
        if not name:
            return
        node_id = _make_node_id(rel_path, name)
        docstring = _find_docstring(node, config)
        decorators = _extract_decorators(node, config)

        result.nodes.append({
            "id": node_id,
            "label": name,
            "type": "class",
            "file_type": "code",
            "source_file": rel_path,
            "source_location": f"L{node.start_point[0] + 1}",
            "docstring": docstring or None,
            "decorators": decorators or None,
        })
        result.edges.append({"source": file_node_id, "target": node_id, "relation": "contains"})
        symbol_map[name] = node_id

        body = node.child_by_field_name(config.body_field)
        target = body if body else node
        for member in target.children:
            if member.type in config.function_types:
                mname = _find_name(member, config.name_field)
                if not mname:
                    continue
                method_id = _make_node_id(rel_path, f"{name}_{mname}")
                params = _find_params(member)
                ret_type = _find_return_type(member)
                mdocstring = _find_docstring(member, config)

                result.nodes.append({
                    "id": method_id,
                    "label": f"{name}.{mname}",
                    "type": "method",
                    "file_type": "code",
                    "source_file": rel_path,
                    "source_location": f"L{member.start_point[0] + 1}",
                    "params": params or None,
                    "signature": _build_signature(f"{name}.{mname}", params, ret_type),
                    "docstring": mdocstring or None,
                })
                result.edges.append({"source": node_id, "target": method_id, "relation": "method"})
                symbol_map[f"{name}.{mname}"] = method_id
                method_calls = _extract_calls(member)
                if method_calls:
                    all_calls[method_id] = method_calls

    def _process_function(node: tree_sitter.Node) -> None:
        name = _find_name(node, config.name_field)
        if not name:
            return
        node_id = _make_node_id(rel_path, name)
        params = _find_params(node)
        ret_type = _find_return_type(node)
        docstring = _find_docstring(node, config)
        decorators = _extract_decorators(node, config)

        result.nodes.append({
            "id": node_id,
            "label": name,
            "type": "function",
            "file_type": "code",
            "source_file": rel_path,
            "source_location": f"L{node.start_point[0] + 1}",
            "params": params or None,
            "signature": _build_signature(name, params, ret_type),
            "docstring": docstring or None,
            "decorators": decorators or None,
        })
        result.edges.append({"source": file_node_id, "target": node_id, "relation": "contains"})
        symbol_map[name] = node_id
        func_calls = _extract_calls(node)
        if func_calls:
            all_calls[node_id] = func_calls

    def _process_import(node: tree_sitter.Node) -> None:
        imported = _extract_imports(node, config)
        for imp in imported:
            mod_parts = imp["module"].split(".")
            imp_id = _make_node_id("import", mod_parts[-1] if mod_parts else imp["module"])
            result.edges.append({
                "source": file_node_id,
                "target": imp_id,
                "relation": "imports",
                "source_file": rel_path,
                "source_location": f"L{node.start_point[0] + 1}",
                "import_text": imp["text"][:100],
                "import_module": imp["module"],
                "confidence": "HIGH",
                "provenance": "EXTRACTED",
            })

    def _process_call_filtered(node: tree_sitter.Node) -> None:
        """Handle Elixir/Ruby where classes/functions/imports are all 'call' nodes."""
        if not config.call_name_filters:
            return
        func_name = _get_call_func_name(node)
        if not func_name:
            return
        for category, names in config.call_name_filters.items():
            if func_name not in names:
                continue
            text = _node_text(node)
            args = node.child_by_field_name("arguments")

            if category == "class":
                cname = ""
                if args:
                    for c in args.children:
                        if c.type in ("identifier", "alias"):
                            cname = _node_text(c)
                            break
                cname = cname or func_name
                nid = _make_node_id(rel_path, cname)
                result.nodes.append({"id": nid, "label": cname, "type": "class",
                                     "file_type": "code", "source_file": rel_path,
                                     "source_location": f"L{node.start_point[0] + 1}"})
                result.edges.append({"source": file_node_id, "target": nid, "relation": "contains"})
                symbol_map[cname] = nid

            elif category == "function":
                fname = ""
                if args:
                    for c in args.children:
                        if c.type in ("identifier", "call"):
                            fname = _find_name(c) or _node_text(c).split("(")[0]
                            break
                fname = fname or func_name
                nid = _make_node_id(rel_path, fname)
                result.nodes.append({"id": nid, "label": fname, "type": "function",
                                     "file_type": "code", "source_file": rel_path,
                                     "source_location": f"L{node.start_point[0] + 1}"})
                result.edges.append({"source": file_node_id, "target": nid, "relation": "contains"})
                symbol_map[fname] = nid

            elif category == "import":
                mod = text.strip()
                if args:
                    for c in args.children:
                        if c.type in ("identifier", "alias", "atom"):
                            mod = _node_text(c)
                            break
                imp_id = _make_node_id("import", mod)
                result.edges.append({
                    "source": file_node_id, "target": imp_id, "relation": "imports",
                    "source_file": rel_path, "import_text": text[:100], "import_module": mod,
                    "confidence": "HIGH", "provenance": "EXTRACTED",
                })
            return

    # Walk top-level nodes
    for node in root_node.children:
        if config.call_name_filters and node.type in config.call_types:
            _process_call_filtered(node)
            continue
        if node.type in config.class_types:
            _process_class(node)
        elif node.type in config.function_types:
            _process_function(node)
        elif node.type in config.import_types:
            _process_import(node)

    # Wire intra-file call graph edges
    for caller_id, called_names in all_calls.items():
        seen_targets: set[str] = set()
        for call_name in called_names:
            target_id = symbol_map.get(call_name)
            confidence = "HIGH"
            provenance = "INFERRED"
            if not target_id:
                for sym_name, sym_id in symbol_map.items():
                    if sym_name.endswith(f".{call_name}"):
                        target_id = sym_id
                        confidence = "MEDIUM"
                        break
            if not target_id:
                # Could not resolve — record as ambiguous import-like node
                target_id = _make_node_id("unresolved", call_name)
                confidence = "LOW"
                provenance = "AMBIGUOUS"
            if target_id and target_id != caller_id and target_id not in seen_targets:
                seen_targets.add(target_id)
                result.edges.append({
                    "source": caller_id, "target": target_id,
                    "relation": "calls", "source_file": rel_path,
                    "confidence": confidence, "provenance": provenance,
                })

    # Rationale comments
    rationale = _extract_rationale_comments(source_text)
    for r in rationale:
        rat_id = _make_node_id(rel_path, f"rationale_{r['line']}")
        result.nodes.append({
            "id": rat_id,
            "label": f"{r['type']}: {r['text'][:80]}",
            "type": "rationale",
            "file_type": "code",
            "source_file": rel_path,
            "source_location": f"L{r['line']}",
            "rationale_type": r["type"],
        })
        result.edges.append({"source": rat_id, "target": file_node_id, "relation": "rationale_for"})

    return result


# ---------------------------------------------------------------------------
# Cross-file import resolution
# ---------------------------------------------------------------------------


def _resolve_imports(
    all_results: dict[str, ExtractionResult],
    root: Path,
) -> list[dict[str, Any]]:
    """Resolve import edges to actual file nodes in the graph."""
    file_map: dict[str, str] = {}
    stem_map: dict[str, str] = {}
    rel_path_map: dict[str, str] = {}

    for rel_path in all_results:
        fid = _make_file_node_id(rel_path)
        stem = Path(rel_path).stem
        stem_map[stem] = fid
        rel_path_map[rel_path] = fid

        module_path = rel_path.replace("/", ".").replace("\\", ".")
        if module_path.endswith(".py"):
            module_path = module_path[:-3]
        file_map[module_path] = fid
        parts = module_path.split(".")
        if parts:
            file_map[parts[-1]] = fid

    resolved_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()

    for rel_path, res in all_results.items():
        file_id = _make_file_node_id(rel_path)
        for edge in res.edges:
            if edge["relation"] != "imports":
                continue
            import_module = edge.get("import_module", "")
            if not import_module:
                continue

            target_fid: str | None = None

            # 1. Exact module path match
            if import_module in file_map:
                target_fid = file_map[import_module]
            else:
                # 2. Last component match
                last = import_module.rsplit(".", 1)[-1]
                if last in stem_map:
                    target_fid = stem_map[last]
                else:
                    # 3. JS/TS relative imports
                    if import_module.startswith("."):
                        importer_dir = str(Path(rel_path).parent).replace("\\", "/")
                        resolved = str(Path(importer_dir) / import_module).replace("\\", "/")
                        resolved = str(Path(resolved)).replace("\\", "/")
                        for try_ext in ("", ".js", ".ts", ".jsx", ".tsx", "/index.js", "/index.ts"):
                            candidate = resolved + try_ext
                            if candidate in rel_path_map:
                                target_fid = rel_path_map[candidate]
                                break

            if target_fid and target_fid != file_id:
                edge_key = (file_id, target_fid)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    resolved_edges.append({
                        "source": file_id,
                        "target": target_fid,
                        "relation": "imports",
                        "source_file": rel_path,
                    })

    return resolved_edges


# ---------------------------------------------------------------------------
# Main extraction entry point
# ---------------------------------------------------------------------------


def extract(code_files: list[str], root: Path) -> dict[str, Any]:
    """Extract AST information from all code files."""
    all_results: dict[str, ExtractionResult] = {}
    all_nodes: list[dict[str, Any]] = []
    all_edges: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for rel_path in code_files:
        file_path = root / rel_path
        if not file_path.is_file():
            continue

        res = extract_file(file_path, root)
        all_results[rel_path] = res

        for node in res.nodes:
            if node["id"] not in seen_ids:
                all_nodes.append(node)
                seen_ids.add(node["id"])
        all_edges.extend(res.edges)

    resolved = _resolve_imports(all_results, root)
    all_edges.extend(resolved)

    return {"nodes": all_nodes, "edges": all_edges}
