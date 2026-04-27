"""Layer 4: committed certificate / private-key detection.

Reads at most 64 bytes of any candidate file to identify the PEM header.
Never reads key material beyond that.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.models import Finding
from backend.scanner.walker import find_cert_files, is_test_path


_PEM_HEADER_RE = re.compile(
    rb"-----BEGIN\s+(?P<kind>RSA|EC|DSA|OPENSSH|ENCRYPTED|ED25519|PGP)?\s*(?:PRIVATE\s+KEY|CERTIFICATE)-----"
)


_counter = {"n": 0}


def _next_id() -> str:
    _counter["n"] += 1
    return f"QS-PEM-COMMIT-{_counter['n']:03d}"


def scan(root: Path) -> list[Finding]:
    _counter["n"] = 0
    findings: list[Finding] = []
    for path, rel in find_cert_files(root):
        try:
            with path.open("rb") as f:
                head = f.read(64)
        except OSError:
            continue
        m = _PEM_HEADER_RE.search(head)
        if not m:
            continue
        header = m.group(0).decode("ascii", errors="replace")
        is_private = b"PRIVATE KEY" in head
        sev = "critical" if is_private else "medium"
        findings.append(Finding(
            id=_next_id(),
            rule_id="cert.committed",
            category="committed_secret",
            severity=sev,
            confidence="high",
            file_path=rel,
            line_start=1,
            line_end=1,
            code_snippet=header + " [REDACTED — scanner read 64 bytes only]",
            language="config",
            in_test_context=is_test_path(rel),
            detection_layer="cert",
            rule_description=("Committed private key material." if is_private
                              else "Committed X.509 certificate."),
            remediation_class="remove_secret" if is_private else "review_cert",
        ))
    return findings
