"""Orchestrated scan over a cloned repo."""

from __future__ import annotations

from pathlib import Path

from backend.models import Finding
from backend.scanner import certs, config_scan, manifest, source


def scan_repo(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(manifest.scan(root))
    findings.extend(source.scan(root))
    findings.extend(config_scan.scan(root))
    findings.extend(certs.scan(root))
    # Dedup by (rule_id, file, line, algorithm)
    seen = set()
    deduped: list[Finding] = []
    for f in findings:
        key = (f.rule_id, f.file_path, f.line_start, f.algorithm)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    # Cap at 50 for LLM token budget — but always preserve the import
    # summaries (one per library) so readers see the dependency picture
    # even when the rule findings dominate.
    imports = [f for f in deduped if f.rule_id.endswith(".import")]
    non_imports = [f for f in deduped if not f.rule_id.endswith(".import")]
    budget = max(0, 50 - len(imports))
    return imports + non_imports[:budget]
