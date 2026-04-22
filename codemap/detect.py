"""File discovery, classification, and project-type detection.

Walks a directory tree respecting .gitignore and .codemapignore,
classifies files by type, detects the project framework, and
estimates token counts.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Extension maps
# ---------------------------------------------------------------------------

CODE_EXTENSIONS: set[str] = {
    ".py", ".pyi",
    ".js", ".jsx", ".mjs", ".cjs",
    ".ts", ".tsx",
    ".go",
    ".rs",
    ".java",
    ".c", ".h",
    ".cpp", ".cc", ".cxx", ".hpp",
    ".rb",
    ".cs",
    ".kt", ".kts",
    ".scala",
    ".php",
    ".swift",
    ".lua",
    ".zig",
    ".ps1",
    ".ex", ".exs",
    ".m", ".mm",          # Objective-C
    ".jl",                 # Julia
    ".vue", ".svelte",
    ".dart",
}

DOC_EXTENSIONS: set[str] = {".md", ".mdx", ".txt", ".rst", ".html", ".htm"}

CONFIG_EXTENSIONS: set[str] = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".xml", ".properties",
}

CONFIG_FILENAMES: set[str] = {
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "Makefile", "Rakefile", "Vagrantfile",
    ".gitignore", ".dockerignore", ".editorconfig",
    "Procfile", "Gemfile", "Pipfile",
}

IMAGE_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".c": "C", ".h": "C/C++", ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++",
    ".rb": "Ruby", ".cs": "C#", ".scala": "Scala", ".php": "PHP", ".swift": "Swift",
    ".lua": "Lua", ".zig": "Zig", ".ps1": "PowerShell", ".ex": "Elixir", ".exs": "Elixir",
    ".m": "Objective-C", ".mm": "Objective-C++", ".jl": "Julia", ".vue": "Vue", ".svelte": "Svelte",
    ".dart": "Dart",
}

FRAMEWORK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fastapi": ("Python",), "flask": ("Python",), "django": ("Python",), "pytest": ("Python",), "click": ("Python",),
    "react": ("JavaScript", "TypeScript"), "next": ("JavaScript", "TypeScript"), "vue": ("JavaScript", "TypeScript"),
    "angular": ("JavaScript", "TypeScript"), "svelte": ("JavaScript", "TypeScript"), "express": ("JavaScript", "TypeScript"),
    "nestjs": ("JavaScript", "TypeScript"), "vite": ("JavaScript", "TypeScript"),
    "spring": ("Java", "Kotlin"), "ktor": ("Kotlin",), "gin": ("Go",), "echo": ("Go",), "fiber": ("Go",),
    "axum": ("Rust",), "actix": ("Rust",), "rocket": ("Rust",), "tokio": ("Rust",),
    "rails": ("Ruby",), "sinatra": ("Ruby",), "laravel": ("PHP",), "symfony": ("PHP",),
    "vapor": ("Swift",), "phoenix": ("Elixir",), "aspnet": ("C#",),
}

MANIFEST_NAMES: set[str] = {
    "pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile",
    "package.json", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts",
    "composer.json", "Gemfile", "mix.exs", "Package.swift", "pnpm-lock.yaml", "yarn.lock",
}

TEST_MARKERS: set[str] = {"test_", "_test.", ".test.", ".spec.", "tests/", "__tests__/", "test/"}

# Directories to always skip
ALWAYS_SKIP: set[str] = {
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".tox", ".nox",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "venv", ".venv", "env", ".env",
    "dist", "build", "out", "target",
    ".next", ".nuxt", ".output",
    "vendor",
    "codemap-out",
    "codemap-zero",
    ".idea", ".vscode",
}

# Binary / generated files to always skip
BINARY_EXTENSIONS: set[str] = {
    ".pyc", ".pyo", ".class", ".o", ".obj", ".so", ".dll", ".dylib",
    ".exe", ".bin", ".wasm",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".mov", ".avi", ".mkv", ".wav",
    ".ico", ".icns",
    ".lock",
}

# ---------------------------------------------------------------------------
# Ignore-file parsing
# ---------------------------------------------------------------------------


def _parse_ignore_file(path: Path) -> list[str]:
    """Parse a .gitignore / .codemapignore file and return patterns."""
    if not path.is_file():
        return []
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _matches_any(rel_path: str, name: str, patterns: list[str]) -> bool:
    """Check if a relative path or name matches any ignore pattern."""
    rel_posix = rel_path.replace("\\", "/")
    for pat in patterns:
        pat_clean = pat.rstrip("/")
        # directory-only pattern (ends with /)
        if pat.endswith("/"):
            if fnmatch.fnmatch(name, pat_clean) or fnmatch.fnmatch(rel_posix + "/", pat):
                return True
            # also match if pattern appears as a directory component
            if f"/{pat_clean}/" in f"/{rel_posix}/":
                return True
            continue
        # pattern with slash → match against full relative path
        if "/" in pat_clean:
            if fnmatch.fnmatch(rel_posix, pat_clean):
                return True
        else:
            # bare name pattern → match against file/dir name
            if fnmatch.fnmatch(name, pat_clean):
                return True
    return False


# ---------------------------------------------------------------------------
# Detection result
# ---------------------------------------------------------------------------


@dataclass
class DetectionResult:
    """Result of scanning a directory tree."""

    root: str
    total_files: int = 0
    total_lines: int = 0
    total_words: int = 0
    estimated_tokens: int = 0
    total_dirs_scanned: int = 0
    total_files_seen: int = 0
    skipped_ignored: int = 0
    skipped_binary: int = 0
    extensionless_included: int = 0
    skipped_limit: int = 0
    files: dict[str, list[str]] = field(default_factory=lambda: {
        "code": [], "docs": [], "config": [], "tests": [], "images": [], "other": [],
    })
    project_type: str = "unknown"
    project_name: str = ""
    project_description: str = ""
    frameworks: list[str] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)
    frameworks_by_language: dict[str, list[str]] = field(default_factory=dict)
    dependencies_by_ecosystem: dict[str, list[str]] = field(default_factory=dict)
    manifest_files: list[str] = field(default_factory=list)
    skipped_dirs: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    largest_files: list[dict[str, Any]] = field(default_factory=list)
    line_heavy_files: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "total_words": self.total_words,
            "estimated_tokens": self.estimated_tokens,
            "total_dirs_scanned": self.total_dirs_scanned,
            "total_files_seen": self.total_files_seen,
            "skipped_ignored": self.skipped_ignored,
            "skipped_binary": self.skipped_binary,
            "extensionless_included": self.extensionless_included,
            "skipped_limit": self.skipped_limit,
            "files": self.files,
            "project_type": self.project_type,
            "project_name": self.project_name,
            "project_description": self.project_description,
            "frameworks": self.frameworks,
            "languages": self.languages,
            "frameworks_by_language": self.frameworks_by_language,
            "dependencies_by_ecosystem": self.dependencies_by_ecosystem,
            "manifest_files": self.manifest_files,
            "entry_points": self.entry_points,
            "largest_files": self.largest_files,
            "line_heavy_files": self.line_heavy_files,
        }


# ---------------------------------------------------------------------------
# File classification helpers
# ---------------------------------------------------------------------------


def _classify_file(rel_path: str, ext: str) -> str:
    """Return the category for a file: code, docs, config, tests, images, other."""
    rel_lower = rel_path.lower().replace("\\", "/")

    # Check test markers first (tests are still code, but we track them)
    if ext in CODE_EXTENSIONS:
        for marker in TEST_MARKERS:
            if marker in rel_lower:
                return "tests"
        return "code"

    if ext in DOC_EXTENSIONS:
        return "docs"
    if ext in CONFIG_EXTENSIONS:
        return "config"
    if ext in IMAGE_EXTENSIONS:
        return "images"
    return "other"


def _count_file(path: Path) -> tuple[int, int]:
    """Return (lines, words) for a text file. Returns (0,0) on error."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        words = len(text.split())
        return lines, words
    except (OSError, UnicodeDecodeError):
        return 0, 0


def _file_size(path: Path) -> int:
    """Return file size in bytes. Returns 0 on error."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _language_stats(code_files: list[str], test_files: list[str]) -> dict[str, int]:
    """Build language counts from code and test files by extension."""
    counts: dict[str, int] = {}
    for rel in code_files + test_files:
        ext = Path(rel).suffix.lower()
        language = LANGUAGE_BY_EXTENSION.get(ext)
        if not language:
            continue
        counts[language] = counts.get(language, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def _sanitize_dep_name(name: str) -> str:
    dep = name.strip().strip('"').strip("'").strip()
    dep = re.split(r"[<>=!~\[\]@ ;]", dep, maxsplit=1)[0].strip()
    dep = dep.rstrip(";,.")
    return dep


def _read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _find_manifest_files(root: Path) -> list[Path]:
    manifests: list[Path] = []
    for dirpath_str, dirnames, filenames in os.walk(root):
        dirpath = Path(dirpath_str)
        dirnames[:] = [d for d in dirnames if d not in ALWAYS_SKIP]
        for fname in filenames:
            if fname in MANIFEST_NAMES or fname.endswith(".csproj"):
                manifests.append(dirpath / fname)
    manifests.sort()
    return manifests


def _extract_dependencies_from_manifests(root: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Extract dependency names per ecosystem from common manifest files."""
    deps: dict[str, set[str]] = {}
    manifests = _find_manifest_files(root)

    def _add_many(ecosystem: str, values: list[str]) -> None:
        if ecosystem not in deps:
            deps[ecosystem] = set()
        for v in values:
            name = _sanitize_dep_name(v)
            if name:
                deps[ecosystem].add(name.lower())

    for path in manifests:
        name = path.name
        text = _read_text_safe(path)
        if not text:
            continue

        if name == "requirements.txt":
            lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
            _add_many("python", lines)
        elif name == "pyproject.toml":
            try:
                import tomllib
                data = tomllib.loads(text)
                proj = data.get("project", {})
                _add_many("python", list(proj.get("dependencies", []) or []))
                opt = proj.get("optional-dependencies", {}) or {}
                for items in opt.values():
                    _add_many("python", list(items or []))
                poetry = ((data.get("tool", {}) or {}).get("poetry", {}) or {}).get("dependencies", {}) or {}
                _add_many("python", list(poetry.keys()))
            except Exception:
                pass
        elif name == "package.json":
            try:
                pkg = json.loads(text)
                keys = []
                for sec in ("dependencies", "devDependencies", "peerDependencies"):
                    keys.extend(list((pkg.get(sec, {}) or {}).keys()))
                _add_many("node", keys)
            except json.JSONDecodeError:
                pass
        elif name == "go.mod":
            mods = re.findall(r"^\s*require\s+([^\s]+)", text, flags=re.MULTILINE)
            _add_many("go", mods)
        elif name == "Cargo.toml":
            try:
                import tomllib
                data = tomllib.loads(text)
                keys = list((data.get("dependencies", {}) or {}).keys())
                keys += list((data.get("dev-dependencies", {}) or {}).keys())
                _add_many("rust", keys)
            except Exception:
                pass
        elif name == "composer.json":
            try:
                pkg = json.loads(text)
                keys = list((pkg.get("require", {}) or {}).keys())
                keys += list((pkg.get("require-dev", {}) or {}).keys())
                _add_many("php", keys)
            except json.JSONDecodeError:
                pass
        elif name == "Gemfile":
            gems = re.findall(r"^\s*gem\s+[\"']([^\"']+)[\"']", text, flags=re.MULTILINE)
            _add_many("ruby", gems)

    dep_map = {eco: sorted(list(vals))[:80] for eco, vals in sorted(deps.items())}
    manifest_paths = [str(p.relative_to(root)).replace("\\", "/") for p in manifests]
    return dep_map, manifest_paths


def _detect_frameworks(dependencies_by_ecosystem: dict[str, list[str]]) -> tuple[list[str], dict[str, list[str]]]:
    """Infer frameworks from dependency names and group by language."""
    found: set[str] = set()
    by_lang: dict[str, set[str]] = {}

    dep_pool = set()
    for deps in dependencies_by_ecosystem.values():
        for d in deps:
            dep_pool.add(d.lower())

    for fw, langs in FRAMEWORK_KEYWORDS.items():
        if fw in dep_pool:
            found.add(fw)
            for lang in langs:
                by_lang.setdefault(lang, set()).add(fw)

    frameworks = sorted(found)
    frameworks_by_language = {k: sorted(list(v)) for k, v in sorted(by_lang.items())}
    return frameworks, frameworks_by_language


# ---------------------------------------------------------------------------
# Project type detection
# ---------------------------------------------------------------------------

_PROJECT_SIGNALS: list[tuple[str, str, list[str]]] = [
    # (filename, project_type, frameworks_to_check_inside)
    ("pyproject.toml", "python", ["fastapi", "flask", "django", "pytest", "click"]),
    ("setup.py", "python", []),
    ("setup.cfg", "python", []),
    ("Pipfile", "python", []),
    ("requirements.txt", "python", ["fastapi", "flask", "django"]),
    ("package.json", "node", ["react", "vue", "angular", "next", "express", "svelte"]),
    ("go.mod", "go", ["gin", "echo", "fiber"]),
    ("Cargo.toml", "rust", ["actix", "axum", "rocket", "tokio"]),
    ("pom.xml", "java", ["spring"]),
    ("build.gradle", "java", ["spring"]),
    ("build.gradle.kts", "kotlin", ["spring", "ktor"]),
    ("Gemfile", "ruby", ["rails", "sinatra"]),
    ("composer.json", "php", ["laravel", "symfony"]),
    ("Package.swift", "swift", ["vapor"]),
    ("mix.exs", "elixir", ["phoenix"]),
    (".csproj", "csharp", ["aspnet"]),
]


def _detect_project_type(root: Path) -> tuple[str, str, str, list[str]]:
    """Detect project type, name, description, and frameworks from config files."""
    project_type = "unknown"
    project_name = root.name
    project_description = ""
    frameworks: list[str] = []

    for filename, ptype, fw_keywords in _PROJECT_SIGNALS:
        # For .csproj, search for any matching file
        if filename.startswith("."):
            matches = list(root.glob(f"*{filename}"))
            if matches:
                project_type = ptype
                break
            continue

        config_path = root / filename
        if not config_path.is_file():
            continue

        project_type = ptype

        raw_content = _read_text_safe(config_path)
        content = raw_content.lower()

        # Try to extract name/description
        if filename == "pyproject.toml":
            try:
                import tomllib
                data = tomllib.loads(raw_content)
                proj = data.get("project", {})
                project_name = proj.get("name", project_name)
                project_description = proj.get("description", project_description)
            except Exception:
                # Fallback: simple line parsing
                in_project = False
                for line in content.splitlines():
                    if line.strip() == "[project]":
                        in_project = True
                        continue
                    if line.strip().startswith("[") and in_project:
                        in_project = False
                    if in_project and line.strip().startswith("name"):
                        val = line.split("=", 1)[-1].strip().strip('"').strip("'")
                        if val:
                            project_name = val
                    elif in_project and line.strip().startswith("description"):
                        val = line.split("=", 1)[-1].strip().strip('"').strip("'")
                        if val:
                            project_description = val
        elif filename == "package.json":
            import json as _json
            try:
                pkg = _json.loads(raw_content)
                project_name = pkg.get("name", project_name)
                project_description = pkg.get("description", project_description)
            except _json.JSONDecodeError:
                pass

        # Detect frameworks
        for kw in fw_keywords:
            if kw in content:
                frameworks.append(kw)

        break  # First match wins

    return project_type, project_name, project_description, frameworks


def _detect_entry_points(root: Path, code_files: list[str]) -> list[str]:
    """Find likely entry point files."""
    entries: list[str] = []
    entry_names = {
        "main.py", "app.py", "server.py", "index.py", "cli.py", "__main__.py",
        "main.go", "main.rs", "main.java", "Main.java",
        "index.js", "index.ts", "server.js", "server.ts", "app.js", "app.ts",
        "main.js", "main.ts",
        "Program.cs", "Main.kt",
        "manage.py",  # Django
    }

    for rel in code_files:
        name = Path(rel).name
        if name in entry_names:
            entries.append(rel)
            continue
        # Check for if __name__ == "__main__" pattern in Python files
        if name.endswith(".py"):
            full = root / rel
            try:
                text = full.read_text(encoding="utf-8", errors="replace")
                if 'if __name__' in text and '__main__' in text:
                    entries.append(rel)
            except OSError:
                pass

    return entries


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------


def detect(root: Path, max_files: int = 0, include_ignored: bool = False) -> DetectionResult:
    """Scan a directory and classify all files.

    Args:
        root: Directory to scan.
        max_files: Maximum files to process (0 = unlimited).
        include_ignored: If True, include files matched by ignore patterns.

    Returns:
        DetectionResult with classified files and metadata.
    """
    root = root.resolve()
    result = DetectionResult(root=str(root))

    # Load ignore patterns
    patterns: list[str] = []
    for ignore_file in (".codemapignore", ".gitignore"):
        patterns.extend(_parse_ignore_file(root / ignore_file))

    file_count = 0
    file_sizes: list[dict[str, Any]] = []
    file_lines: list[dict[str, Any]] = []

    for dirpath_str, dirnames, filenames in os.walk(root):
        dirpath = Path(dirpath_str)
        rel_dir = str(dirpath.relative_to(root))
        if rel_dir == ".":
            rel_dir = ""
        result.total_dirs_scanned += 1

        # Prune skipped directories (modify dirnames in-place)
        pruned: list[str] = []
        kept: list[str] = []
        for d in dirnames:
            rel_sub = f"{rel_dir}/{d}" if rel_dir else d
            if d in ALWAYS_SKIP:
                pruned.append(d)
                continue
            if not include_ignored and _matches_any(rel_sub, d, patterns):
                pruned.append(d)
                continue
            kept.append(d)
        if pruned:
            result.skipped_dirs.extend(f"{rel_dir}/{d}" if rel_dir else d for d in pruned)
        dirnames[:] = kept
        dirnames.sort()

        for fname in sorted(filenames):
            result.total_files_seen += 1
            if max_files and file_count >= max_files:
                result.skipped_limit += 1
                break

            rel_path = f"{rel_dir}/{fname}" if rel_dir else fname
            ext = Path(fname).suffix.lower()

            # Skip binary/generated files
            if ext in BINARY_EXTENSIONS:
                result.skipped_binary += 1
                continue

            # Skip ignored files
            if not include_ignored and _matches_any(rel_path, fname, patterns):
                result.skipped_ignored += 1
                continue

            # Skip files with no extension that aren't known config names
            if not ext and fname not in CONFIG_FILENAMES:
                result.extensionless_included += 1
                category = "other"
            else:
                # Classify
                if fname in CONFIG_FILENAMES:
                    category = "config"
                else:
                    category = _classify_file(rel_path, ext)

            result.files[category].append(rel_path)

            file_path = root / rel_path
            size_bytes = _file_size(file_path)

            # Count lines/words for text files (not images)
            if category != "images":
                lines, words = _count_file(file_path)
                result.total_lines += lines
                result.total_words += words
                file_lines.append({"path": rel_path, "lines": lines, "category": category})

            file_sizes.append({"path": rel_path, "bytes": size_bytes, "category": category})

            file_count += 1

        if max_files and file_count >= max_files:
            break

    result.total_files = sum(len(v) for v in result.files.values())
    # Standard estimate: ~4 chars per token, ~5 chars per word → ~1.25 words per token
    result.estimated_tokens = int(result.total_words * 100 / 75)

    # Project type detection
    ptype, pname, pdesc, fws = _detect_project_type(root)
    result.project_type = ptype
    result.project_name = pname
    result.project_description = pdesc
    result.languages = _language_stats(result.files["code"], result.files["tests"])

    dep_map, manifest_files = _extract_dependencies_from_manifests(root)
    result.dependencies_by_ecosystem = dep_map
    result.manifest_files = manifest_files

    dep_frameworks, fw_by_lang = _detect_frameworks(dep_map)
    combined_frameworks = sorted(set(fws + dep_frameworks))
    if not fw_by_lang and combined_frameworks:
        # Fallback grouping if frameworks were discovered only by signal scan
        fw_by_lang = {"General": combined_frameworks}
    result.frameworks_by_language = fw_by_lang
    result.frameworks = combined_frameworks

    # Entry points
    result.entry_points = _detect_entry_points(root, result.files["code"])

    result.largest_files = sorted(file_sizes, key=lambda x: x["bytes"], reverse=True)[:15]
    result.line_heavy_files = sorted(file_lines, key=lambda x: x["lines"], reverse=True)[:15]

    return result
