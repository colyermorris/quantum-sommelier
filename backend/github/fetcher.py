"""Clone a public GitHub repo to an ephemeral working directory."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from backend.config import SETTINGS
from backend.github.token_pool import POOL


REPO_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[\w.-]+)/(?P<name>[\w.-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


class RepoFetchError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass
class ClonedRepo:
    owner: str
    name: str
    url: str
    ref: str
    commit_sha: str
    primary_language: str
    stars: int
    description: str
    path: Path
    size_bytes: int


def normalize_repo_url(repo_url: str) -> tuple[str, str]:
    raw = repo_url.strip()
    short = re.match(r"^([\w.-]+)/([\w.-]+?)(?:\.git)?$", raw)
    if short:
        return short.group(1), short.group(2)
    m = REPO_URL_RE.match(raw)
    if not m:
        raise RepoFetchError("invalid_url", "That URL doesn't point to a public GitHub repo.")
    return m.group("owner"), m.group("name")


def _auth_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "quantum-sommelier/1.0"}
    tok = POOL.next()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


def _repo_meta(owner: str, name: str) -> dict:
    try:
        resp = httpx.get(
            f"https://api.github.com/repos/{owner}/{name}",
            headers=_auth_headers(),
            timeout=15,
        )
    except httpx.RequestError as exc:
        raise RepoFetchError("github_unreachable", f"GitHub unreachable: {exc}", retryable=True)
    if resp.status_code == 404:
        raise RepoFetchError("not_found", f"Repo {owner}/{name} not found or not public.")
    if resp.status_code == 403:
        raise RepoFetchError("rate_limited", "GitHub rate limit hit.", retryable=True)
    resp.raise_for_status()
    data = resp.json()
    if data.get("private"):
        raise RepoFetchError("not_public", "Private repos are not supported.")
    if data.get("size", 0) * 1024 > SETTINGS.max_repo_bytes:
        raise RepoFetchError(
            "too_large",
            "That cellar is oversized. We only pour from repos under 500 MB.",
        )
    return data


def _dir_size(path: Path) -> int:
    total = 0
    for dp, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                continue
    return total


def clone(owner: str, name: str, ref: str, job_id: str) -> ClonedRepo:
    meta = _repo_meta(owner, name)

    # If the caller passed the default "main", prefer the repo's actual default branch
    # (many older repos still use "master", some use "trunk"/"develop"/etc.).
    default_branch = meta.get("default_branch") or "main"
    target_ref = default_branch if (not ref or ref == "main") else ref

    work_root = Path(SETTINGS.work_dir)
    work_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest = work_root / job_id
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(mode=0o700)

    tok = POOL.next()
    url = f"https://github.com/{owner}/{name}.git"
    authed_url = (
        f"https://x-access-token:{tok}@github.com/{owner}/{name}.git" if tok else url
    )

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    def _run_clone(with_branch: bool) -> subprocess.CompletedProcess:
        base = ["git", "clone", "--depth", "1"]
        if with_branch:
            base += ["--single-branch", "--branch", target_ref]
        base += [authed_url, str(dest)]
        return subprocess.run(
            base, env=env, timeout=60,
            capture_output=True, text=True, check=False,
        )

    try:
        proc = _run_clone(with_branch=True)
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest, ignore_errors=True)
        raise RepoFetchError("clone_timeout", "Clone timed out. The repo may be too large.")

    if proc.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        stderr = (proc.stderr or "").strip()
        branch_missing = ("Remote branch" in stderr) or ("not found in upstream" in stderr.lower())
        if branch_missing:
            # Last resort: let git pick the remote HEAD.
            dest.mkdir(mode=0o700)
            try:
                proc2 = _run_clone(with_branch=False)
            except subprocess.TimeoutExpired:
                shutil.rmtree(dest, ignore_errors=True)
                raise RepoFetchError("clone_timeout", "Clone timed out.")
            if proc2.returncode != 0:
                shutil.rmtree(dest, ignore_errors=True)
                raise RepoFetchError(
                    "clone_failed",
                    (proc2.stderr or stderr).strip()[:300] or "git clone failed",
                )
        else:
            raise RepoFetchError("clone_failed", stderr[:300] or "git clone failed")

    # Resolve actual commit sha
    head = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    commit_sha = (head.stdout or meta.get("default_branch", "")).strip()[:7] or "unknown"

    # Strip .git to save space and prevent accidental network ops
    shutil.rmtree(dest / ".git", ignore_errors=True)

    size = _dir_size(dest)
    if size > SETTINGS.max_repo_bytes:
        shutil.rmtree(dest, ignore_errors=True)
        raise RepoFetchError("too_large", "The repo's on-disk size exceeds our limit.")

    return ClonedRepo(
        owner=owner,
        name=name,
        url=f"https://github.com/{owner}/{name}",
        ref=meta.get("default_branch", ref),
        commit_sha=commit_sha,
        primary_language=(meta.get("language") or "unknown"),
        stars=int(meta.get("stargazers_count") or 0),
        description=(meta.get("description") or "")[:280],
        path=dest,
        size_bytes=size,
    )


def cleanup(path: Path) -> None:
    try:
        if path and Path(path).exists():
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def sweep_work_root() -> None:
    """On worker startup, sweep orphaned job dirs from crashed workers."""
    root = Path(SETTINGS.work_dir)
    if not root.exists():
        return
    for child in root.iterdir():
        try:
            shutil.rmtree(child, ignore_errors=True)
        except Exception:
            pass
