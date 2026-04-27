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
            f"\nRecommended textbook (provided by instructor — this IS real, use as-is):\n"
            f"{recommended_textbook.strip()}\n"
            "Set the top-level `primary_textbook` field to EXACTLY this citation. "
            "You may still leave `textbook_recommendations` as an empty list, "
            "OR add 1-2 real alternative textbooks for completeness. "
            "Do NOT generate per-week articles, case names, or HBR/FT references."
        )
    else:
        textbook_block = (
            "\nNo textbook was specified by the instructor. Leave `primary_textbook` "
            "as an empty string. In `textbook_recommendations`, provide 2-3 REAL, "
            "widely-used textbooks commonly assigned in this course area at this level — "
            "the instructor will pick one. Use exact citation format. "
            "Do NOT invent fake textbooks. Do NOT generate per-week articles."
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
