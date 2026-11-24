"""Privacy scanner for repository content and generated artifacts.

Detects likely secrets, personal e-mail addresses, private tracker organization URLs and
private-key material. Findings are candidates for human review; the scanner reports the
rule and location but never echoes the matched secret value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Domains reserved for documentation/examples (RFC 2606/6761) and GitHub noreply.
ALLOWED_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "example.invalid",
    "invalid",
    "test",
    "users.noreply.github.com",
    "noreply.github.com",
}
ALLOWED_TRACKER_ORGS = {
    "example",
    "contoso",
    "fabrikam",
    "synthetic",
    "fixture",
    "your-org",
    "{organization}",
    "{org}",
    "org",
    "organization",
    # public Microsoft services on the same domain, not customer organizations
    "marketplace",
    "app",
    "go",
    "status",
}

RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    (
        "bearer_token",
        re.compile(r"(?i)\bauthorization\s*[:=]\s*[\"']?(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{16,}"),
    ),
    (
        "azure_pat_assignment",
        re.compile(
            r"(?i)\b(?:pat|personal[_-]?access[_-]?token|azure_devops_ext_pat)\s*[:=]\s*[\"']?[a-z0-9]{52}\b"
        ),
    ),
    (
        "generic_secret_assignment",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|client_secret|api[_-]?key)\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"
        ),
    ),
)
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")
ADO_ORG_URL = re.compile(
    r"(?i)https?://dev\.azure\.com/([^/\s\"'<>)]+)|https?://([a-z0-9-]+)\.visualstudio\.com"
)

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".json",
    ".toml",
    ".txt",
    ".html",
    ".css",
    ".js",
    ".yml",
    ".yaml",
    ".csv",
    ".cfg",
    ".ini",
    ".gitignore",
    ".feature",
    ".mmd",
    ".ps1",
    ".sh",
    "",
}


@dataclass(frozen=True)
class PrivacyFinding:
    path: str
    line: int
    rule: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}"


def scan_text(text: str, path: str = "<text>") -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in RULES:
            if pattern.search(line):
                findings.append(PrivacyFinding(path, number, rule))
        for match in EMAIL.finditer(line):
            domain = match.group(1).lower()
            if domain not in ALLOWED_EMAIL_DOMAINS and not domain.endswith(".example"):
                findings.append(PrivacyFinding(path, number, "email_address"))
        for match in ADO_ORG_URL.finditer(line):
            org = (match.group(1) or match.group(2) or "").lower()
            if org not in ALLOWED_TRACKER_ORGS:
                findings.append(PrivacyFinding(path, number, "tracker_org_url"))
    return findings


def scan_paths(paths: list[Path], root: Path) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    for path in paths:
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_text(text, path.relative_to(root).as_posix()))
    return findings
