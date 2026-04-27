"""SVG-template → PNG cork renderer.

Uses resvg-py (Rust-backed) for deterministic, no-browser rasterization.
"""

from __future__ import annotations

from pathlib import Path

from backend.models import TastingNote


_TEMPLATE_PATH = Path(__file__).parent / "template.svg"

_GRADE_COLORS = {
    "A": "#556B2F",
    "B": "#6B8E23",
    "C": "#B8860B",
    "D": "#A0522D",
    "F": "#8B2500",
}


def _wrap_quote(text: str, max_len: int = 54) -> tuple[str, str]:
    text = text.strip()
    if len(text) <= max_len:
        return text, ""
    # Break at nearest space before max_len
    cut = text.rfind(" ", 0, max_len)
    if cut == -1:
        cut = max_len
    return text[:cut].strip(), text[cut:].strip()[:max_len]


def _escape_xml(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))


def build_svg(tasting: TastingNote) -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    repo_slug = f"{tasting.repo.owner}/{tasting.repo.name}"
    meta = f"{tasting.repo.ref} @ {tasting.repo.commit_sha} · {tasting.repo.primary_language} · ★ {tasting.repo.stars:,}"
    pq1, pq2 = _wrap_quote(tasting.pull_quote)
    axes = tasting.score.axes
    grade_color = _GRADE_COLORS.get(tasting.score.letter_grade, "#2C2420")
    subs = {
        "{{REPO_SLUG}}": _escape_xml(repo_slug),
        "{{REPO_META}}": _escape_xml(meta),
        "{{GRADE}}": _escape_xml(tasting.score.letter_grade),
        "{{GRADE_BG}}": grade_color,
        "{{PULL_QUOTE_LINE_1}}": _escape_xml("“" + pq1),
        "{{PULL_QUOTE_LINE_2}}": _escape_xml(pq2 + "”" if pq2 else "”"),
        "{{HNDL}}": str(axes.hndl_exposure),
        "{{SIG}}": str(axes.signature_agility),
        "{{HYG}}": str(axes.crypto_hygiene),
        "{{PQA}}": str(axes.pq_adoption_readiness),
        "{{HNDL_W}}": str(int(axes.hndl_exposure * 2)),
        "{{SIG_W}}": str(int(axes.signature_agility * 2)),
        "{{HYG_W}}": str(int(axes.crypto_hygiene * 2)),
        "{{PQA_W}}": str(int(axes.pq_adoption_readiness * 2)),
        "{{RUBRIC_VERSION}}": _escape_xml(tasting.rubric_version),
        "{{SCANNED_AT}}": _escape_xml(tasting.scanned_at),
    }
    out = template
    for k, v in subs.items():
        out = out.replace(k, v)
    return out


_FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts",
]


def render_png(tasting: TastingNote) -> bytes:
    svg = build_svg(tasting)
    try:
        import base64
        import resvg_py  # type: ignore
        # resvg does not load system fonts by default — hand it explicit dirs
        # and family mappings so generic families resolve to our DejaVu set.
        out = resvg_py.svg_to_base64(
            svg_string=svg,
            font_dirs=_FONT_DIRS,
            serif_family="DejaVu Serif",
            sans_serif_family="DejaVu Sans",
            monospace_family="DejaVu Sans Mono",
            font_family="DejaVu Serif",
        )
        if isinstance(out, (list, tuple, bytes, bytearray)):
            if isinstance(out, (list, tuple)):
                out = bytes(out)
            if isinstance(out, (bytes, bytearray)) and out[:8].startswith(b"\x89PNG"):
                return bytes(out)
            if isinstance(out, (bytes, bytearray)):
                out = out.decode("ascii", errors="ignore")
        if isinstance(out, str):
            return base64.b64decode(out)
        return bytes(out)
    except Exception:
        # Fallback: return the SVG bytes. Caller must serve image/svg+xml.
        return svg.encode("utf-8")


def render_svg(tasting: TastingNote) -> bytes:
    return build_svg(tasting).encode("utf-8")
