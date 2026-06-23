#!/usr/bin/env python3
"""
Convert league SVG logos to white/light fills for use on blue gradient headers.
Reads from new big logos/, writes to frontend/public/logos/*_large.svg
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "new big logos"
OUT_DIR = ROOT / "frontend" / "public" / "logos"

# source filename stem -> output *_large.svg basename (without path)
MAPPING: dict[str, str] = {
    "england_english-premier-league.football-logos.cc": "epl_large.svg",
    "spain_la-liga.football-logos.cc": "laliga_large.svg",
    "italy_serie-a.football-logos.cc": "seriea_large.svg",
    "germany_bundesliga.football-logos.cc": "bundesliga_large.svg",
    "france_ligue-1.football-logos.cc": "ligue1_large.svg",
    "russia_russian-premier-league.football-logos.cc": "rpl_large.svg",
    "tournaments_uefa-champions-league.football-logos.cc": "ucl_large.svg",
    "tournaments_uefa-europa-league.football-logos.cc": "uel_large.svg",
    "tournaments_uefa-conference-league.football-logos.cc": "uecl_large.svg",
}

# 3, 4, 6, 8 digit hex
HEX = r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b"
# Capturing group for replace callbacks — longer hex first so fill:#1a1659 is not split as #1a1 + 659
HEX_CAP = r"(#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}(?![0-9a-fA-F])|[0-9a-fA-F]{3}(?![0-9a-fA-F])))"


def _expand_hex_digits(h: str) -> str | None:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        return "".join(c * 2 for c in h)
    if len(h) == 4:
        return "".join(c * 2 for c in h[:3])
    if len(h) == 6:
        return h
    if len(h) == 8:
        return h[:6]
    return None


def _srgb_channel(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (x / 255.0 for x in rgb)
    r, g, b = _srgb_channel(r), _srgb_channel(g), _srgb_channel(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def luminance_to_gray_hex(rgb: tuple[int, int, int]) -> str:
    """Map any fill color to a gray that preserves relative luminance (for light-on-dark UI)."""
    lum = relative_luminance(rgb) + 0.2
    g = round(100 + lum * 500)
    g = max(150, min(248, g))
    return f"#{g:02x}{g:02x}{g:02x}"


def hex_to_rgb(h: str) -> tuple[int, int, int] | None:
    d = _expand_hex_digits(h)
    if not d:
        return None
    return int(d[0:2], 16), int(d[2:4], 16), int(d[4:6], 16)


def strip_noise(content: str) -> str:
    s = content
    s = re.sub(r"<!--\s*Source:.*?-->", "", s, flags=re.DOTALL)
    s = re.sub(r'data-source="[^"]*"', "", s)
    s = re.sub(r'\sdata-name="[^"]*"', "", s)
    s = re.sub(r"<!--\s*source:.*?-->\s*", "", s, flags=re.IGNORECASE)
    return s


def remove_bundesliga_red_background(s: str) -> str:
    """Full red plate behind the mark; whitening it erases all contrast."""
    return re.sub(
        r'<path\s+fill="#d10214"[^>]*>\s*</path>',
        "",
        s,
        flags=re.IGNORECASE,
    )


def replace_fills_with_luminance_grays(s: str) -> str:
    """Replace solid hex fills/strokes and gradient stops with luminance-matched grays."""

    def gray_hex_token(hx: str) -> str:
        rgb = hex_to_rgb(hx)
        if rgb is None:
            return hx
        return luminance_to_gray_hex(rgb)

    def rgba_to_fill_gray(m: re.Match[str]) -> str:
        parts = [p.strip() for p in m.group(1).split(",")]
        if len(parts) < 3:
            return m.group(0)
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        return f"fill:{luminance_to_gray_hex((r, g, b))}"

    def rgba_to_stroke_gray(m: re.Match[str]) -> str:
        parts = [p.strip() for p in m.group(1).split(",")]
        if len(parts) < 3:
            return m.group(0)
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        return f"stroke:{luminance_to_gray_hex((r, g, b))}"

    out = s
    out = re.sub(rf"stop-color:{HEX_CAP}", lambda m: f"stop-color:{gray_hex_token(m.group(1))}", out)
    out = re.sub(rf'stop-color="{HEX_CAP}"', lambda m: f'stop-color="{gray_hex_token(m.group(1))}"', out)
    out = re.sub(rf'fill="{HEX_CAP}"', lambda m: f'fill="{gray_hex_token(m.group(1))}"', out)
    out = re.sub(rf'stroke="{HEX_CAP}"', lambda m: f'stroke="{gray_hex_token(m.group(1))}"', out)
    out = re.sub(rf"fill:{HEX_CAP}", lambda m: f"fill:{gray_hex_token(m.group(1))}", out)
    out = re.sub(rf"stroke:{HEX_CAP}", lambda m: f"stroke:{gray_hex_token(m.group(1))}", out)
    out = re.sub(r"fill:rgba?\(([^)]+)\)", rgba_to_fill_gray, out)
    out = re.sub(r"stroke:rgba?\(([^)]+)\)", rgba_to_stroke_gray, out)
    return out


def replace_paint_servers_with_white(s: str) -> str:
    """After gradients are flattened to grays or unused, url() fills become flat white."""
    s = re.sub(r"fill:url\([^)]+\)", "fill:#ffffff", s)
    s = re.sub(r"stroke:url\([^)]+\)", "stroke:#ffffff", s)
    s = re.sub(r'fill="url\([^)]+\)"', 'fill="#ffffff"', s)
    s = re.sub(r'stroke="url\([^)]+\)"', 'stroke="#ffffff"', s)
    return s


def to_white_svg(content: str) -> str:
    s = content
    # Critical: CSS-style fill:url() must become fill:#ffffff — NOT fill="#ffffff"
    # (nested quotes break style="fill:...").
    s = replace_paint_servers_with_white(s)

    s = re.sub(rf"stop-color:{HEX}", "stop-color:#ffffff", s)
    s = re.sub(rf"fill:{HEX}", "fill:#ffffff", s)
    s = re.sub(rf"stroke:{HEX}", "stroke:#ffffff", s)

    s = re.sub(rf'fill="{HEX}"', 'fill="#ffffff"', s)
    s = re.sub(rf'stroke="{HEX}"', 'stroke="#ffffff"', s)

    s = re.sub(r"fill:rgba?\([^)]+\)", "fill:#ffffff", s)
    s = re.sub(r"stroke:rgba?\([^)]+\)", "stroke:#ffffff", s)

    s = replace_paint_servers_with_white(s)
    return s


def to_gray_toned_svg(content: str) -> str:
    """RPL / Serie A: luminance-matched grays."""
    s = strip_noise(content)
    s = replace_fills_with_luminance_grays(s)
    return s


def strip_seriea_clip_and_unused_defs_for_telegram(s: str) -> str:
    """
    Telegram WKWebView often fails SVG-as-<img> when clip-path=\"url(#id)\" is used.
    Remove clip + unused gradient defs after fills are flattened to solids.
    """
    s = re.sub(r'\s+clip-path="url\(#a\)"', "", s, flags=re.IGNORECASE)
    s = re.sub(r"<clipPath\b[^>]*>.*?</clipPath>", "", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(
        r'<linearGradient\b[^>]*id="b"[^>]*>.*?</linearGradient>',
        "",
        s,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    s = re.sub(
        r'<linearGradient\b[^>]*id="c"[^>]*>.*?</linearGradient>',
        "",
        s,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    s = re.sub(r"<defs\s*>\s*</defs>", "", s)
    return s


def flatten_seriea_gradient_fills_for_telegram(s: str) -> str:
    """
    Telegram Mini App (WKWebView) often fails to paint SVG-as-<img> when paths use
    fill:url(#gradient). Chrome/desktop is fine. Replace with solid mid-grays.
    """
    s = re.sub(r"fill:url\(#b\)", "fill:#888888", s, flags=re.IGNORECASE)
    s = re.sub(r"fill:url\(#c\)", "fill:#888888", s, flags=re.IGNORECASE)
    s = re.sub(r'fill="url\(#paint0[^"]*\)"', 'fill="#888888"', s)
    s = re.sub(r'fill="url\(#paint1[^"]*\)"', 'fill="#888888"', s)
    return s


def process_bundesliga_white(raw: str) -> str:
    """Remove red plate, then same flat white pipeline as other European leagues."""
    s = strip_noise(raw)
    s = remove_bundesliga_red_background(s)
    return ensure_path_fill_white(to_white_svg(s))


def ensure_path_fill_white(s: str) -> str:
    """Paths with only `d=` and no fill inherit black; force white fill."""
    out: list[str] = []
    i = 0
    while True:
        j = s.find("<path", i)
        if j < 0:
            out.append(s[i:])
            break
        out.append(s[i:j])
        k = s.find(">", j)
        if k < 0:
            out.append(s[j:])
            break
        opentag = s[j : k + 1]
        if "fill=" not in opentag and "fill:" not in opentag:
            opentag = opentag.replace("<path ", '<path fill="#ffffff" ', 1)
        out.append(opentag)
        i = k + 1
    return "".join(out)


def process_default(raw: str) -> str:
    s = strip_noise(raw)
    white = ensure_path_fill_white(to_white_svg(s))
    return white


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stem, out_name in MAPPING.items():
        src = SRC_DIR / f"{stem}.svg"
        if not src.exists():
            raise SystemExit(f"Missing source: {src}")
        raw = src.read_text(encoding="utf-8")

        if stem == "russia_russian-premier-league.football-logos.cc":
            white = to_gray_toned_svg(raw)
        elif stem == "italy_serie-a.football-logos.cc":
            white = strip_seriea_clip_and_unused_defs_for_telegram(
                flatten_seriea_gradient_fills_for_telegram(to_gray_toned_svg(raw))
            )
        elif stem == "germany_bundesliga.football-logos.cc":
            white = process_bundesliga_white(raw)
        else:
            white = process_default(raw)

        out_path = OUT_DIR / out_name
        out_path.write_text(white, encoding="utf-8")
        print(f"Wrote {out_path.relative_to(ROOT)}")

    # List icon: seriea_small.svg (same gray treatment; fixes missing stops + url() for <img>)
    seriea_small = OUT_DIR / "seriea_small.svg"
    if seriea_small.exists():
        toned = flatten_seriea_gradient_fills_for_telegram(
            to_gray_toned_svg(seriea_small.read_text(encoding="utf-8"))
        )
        seriea_small.write_text(toned, encoding="utf-8")
        print(f"Wrote {seriea_small.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
