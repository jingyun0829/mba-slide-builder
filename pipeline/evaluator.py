"""Evaluate a generated outline for pedagogical quality.

Returns scores on multiple dimensions + qualitative feedback. Used for:
  - Single-outline review (one click after generation)
  - Comparing multiple alternative versions side-by-side
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from anthropic import Anthropic

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
# Sonnet for evaluation — needs solid judgment but doesn't need Opus's depth.
_MODEL = os.getenv("ANTHROPIC_EVAL_MODEL", "claude-sonnet-4-6")
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    return text


def evaluate_outline(outline_json: str, style_profile: dict | None = None) -> dict:
    """Return a dict with overall_score, scores{}, strengths[], weaknesses[], verdict."""
    system = (_PROMPT_DIR / "evaluator.md").read_text()

    style_block = ""
    if style_profile:
        try:
            from pipeline.style_analyzer import profile_to_prompt_block
            style_block = "\n\n" + profile_to_prompt_block(style_profile)
        except Exception:
            style_block = ""

    user_msg = f"""Outline to evaluate (JSON):

{outline_json}
{style_block}

Return the evaluation JSON. JSON only — no prose, no fences."""

    resp = _client.messages.create(
        model=_MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = _strip_fences(resp.content[0].text)
    return json.loads(text)
