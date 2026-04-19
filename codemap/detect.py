"""File discovery, classification, and project-type detection.

Walks a directory tree respecting .gitignore and .codemapignore,
classifies files by type, detects the project framework, and
estimates token counts.
"""

from __future__ import annotations

import fnmatch
import os
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
    files: dict[str, list[str]] = field(default_factory=lambda: {
        "code": [], "docs": [], "config": [], "tests": [], "images": [], "other": [],
    })
    project_type: str = "unknown"
    project_name: str = ""
    project_description: str = ""
    frameworks: list[str] = field(default_factory=list)
    skipped_dirs: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "total_words": self.total_words,
            "estimated_tokens": self.estimated_tokens,
            "files": self.files,
            "project_type": self.project_type,
            "project_name": self.project_name,
            "project_description": self.project_description,
            "frameworks": self.frameworks,
            "entry_points": self.entry_points,
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

        try:
            content = config_path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            content = ""

        # Try to extract name/description
        if filename == "pyproject.toml":
            try:
                import tomllib
                data = tomllib.loads(content)
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
                pkg = _json.loads(content)
                project_name = pkg.get("name", project_name)
                project_description = pkg.get("description", project_description)
            except _json.JSONDecodeError:
                pass
            import json as _json
            try:
                pkg = _json.loads(content)
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


def detect(root: Path, max_files: int = 0) -> DetectionResult:
    """Scan a directory and classify all files.

    Args:
        root: Directory to scan.
        max_files: Maximum files to process (0 = unlimited).

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

    for dirpath_str, dirnames, filenames in os.walk(root):
        dirpath = Path(dirpath_str)
        rel_dir = str(dirpath.relative_to(root))
        if rel_dir == ".":
            rel_dir = ""

        # Prune skipped directories (modify dirnames in-place)
        dirnames[:] = [
            d for d in dirnames
            if d not in ALWAYS_SKIP
            and not d.startswith(".")
            and not _matches_any(
                f"{rel_dir}/{d}" if rel_dir else d, d, patterns
            )
        ]
        dirnames.sort()

        for fname in sorted(filenames):
            if max_files and file_count >= max_files:
                break

            rel_path = f"{rel_dir}/{fname}" if rel_dir else fname
            ext = Path(fname).suffix.lower()

            # Skip binary/generated files
            if ext in BINARY_EXTENSIONS:
                continue

            # Skip ignored files
            if _matches_any(rel_path, fname, patterns):
                continue

            # Skip files with no extension that aren't known config names
            if not ext and fname not in CONFIG_FILENAMES:
                continue

            # Classify
            if fname in CONFIG_FILENAMES:
                category = "config"
            else:
                category = _classify_file(rel_path, ext)

            # Skip "other" - we only care about code, docs, config, tests, images
            if category == "other":
                continue

            result.files[category].append(rel_path)

            # Count lines/words for text files (not images)
            if category != "images":
                lines, words = _count_file(root / rel_path)
                result.total_lines += lines
                result.total_words += words

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
    result.frameworks = fws

    # Entry points
    result.entry_points = _detect_entry_points(root, result.files["code"])

    return result
