"""Generate SVG diagrams for image-type slides via Claude Haiku (fast + cheap)."""
from __future__ import annotations
import os, re
from anthropic import Anthropic

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
# Haiku is much faster than Opus for structured markup generation like SVG.
_MODEL = os.getenv("ANTHROPIC_SVG_MODEL", "claude-haiku-4-5-20251001")

_SYSTEM = """You generate clean, educational SVG diagrams for business school lecture slides.

Rules:
- Return ONLY the SVG markup. Start with <svg and end with </svg>. No code fences, no text around it.
- Use viewBox="0 0 800 500".
- Simple shapes: rectangles, circles, arrows, lines, polygons, text.
- Text: 16-22pt, sans-serif, readable.
- Colors: mostly black/dark-gray strokes on white. Use #C00000 red ONLY to emphasize the key relationship.
- Stroke width: 2-3px.
- Arrows: define a <marker> once in <defs> and reference it.
- Clear layout, no overlapping elements.

Common types: two-world counterfactual, causal DAG, flow chart, split-apply-combine, scatter plot sketch, Simpson's paradox reversal."""

def _extract_svg(text):
    text = text.strip()
    fence = re.search(r"```(?:svg|xml|html)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    m = re.search(r"(<svg[\s\S]*?</svg>)", text)
    if not m:
        return None
    svg = m.group(1)
    return svg if len(svg) >= 50 else None

def generate_svg(title, hint):
    if not hint and not title:
        return None
    user_msg = f"Slide title: {title}\nDiagram: {hint}\n\nReturn the SVG markup only."
    try:
        resp = _client.messages.create(
            model=_MODEL,
            max_tokens=3000,
            system=_SYSTEM,
            messages=[{"role":"user","content":user_msg}],
        )
        return _extract_svg(resp.content[0].text)
    except Exception:
        return None
