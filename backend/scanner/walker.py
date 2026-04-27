"""Walk the cloned repo, yielding (relpath, language) pairs, respecting exclusions."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator


EXCLUDE_DIRS = {
    "node_modules", "venv", ".venv", "env", "__pycache__",
    "dist", "build", "out", ".git", ".next", "target",
    "vendor", "third_party", "coverage",
}
MAX_FILE_BYTES = 1 * 1024 * 1024  # 1 MB

SOURCE_SUFFIXES = {
    ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".jsx": "javascript",
}

MANIFEST_NAMES = {
    "requirements.txt": "requirements",
    "pyproject.toml": "pyproject",
    "Pipfile": "pipfile",
    "Pipfile.lock": "pipfile_lock",
    "poetry.lock": "poetry_lock",
    "setup.py": "setup_py",
    "setup.cfg": "setup_cfg",
    "package.json": "package_json",
    "package-lock.json": "package_lock_json",
    "yarn.lock": "yarn_lock",
    "pnpm-lock.yaml": "pnpm_lock",
}

CONFIG_NAMES = {
    "Dockerfile": "dockerfile",
    "dockerfile": "dockerfile",
    "nginx.conf": "nginx",
    "httpd.conf": "apache",
}

CERT_SUFFIXES = {".pem", ".crt", ".cer", ".key", ".p12", ".pfx", ".jks", ".keystore"}

TEST_PATH_MARKERS = ("fixtures/", "testdata/", "/test/", "/tests/", "__tests__/")


def is_test_path(relpath: str) -> bool:
    return any(m in relpath.replace("\\", "/") for m in TEST_PATH_MARKERS)


def walk_source(root: Path) -> Iterator[tuple[Path, str, str]]:
    """Yield (abs_path, rel_path, language) for scannable source files."""
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(ex in p.parts for ex in EXCLUDE_DIRS):
            continue
        if p.suffix not in SOURCE_SUFFIXES:
            continue
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        rel = str(p.relative_to(root))
        yield p, rel, SOURCE_SUFFIXES[p.suffix]


def find_manifests(root: Path) -> list[tuple[Path, str, str]]:
    hits: list[tuple[Path, str, str]] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(ex in p.parts for ex in EXCLUDE_DIRS):
            continue
        kind = MANIFEST_NAMES.get(p.name)
        if kind:
            hits.append((p, str(p.relative_to(root)), kind))
    return hits


def find_configs(root: Path) -> list[tuple[Path, str, str]]:
    hits: list[tuple[Path, str, str]] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(ex in p.parts for ex in EXCLUDE_DIRS):
            continue
        if p.name in CONFIG_NAMES:
            hits.append((p, str(p.relative_to(root)), CONFIG_NAMES[p.name]))
        elif p.suffix == ".conf" and "nginx" in p.name.lower():
            hits.append((p, str(p.relative_to(root)), "nginx"))
    return hits


def find_cert_files(root: Path) -> list[tuple[Path, str]]:
    hits: list[tuple[Path, str]] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(ex in p.parts for ex in EXCLUDE_DIRS):
            continue
        if p.suffix.lower() in CERT_SUFFIXES:
            hits.append((p, str(p.relative_to(root))))
    return hits
