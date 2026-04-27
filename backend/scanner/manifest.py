"""Layer 1: manifest and lockfile analysis.

Pure parsing. No package-manager execution, ever.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from backend.models import Finding
from backend.scanner.db import lookup as db_lookup
from backend.scanner.walker import find_manifests, is_test_path


_PIP_LINE_RE = re.compile(r"^\s*([A-Za-z0-9_.\-\[\]]+)\s*([=<>!~]=?\s*[\w.\-+]+)?")
_FINDING_COUNTER = {"n": 0}


def _next_id(rule: str) -> str:
    _FINDING_COUNTER["n"] += 1
    return f"QS-{rule}-{_FINDING_COUNTER['n']:03d}"


def _severity_for(quantum_status: str) -> tuple[str, str]:
    # (severity, category)
    if quantum_status == "pqc":
        return "info", "pqc_adoption"
    if quantum_status == "vulnerable":
        return "high", "quantum_vulnerable"
    if quantum_status == "deprecated":
        return "medium", "deprecated_primitive"
    return "info", "suspected"


def _dep_finding(
    repo_root: Path, rel: str, line: int, snippet: str,
    lib_name: str, version: str | None,
) -> Finding | None:
    lib = db_lookup(lib_name)
    if not lib:
        return None
    # Library-level finding: one per dep, summarizing the strongest concern
    primitives = lib.get("exposes", [])
    # Prefer the most serious posture for the headline
    priorities = ["pqc", "vulnerable", "deprecated", "symmetric_safe"]
    sorted_prims = sorted(
        primitives,
        key=lambda p: priorities.index(p["quantum_status"]) if p["quantum_status"] in priorities else 99,
    )
    primary = sorted_prims[0] if sorted_prims else None
    if not primary:
        return None
    severity, category = _severity_for(primary["quantum_status"])
    algo = primary.get("primitive")
    confidence = "high" if version else "low"
    rule_short = f"{lib_name}-dep".upper().replace("@", "").replace("/", "-").replace("_", "-")
    return Finding(
        id=_next_id(rule_short),
        rule_id=f"manifest.{lib_name}",
        category=category,
        severity=severity,
        confidence=confidence,
        file_path=rel,
        line_start=line,
        line_end=line,
        code_snippet=snippet,
        language="manifest",
        in_test_context=is_test_path(rel),
        algorithm=algo,
        library=lib_name,
        version=version,
        detection_layer="manifest",
        rule_description=f"Dependency {lib_name}{('@' + version) if version else ''} exposes {algo} ({primary['quantum_status']}).",
        remediation_class="upgrade_library" if primary["quantum_status"] == "deprecated" else "review_dependency",
    )


def _parse_requirements(text: str) -> list[tuple[int, str, str | None, str]]:
    out: list[tuple[int, str, str | None, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        m = _PIP_LINE_RE.match(stripped)
        if m:
            name = m.group(1).split("[")[0]
            ver = None
            if m.group(2):
                ver_match = re.search(r"([\d.]+[\w.\-+]*)", m.group(2))
                ver = ver_match.group(1) if ver_match else None
            out.append((i, name.lower(), ver, line.rstrip()))
    return out


def _parse_pyproject(text: str) -> list[tuple[int, str, str | None, str]]:
    try:
        data = tomllib.loads(text)
    except Exception:
        return []
    deps_out: list[tuple[int, str, str | None, str]] = []

    def add(name: str, ver: str | None):
        deps_out.append((1, name.lower(), ver, f"{name} {ver or ''}"))

    project_deps = data.get("project", {}).get("dependencies", []) or []
    for d in project_deps:
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*([=<>!~]=?\s*[\w.\-+]+)?", str(d))
        if m:
            ver = None
            if m.group(2):
                vm = re.search(r"([\d.]+[\w.\-+]*)", m.group(2))
                ver = vm.group(1) if vm else None
            add(m.group(1), ver)
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {}) or {}
    for name, spec in poetry_deps.items():
        if name.lower() == "python":
            continue
        ver = None
        if isinstance(spec, str):
            vm = re.search(r"([\d.]+[\w.\-+]*)", spec)
            ver = vm.group(1) if vm else None
        elif isinstance(spec, dict) and "version" in spec:
            vm = re.search(r"([\d.]+[\w.\-+]*)", str(spec["version"]))
            ver = vm.group(1) if vm else None
        add(name, ver)
    return deps_out


def _parse_package_json(text: str) -> list[tuple[int, str, str | None, str]]:
    try:
        data = json.loads(text)
    except Exception:
        return []
    out: list[tuple[int, str, str | None, str]] = []
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps = data.get(section, {}) or {}
        for name, ver in deps.items():
            vstr = None
            if isinstance(ver, str):
                vm = re.search(r"([\d.]+[\w.\-+]*)", ver)
                vstr = vm.group(1) if vm else None
            out.append((1, name, vstr, f"{name}: {ver}"))
    return out


def scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path, rel, kind in find_manifests(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        deps: list[tuple[int, str, str | None, str]] = []
        if kind == "requirements":
            deps = _parse_requirements(text)
        elif kind == "pyproject":
            deps = _parse_pyproject(text)
        elif kind == "package_json":
            deps = _parse_package_json(text)
        elif kind == "setup_py":
            # Cheap regex for install_requires
            m = re.search(r"install_requires\s*=\s*\[([^\]]*)\]", text, re.S)
            if m:
                for entry in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
                    nm = _PIP_LINE_RE.match(entry)
                    if nm:
                        deps.append((1, nm.group(1).lower(), None, entry))
        # Lockfile parsing is intentionally thin; manifests carry enough signal for v1.

        for (line, name, ver, snippet) in deps:
            f = _dep_finding(root, rel, line, snippet, name, ver)
            if f:
                findings.append(f)
    return findings
