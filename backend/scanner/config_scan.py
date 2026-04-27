"""Layer 3: configuration file analysis — Dockerfile, nginx, apache."""

from __future__ import annotations

import re
from pathlib import Path

from backend.models import Finding
from backend.scanner.walker import find_configs, is_test_path


_NGINX_PROTOCOLS = re.compile(r"^\s*ssl_protocols\s+([^;]+);", re.M | re.I)
_NGINX_CIPHERS = re.compile(r"^\s*ssl_ciphers\s+([^;]+);", re.M | re.I)
_APACHE_PROTOCOLS = re.compile(r"^\s*SSLProtocol\s+(.+)$", re.M | re.I)
_DOCKER_OPENSSL = re.compile(r"openssl(?:[=\-])(\d+\.\d+\.\d+)", re.I)
_DOCKER_FROM = re.compile(r"^FROM\s+([^\s]+)", re.M | re.I)


_counter = {"n": 0}


def _next_id(rule: str) -> str:
    _counter["n"] += 1
    return f"QS-{rule}-{_counter['n']:03d}"


def scan(root: Path) -> list[Finding]:
    _counter["n"] = 0
    findings: list[Finding] = []
    for path, rel, kind in find_configs(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        in_test = is_test_path(rel)

        if kind == "nginx":
            for m in _NGINX_PROTOCOLS.finditer(text):
                protos = m.group(1)
                line = text[: m.start()].count("\n") + 1
                bad = [p for p in protos.split() if p.lower() in ("tlsv1", "tlsv1.1", "sslv2", "sslv3")]
                if bad:
                    findings.append(Finding(
                        id=_next_id("NGINX-TLS"),
                        rule_id="config.nginx.ssl_protocols",
                        category="config_weakness",
                        severity="high",
                        confidence="high",
                        file_path=rel,
                        line_start=line,
                        line_end=line,
                        code_snippet=m.group(0),
                        language="config",
                        in_test_context=in_test,
                        detection_layer="config",
                        rule_description=f"nginx ssl_protocols allows deprecated: {', '.join(bad)}",
                        remediation_class="harden_tls",
                    ))
            for m in _NGINX_CIPHERS.finditer(text):
                ciphers = m.group(1)
                line = text[: m.start()].count("\n") + 1
                if re.search(r"RC4|DES|MD5|NULL|EXPORT", ciphers, re.I):
                    findings.append(Finding(
                        id=_next_id("NGINX-CIPHER"),
                        rule_id="config.nginx.ssl_ciphers",
                        category="config_weakness",
                        severity="high",
                        confidence="high",
                        file_path=rel,
                        line_start=line,
                        line_end=line,
                        code_snippet=m.group(0),
                        language="config",
                        in_test_context=in_test,
                        detection_layer="config",
                        rule_description="nginx ssl_ciphers includes broken/deprecated cipher.",
                        remediation_class="harden_tls",
                    ))

        elif kind == "apache":
            for m in _APACHE_PROTOCOLS.finditer(text):
                line = text[: m.start()].count("\n") + 1
                value = m.group(1)
                if re.search(r"TLSv1(?:\.1)?\b|SSLv[23]", value, re.I):
                    findings.append(Finding(
                        id=_next_id("APACHE-TLS"),
                        rule_id="config.apache.ssl_protocol",
                        category="config_weakness",
                        severity="high",
                        confidence="high",
                        file_path=rel,
                        line_start=line,
                        line_end=line,
                        code_snippet=m.group(0),
                        language="config",
                        in_test_context=in_test,
                        detection_layer="config",
                        rule_description=f"Apache SSLProtocol allows deprecated: {value.strip()}",
                        remediation_class="harden_tls",
                    ))

        elif kind == "dockerfile":
            for m in _DOCKER_FROM.finditer(text):
                base = m.group(1)
                if re.search(r"openssl:1\.0|openssl:1\.1\.0", base, re.I):
                    line = text[: m.start()].count("\n") + 1
                    findings.append(Finding(
                        id=_next_id("DOCKER-OPENSSL"),
                        rule_id="config.dockerfile.openssl_base",
                        category="config_weakness",
                        severity="medium",
                        confidence="high",
                        file_path=rel,
                        line_start=line,
                        line_end=line,
                        code_snippet=m.group(0),
                        language="config",
                        in_test_context=in_test,
                        detection_layer="config",
                        rule_description=f"Base image pins an outdated OpenSSL: {base}",
                        remediation_class="upgrade_library",
                    ))
            for m in _DOCKER_OPENSSL.finditer(text):
                ver = m.group(1)
                if ver.startswith(("1.0.", "1.1.0")):
                    line = text[: m.start()].count("\n") + 1
                    findings.append(Finding(
                        id=_next_id("DOCKER-OPENSSL"),
                        rule_id="config.dockerfile.openssl_pin",
                        category="config_weakness",
                        severity="medium",
                        confidence="high",
                        file_path=rel,
                        line_start=line,
                        line_end=line,
                        code_snippet=m.group(0),
                        language="config",
                        in_test_context=in_test,
                        detection_layer="config",
                        rule_description=f"Installs outdated OpenSSL pin: {ver}",
                        remediation_class="upgrade_library",
                    ))
    return findings
