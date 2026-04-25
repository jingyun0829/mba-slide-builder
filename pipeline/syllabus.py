"""Course description + weeks → structured syllabus JSON."""
from __future__ import annotations

import json
import os
from pathlib import Path

from anthropic import Anthropic

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_system(module: str) -> str:
    base = (_PROMPT_DIR / "system_base.md").read_text()
    mod_file = _PROMPT_DIR / f"{module}.md"
    module_block = mod_file.read_text() if mod_file.exists() else ""
    schema = (_PROMPT_DIR / "syllabus_schema.md").read_text()
    return f"{base}\n\n{module_block}\n\n{schema}"


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    return text


def generate_syllabus(
    course_description: str,
    total_weeks: int,
    course_level: str,
    module_area: str,
    extra_notes: str = "",
    recommended_textbook: str = "",
) -> str:
    system = _load_system(module_area)

    textbook_block = ""
    if recommended_textbook and recommended_textbook.strip():
        textbook_block = (
            f"\nRecommended textbook(s) — anchor weekly readings to this when sensible:\n"
            f"{recommended_textbook.strip()}\n"
            "Set the top-level `primary_textbook` field to this string. "
            "In each week's `suggested_readings`, lead with the relevant chapter from this textbook "
            "(e.g., 'Anderson Ch. 3.1-3.4: Numerical Measures'), then add 1 supplemental "
            "current article (HBR, FT, or recent industry case)."
        )

    user_msg = f"""Course description:
{course_description}

Target total weeks: {total_weeks}
Course level: {course_level}
Primary module area: {module_area}
{textbook_block}

Additional notes from instructor:
{extra_notes or "(none)"}

Return the syllabus JSON matching the schema. JSON only — no prose, no fences."""
    resp = _client.messages.create(
        model=_MODEL,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = _strip_fences(resp.content[0].text)
    json.loads(text)
    return text


def save_syllabus(syllabus_json: str, path: str = "syllabi/current.json") -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(syllabus_json)
    return path


def load_syllabus(path: str = "syllabi/current.json") -> str | None:
    p = Path(path)
    return p.read_text() if p.exists() else None
