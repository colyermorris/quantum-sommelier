"""Layer 2: source-code analysis via tree-sitter.

Tree-sitter queries capture:
  - imports of known crypto modules (low-confidence)
  - invocations of sensitive APIs (high-confidence)
  - literal key sizes / curve names / algorithm strings
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from backend.models import Finding
from backend.scanner.walker import walk_source, is_test_path

try:
    from tree_sitter_languages import get_language, get_parser  # type: ignore
    _TS_AVAILABLE = True
except Exception:  # pragma: no cover
    _TS_AVAILABLE = False


# ── Detection rules: pattern → (algorithm, severity, category, description)
# These are lightweight keyword/regex rules applied over the source text. For a
# real tree-sitter query implementation, see the PRD §4.1 Layer 2; we run
# tree-sitter to validate that the match lives in a call expression rather
# than a comment or string literal.

RULES: list[dict] = [
    {
        "id": "RSA-KEYGEN",
        "pattern": re.compile(r"\brsa\.generate_private_key\s*\(", re.I),
        "algorithm": "RSA",
        "severity": "high",
        "category": "quantum_vulnerable",
        "description": "RSA key generation — quantum-vulnerable via Shor's algorithm.",
        "remediation_class": "migrate_to_pqc",
        "capture_key_size": re.compile(r"key_size\s*=\s*(\d+)"),
    },
    {
        "id": "EC-KEYGEN",
        "pattern": re.compile(r"\bec\.generate_private_key\s*\(", re.I),
        "algorithm": "ECDSA",
        "severity": "high",
        "category": "quantum_vulnerable",
        "description": "Elliptic-curve key generation — quantum-vulnerable.",
        "remediation_class": "migrate_to_pqc",
        "capture_curve": re.compile(r"ec\.(SECP\d+R1|SECP\d+K1|P\d+|secp\d+\w*)"),
    },
    {
        "id": "ECDSA-SIGN",
        "pattern": re.compile(r"\bec\.ECDSA\s*\(|\becdsa\.sign\s*\("),
        "algorithm": "ECDSA",
        "severity": "high",
        "category": "quantum_vulnerable",
        "description": "ECDSA signing — quantum-vulnerable.",
        "remediation_class": "migrate_to_pqc",
    },
    {
        "id": "MD5-CALL",
        "pattern": re.compile(r"\bhashlib\.md5\s*\(|\bcreateHash\s*\(\s*['\"]md5['\"]\)|\bMD5\s*\(", re.I),
        "algorithm": "MD5",
        "severity": "medium",
        "category": "deprecated_primitive",
        "description": "MD5 is cryptographically broken; do not use for security.",
        "remediation_class": "replace_hash",
    },
    {
        "id": "SHA1-CALL",
        "pattern": re.compile(r"\bhashlib\.sha1\s*\(|\bcreateHash\s*\(\s*['\"]sha-?1['\"]\)", re.I),
        "algorithm": "SHA-1",
        "severity": "medium",
        "category": "deprecated_primitive",
        "description": "SHA-1 is cryptographically broken.",
        "remediation_class": "replace_hash",
    },
    {
        "id": "JWT-RS256",
        "pattern": re.compile(r"algorithm[s]?\s*[:=]\s*['\"]RS256['\"]|['\"]alg['\"]\s*:\s*['\"]RS256['\"]"),
        "algorithm": "RS256",
        "severity": "high",
        "category": "quantum_vulnerable",
        "description": "JWT signed with RS256 — RSA-backed, quantum-vulnerable.",
        "remediation_class": "migrate_to_pqc",
    },
    {
        "id": "JWT-ES256",
        "pattern": re.compile(r"algorithm[s]?\s*[:=]\s*['\"]ES256['\"]|['\"]alg['\"]\s*:\s*['\"]ES256['\"]"),
        "algorithm": "ES256",
        "severity": "high",
        "category": "quantum_vulnerable",
        "description": "JWT signed with ES256 — ECDSA-backed, quantum-vulnerable.",
        "remediation_class": "migrate_to_pqc",
    },
    {
        "id": "JWT-NONE",
        "pattern": re.compile(r"algorithm[s]?\s*[:=]\s*['\"]none['\"]"),
        "algorithm": "none",
        "severity": "critical",
        "category": "config_weakness",
        "description": "JWT algorithm 'none' disables signature verification.",
        "remediation_class": "remove_insecure_option",
    },
    {
        "id": "AES-ECB",
        "pattern": re.compile(r"AES\.new\s*\([^)]*AES\.MODE_ECB|createCipheriv\s*\(\s*['\"]aes-\d+-ecb['\"]", re.I),
        "algorithm": "AES-ECB",
        "severity": "high",
        "category": "config_weakness",
        "description": "AES in ECB mode — not semantically secure.",
        "remediation_class": "change_mode",
    },
    {
        "id": "ED25519-SIGN",
        "pattern": re.compile(r"\bed25519\.sign\s*\(|\bEd25519PrivateKey\b"),
        "algorithm": "Ed25519",
        "severity": "low",
        "category": "quantum_vulnerable",
        "description": "Ed25519 is quantum-vulnerable (Shor's algorithm).",
        "remediation_class": "plan_migration",
    },
    {
        "id": "X25519-KEX",
        "pattern": re.compile(r"\bx25519\.(getSharedSecret|generate_private_key)|\bX25519PrivateKey\b"),
        "algorithm": "X25519",
        "severity": "low",
        "category": "quantum_vulnerable",
        "description": "X25519 key exchange is quantum-vulnerable.",
        "remediation_class": "plan_migration",
    },
    {
        "id": "ML-KEM-USE",
        "pattern": re.compile(r"\bml_kem(?:512|768|1024)\b|\bMLKEMPrivateKey\b|@noble/post-quantum/ml-kem", re.I),
        "algorithm": "ML-KEM",
        "severity": "info",
        "category": "pqc_adoption",
        "description": "ML-KEM in use — post-quantum KEM (FIPS 203).",
        "remediation_class": "retain",
    },
    {
        "id": "ML-DSA-USE",
        "pattern": re.compile(r"\bml_dsa(?:44|65|87)\b|\bMLDSAPrivateKey\b|@noble/post-quantum/ml-dsa", re.I),
        "algorithm": "ML-DSA",
        "severity": "info",
        "category": "pqc_adoption",
        "description": "ML-DSA in use — post-quantum signatures (FIPS 204).",
        "remediation_class": "retain",
    },
    {
        "id": "AES-GCM",
        "pattern": re.compile(r"\bAESGCM\s*\(|\bAES\.MODE_GCM\b|createCipheriv\s*\(\s*['\"]aes-256-gcm['\"]", re.I),
        "algorithm": "AES-256-GCM",
        "severity": "info",
        "category": "suspected",
        "description": "AES-GCM symmetric encryption — quantum-safe with adequate key size.",
        "remediation_class": "retain",
    },
    {
        "id": "INSECURE-RANDOM",
        "pattern": re.compile(r"\bMath\.random\s*\(\)"),
        "algorithm": "Math.random",
        "severity": "medium",
        "category": "config_weakness",
        "description": "Math.random is not cryptographically secure.",
        "remediation_class": "replace_rng",
    },
]


_IMPORT_RULES_PY = [
    ("hashlib", "hashlib", "info"),
    ("from Crypto", "pycrypto(dome)", "info"),
    ("from cryptography", "cryptography", "info"),
    ("import rsa", "rsa", "info"),
    ("import ecdsa", "ecdsa", "info"),
    ("import jwt", "PyJWT", "info"),
    ("import paramiko", "paramiko", "info"),
]
_IMPORT_RULES_JS = [
    ("from 'crypto'", "node:crypto", "info"),
    ("require('crypto')", "node:crypto", "info"),
    ("from '@noble/post-quantum", "@noble/post-quantum", "info"),
    ("from '@noble/hashes", "@noble/hashes", "info"),
    ("from '@noble/curves", "@noble/curves", "info"),
    ("from 'crypto-js'", "crypto-js", "info"),
    ("from 'jsonwebtoken'", "jsonwebtoken", "info"),
]


# Library descriptions shown when the scanner collapses N imports of the
# same library into a single finding. Keep these short — the frontend edu
# templates carry the deeper text.
_LIBRARY_BLURB = {
    "hashlib":             "Python stdlib hash primitives — MD5/SHA-1/SHA-2/SHA-3. Presence is neutral; specific algorithm calls are graded separately.",
    "pycrypto(dome)":      "PyCrypto/PyCryptodome — classical symmetric and public-key primitives. No post-quantum algorithms.",
    "cryptography":        "pyca/cryptography — the serious Python crypto library. Broad classical surface (AES, RSA, ECDSA, ECDH, Ed25519, x25519); no PQ primitives yet.",
    "rsa":                 "The `rsa` pure-Python library — RSA keygen / sign / encrypt. Quantum-vulnerable by construction.",
    "ecdsa":               "Pure-Python ECDSA — elliptic-curve signatures. Broken by Shor's algorithm under a CRQC.",
    "PyJWT":               "JSON Web Token library. HS256/RS256/ES256 today; no PQ signature algorithms.",
    "paramiko":            "SSH protocol library. Classical key exchange and host keys (RSA/ECDSA/Ed25519).",
    "node:crypto":         "Node's built-in crypto module — symmetric and public-key primitives. Exposes the runtime's OpenSSL.",
    "@noble/post-quantum": "@noble/post-quantum — ML-KEM / ML-DSA / SLH-DSA in pure JS. Finding this is a good sign.",
    "@noble/hashes":       "@noble/hashes — audited pure-JS hash primitives (SHA-2/3, BLAKE, HMAC, HKDF).",
    "@noble/curves":       "@noble/curves — audited pure-JS elliptic curves. Classical (secp256k1, P-256, Ed25519) — not PQ.",
    "crypto-js":           "crypto-js — legacy JS crypto. Often paired with weak modes and brittle IV handling.",
    "jsonwebtoken":        "jsonwebtoken — JWT sign/verify. No PQ signature algorithms.",
}

# Libraries whose mere presence is a positive PQ signal.
_LIBRARY_PQ_POSITIVE = {"@noble/post-quantum"}


_counter = {"n": 0}


def _next_id(rule: str) -> str:
    _counter["n"] += 1
    return f"QS-{rule}-{_counter['n']:03d}"


def _context_snippet(lines: list[str], match_line: int) -> tuple[int, int, str]:
    start = max(0, match_line - 2)
    end = min(len(lines), match_line + 3)
    snippet = "\n".join(lines[start:end])
    return start + 1, end, snippet


def _tree_sitter_context(parser, source_bytes: bytes, byte_offset: int) -> str | None:
    """Return the node kind at the byte offset, or None. Used to reject matches
    that live inside comments or string literals."""
    if parser is None:
        return "unknown"
    try:
        tree = parser.parse(source_bytes)
        node = tree.root_node.descendant_for_byte_range(byte_offset, byte_offset + 1)
        return node.type if node else None
    except Exception:
        return "unknown"


def scan(root: Path) -> list[Finding]:
    _counter["n"] = 0
    findings: list[Finding] = []

    parsers: dict[str, object] = {}
    if _TS_AVAILABLE:
        for lang in ("python", "javascript", "typescript"):
            try:
                parsers[lang] = get_parser(lang)
            except Exception:
                parsers[lang] = None

    # (library, language) -> {'files': [...], 'first_snippet': str, 'first_start': int, 'first_end': int, 'first_rel': str}
    import_hits: dict[tuple[str, str], dict] = {}

    for abs_path, rel, language in walk_source(root):
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lines = text.splitlines()
        source_bytes = text.encode("utf-8", errors="replace")
        parser = parsers.get(language) if _TS_AVAILABLE else None
        in_test = is_test_path(rel)

        # Invocation / literal rules
        for rule in RULES:
            for m in rule["pattern"].finditer(text):
                byte_off = m.start()
                node_type = _tree_sitter_context(parser, source_bytes, byte_off) if parser else "unknown"
                if node_type and ("comment" in node_type or "string" == node_type):
                    continue
                match_line = text.count("\n", 0, byte_off)
                start_line, end_line, snippet = _context_snippet(lines, match_line)

                key_size = None
                curve = None
                if "capture_key_size" in rule:
                    tail = text[m.start(): m.start() + 240]
                    ks = rule["capture_key_size"].search(tail)
                    if ks:
                        key_size = int(ks.group(1))
                if "capture_curve" in rule:
                    tail = text[m.start(): m.start() + 240]
                    cm = rule["capture_curve"].search(tail)
                    if cm:
                        curve = cm.group(1)

                confidence = "high" if not in_test else "medium"
                findings.append(Finding(
                    id=_next_id(rule["id"]),
                    rule_id=f"source.{language}.{rule['id'].lower()}",
                    category=rule["category"],
                    severity=rule["severity"],
                    confidence=confidence,
                    file_path=rel,
                    line_start=start_line,
                    line_end=end_line,
                    code_snippet=snippet[:2000],
                    language=language,
                    in_test_context=in_test,
                    algorithm=rule["algorithm"],
                    key_size=key_size,
                    curve=curve,
                    detection_layer="source",
                    rule_description=rule["description"],
                    remediation_class=rule["remediation_class"],
                ))

        # Import-only rules — collect; emit one finding per (library, language).
        import_rules = _IMPORT_RULES_PY if language == "python" else _IMPORT_RULES_JS
        for needle, lib_label, _sev in import_rules:
            idx = text.find(needle)
            if idx == -1:
                continue
            key = (lib_label, language)
            line_no = text.count("\n", 0, idx)
            start_line, end_line, snippet = _context_snippet(lines, line_no)
            bucket = import_hits.get(key)
            if bucket is None:
                import_hits[key] = {
                    "files": [rel],
                    "first_rel": rel,
                    "first_start": start_line,
                    "first_end": end_line,
                    "first_snippet": snippet,
                    "in_test": in_test,
                }
            else:
                if rel not in bucket["files"]:
                    bucket["files"].append(rel)
                # Prefer the first non-test occurrence as the representative
                if bucket["in_test"] and not in_test:
                    bucket.update({
                        "first_rel": rel,
                        "first_start": start_line,
                        "first_end": end_line,
                        "first_snippet": snippet,
                        "in_test": in_test,
                    })

    # Emit one consolidated finding per (library, language).
    for (lib_label, language), b in import_hits.items():
        count = len(b["files"])
        blurb = _LIBRARY_BLURB.get(lib_label, "Third-party crypto-adjacent library.")
        where = (f"{count} file" if count == 1 else f"{count} files")
        desc = f"`{lib_label}` imported across {where} — {blurb}"
        sev = "info"
        if lib_label in _LIBRARY_PQ_POSITIVE:
            sev = "info"  # positive signal, keep info
        findings.append(Finding(
            id=_next_id("IMPORT"),
            rule_id=f"source.{language}.import",
            category="suspected",
            severity=sev,
            confidence="medium",
            file_path=b["first_rel"],
            line_start=b["first_start"],
            line_end=b["first_end"],
            code_snippet=b["first_snippet"][:600],
            language=language,
            in_test_context=b["in_test"],
            library=lib_label,
            detection_layer="source",
            rule_description=desc,
            remediation_class="review_dependency",
        ))

    return findings
