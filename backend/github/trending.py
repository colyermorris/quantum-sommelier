"""Curated + live-hydrated demo repos for the tasting roulette.

Rather than the GitHub "trending" API (which surfaces AI side-projects with
no cryptography and therefore produces boring A-grades), we hand-pick five
Python / JavaScript repos that are known to contain real crypto code and
will score across the A-F range. Live star counts and blurbs are fetched
from the GitHub API; the curated list is the cache of identity and order.
"""

import time

import httpx

from backend.github.token_pool import POOL
from backend.models import TrendingRepo


_CACHE: "dict[str, tuple[float, list[TrendingRepo]]]" = {}
_CACHE_TTL_S = 30 * 60

# Hand-picked. Each one has real crypto somewhere in the tree and therefore
# produces a meaningful score rather than a degenerate "no findings" A.
_CURATED = [
    # owner, name, fallback_lang, fallback_stars, fallback_blurb
    ("juhoen",         "hybrid-crypto-js",   "JavaScript", 144,
     "RSA + AES hybrid encryption for Node, React Native, and browsers."),
    ("openpgpjs",      "openpgpjs",          "JavaScript", 5900,
     "OpenPGP implementation for JavaScript — signing, encryption, keys."),
    ("digitalbazaar",  "forge",              "JavaScript", 5200,
     "node-forge — TLS, ASN.1, RSA, ECC, hashes, all in pure JS."),
    ("pyca",           "cryptography",       "Python",     6800,
     "Python cryptographic recipes and primitives. The serious one."),
    ("jpadilla",       "pyjwt",              "Python",     5300,
     "JSON Web Token implementation for Python — HS256, RS256, ES256."),
]


def _auth_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "quantum-sommelier/1.0"}
    tok = POOL.next()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


def _hydrate(owner: str, name: str, default_lang: str, default_stars: int, default_blurb: str) -> TrendingRepo:
    """Live-fetch the repo metadata; fall back to the curated defaults on any failure."""
    try:
        resp = httpx.get(
            f"https://api.github.com/repos/{owner}/{name}",
            headers=_auth_headers(),
            timeout=5,
        )
        if resp.status_code == 200:
            d = resp.json()
            return TrendingRepo(
                name=f"{owner}/{name}",
                owner=owner,
                url=d.get("html_url") or f"https://github.com/{owner}/{name}",
                lang=d.get("language") or default_lang,
                stars=int(d.get("stargazers_count") or default_stars),
                blurb=((d.get("description") or default_blurb)).strip()[:110],
            )
    except Exception:
        pass
    return TrendingRepo(
        name=f"{owner}/{name}",
        owner=owner,
        url=f"https://github.com/{owner}/{name}",
        lang=default_lang,
        stars=default_stars,
        blurb=default_blurb,
    )


def rising_repos(limit: int = 5, window_days: int = 30) -> list[TrendingRepo]:
    key = f"curated:{limit}"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _CACHE_TTL_S:
        return hit[1]

    results = [_hydrate(*row) for row in _CURATED[:limit]]
    _CACHE[key] = (now, results)
    return results
