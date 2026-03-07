"""Badge generator for BenchForge scores."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

VALID_STYLES: frozenset[str] = frozenset({"flat", "flat-square", "plastic"})

COLOR_HEX: dict[str, str] = {
    "brightgreen": "#4c1",
    "yellow": "#dfb317",
    "orange": "#fe7d37",
    "red": "#e05d44",
}


@dataclass
class BadgeResult:
    score: int
    label: str
    style: str
    color: str
    svg: str


def _badge_color(score: int) -> str:
    if score >= 80:
        return "brightgreen"
    if score >= 60:
        return "yellow"
    if score >= 40:
        return "orange"
    return "red"


def _measure_width(text: str, *, padding: int) -> int:
    return max(32, len(text) * 7 + padding)


def _layout(label: str, score: int) -> tuple[str, str, int, int, int]:
    value = f"{score}/100"
    safe_label = escape(label)
    safe_value = escape(value)
    label_width = _measure_width(label, padding=18)
    value_width = _measure_width(value, padding=16)
    total_width = label_width + value_width
    return safe_label, safe_value, label_width, value_width, total_width


def _render_flat(score: int, label: str, color: str) -> str:
    safe_label, safe_value, label_width, value_width, total_width = _layout(label, score)
    color_hex = COLOR_HEX[color]
    label_center = label_width / 2
    value_center = label_width + (value_width / 2)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" '
        f'aria-label="{safe_label}: {safe_value}">'
        f'<rect width="{label_width}" height="20" fill="#555"/>'
        f'<rect x="{label_width}" width="{value_width}" height="20" fill="{color_hex}"/>'
        '<text x="50%" y="14" fill="#fff" font-family="Verdana,Geneva,sans-serif" font-size="11" '
        'text-anchor="middle">'
        f'<tspan x="{label_center}" y="14">{safe_label}</tspan>'
        f'<tspan x="{value_center}" y="14">{safe_value}</tspan>'
        '</text>'
        '</svg>'
    )


def _render_flat_square(score: int, label: str, color: str) -> str:
    safe_label, safe_value, label_width, value_width, total_width = _layout(label, score)
    color_hex = COLOR_HEX[color]
    label_center = label_width / 2
    value_center = label_width + (value_width / 2)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" '
        f'aria-label="{safe_label}: {safe_value}">'
        f'<rect width="{label_width}" height="20" fill="#444"/>'
        f'<rect x="{label_width}" width="{value_width}" height="20" fill="{color_hex}"/>'
        f'<path d="M{label_width} 0h1v20h-1z" fill="#000" fill-opacity=".15"/>'
        f'<text x="{label_center}" y="14" fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" '
        'font-size="11" text-anchor="middle">'
        f'{safe_label}</text>'
        f'<text x="{value_center}" y="14" fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" '
        'font-size="11" text-anchor="middle">'
        f'{safe_value}</text>'
        '</svg>'
    )


def _render_plastic(score: int, label: str, color: str) -> str:
    safe_label, safe_value, label_width, value_width, total_width = _layout(label, score)
    color_hex = COLOR_HEX[color]
    label_center = label_width / 2
    value_center = label_width + (value_width / 2)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" '
        f'aria-label="{safe_label}: {safe_value}">'
        '<defs>'
        '<linearGradient id="smooth" x2="0" y2="100%">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".7"/>'
        '<stop offset=".1" stop-color="#aaa" stop-opacity=".1"/>'
        '<stop offset=".9" stop-color="#000" stop-opacity=".3"/>'
        '<stop offset="1" stop-color="#000" stop-opacity=".5"/>'
        '</linearGradient>'
        '</defs>'
        f'<rect rx="4" width="{total_width}" height="20" fill="#555"/>'
        f'<rect rx="4" width="{label_width}" height="20" fill="#555"/>'
        f'<rect rx="4" x="{label_width}" width="{value_width}" height="20" fill="{color_hex}"/>'
        f'<path fill="{color_hex}" d="M{label_width} 0h{value_width}v20H{label_width}z"/>'
        f'<rect rx="4" width="{total_width}" height="20" fill="url(#smooth)"/>'
        f'<text x="{label_center}" y="14" fill="#fff" font-family="Verdana,Geneva,sans-serif" '
        'font-size="11" text-anchor="middle">'
        f'{safe_label}</text>'
        f'<text x="{value_center}" y="14" fill="#fff" font-family="Verdana,Geneva,sans-serif" '
        'font-size="11" text-anchor="middle">'
        f'{safe_value}</text>'
        '</svg>'
    )


def generate_badge(score: int, label: str = "BenchForge", style: str = "flat") -> BadgeResult:
    normalized_score = max(0, min(100, int(score)))
    normalized_label = label.strip() or "BenchForge"
    normalized_style = style.strip().lower()

    if normalized_style not in VALID_STYLES:
        raise ValueError(
            f"Unsupported badge style: {style}. Expected one of: {', '.join(sorted(VALID_STYLES))}."
        )

    color = _badge_color(normalized_score)

    if normalized_style == "flat":
        svg = _render_flat(normalized_score, normalized_label, color)
    elif normalized_style == "flat-square":
        svg = _render_flat_square(normalized_score, normalized_label, color)
    else:
        svg = _render_plastic(normalized_score, normalized_label, color)

    return BadgeResult(
        score=normalized_score,
        label=normalized_label,
        style=normalized_style,
        color=color,
        svg=svg,
    )
