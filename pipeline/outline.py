"""Stage 3 — topic + objectives (+ style profile + controls) → narrative slide list."""
from __future__ import annotations
import json, os
from pathlib import Path
from anthropic import Anthropic

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
# Sonnet is the sweet spot for structured JSON: 5x cheaper than Opus,
# quality is still excellent for pedagogical outlines.
_MODEL = os.getenv("ANTHROPIC_OUTLINE_MODEL", "claude-sonnet-4-6")
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

def _load_system(module, style_block=""):
    base = (_PROMPT_DIR / "system_base.md").read_text()
    mod_file = _PROMPT_DIR / f"{module}.md"
    module_block = mod_file.read_text() if mod_file.exists() else ""
    schema = (_PROMPT_DIR / "outline_schema.md").read_text()
    parts = [base, module_block]
    if style_block:
        parts.append(style_block)
    parts.append(schema)
    return "\n\n".join(p for p in parts if p)

def _strip_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    return text

VERSION_ANGLES = {
    "Style-best fit": "Match the instructor's teaching style profile as tightly as possible — same line density, question-title rate, image-slide rate, opening/closing pattern. Optimize for the highest style_match evaluation score. Don't over-emphasize cases or code beyond their normal pattern.",
    "Case-heavy": "Maximize real-world case content. Aim for 30%+ more example-type slides than baseline. Anchor every key concept to a specific named real company (last 24 months). Frameworks are lenses on those cases, never standalone. Include 1-2 mini-case discussion blocks.",
    "Code-heavy": "Maximize hands-on computation. Aim for 40%+ more code-type slides than baseline (force include_code=true). Real runnable Python/R/SQL with step-by-step explanations. Pair every methodological concept with a code example or in-class exercise where it makes sense.",
}


AUDIENCE_LEVELS = {
    "intro": (
        "🌱 Intro (undergrad / survey)",
        "AUDIENCE: INTRODUCTORY level (undergraduates, non-majors, or survey courses). "
        "Use a familiar consumer-brand analogy for EVERY technical concept (Spotify, Netflix, Amazon, TikTok). "
        "Shorter, more visual slides — fewer lines per slide than the style-profile baseline. "
        "Define every jargon term in plain language the first time it appears. "
        "AVOID math beyond basic arithmetic; replace formulas with intuition. "
        "Include MORE discussion-question slides — students need active participation to stay engaged. "
        "If code is included, keep snippets very short (3-6 lines) with extensive comments."
    ),
    "standard": (
        "📊 Standard (MBA / professional)",
        "AUDIENCE: STANDARD MBA / professional level. "
        "Balance intuitive explanations with technical depth. "
        "Frameworks introduced clearly + one limitation/critique each. "
        "Real-world cases anchor every major concept. Code at standard depth (8-15 lines)."
    ),
    "advanced": (
        "🎓 Advanced (grad / exec ed)",
        "AUDIENCE: ADVANCED graduate or executive education level. "
        "Assume technical fluency — DO NOT define basic terms. "
        "Reference primary research papers when relevant (real authors + year, e.g., 'Pearl 2009', 'Athey & Imbens 2017'). "
        "Include mathematical formulations where they aid clarity (use clean ASCII or LaTeX-style notation in lines). "
        "Heavier framework critique — limits, edge cases, when each model breaks. "
        "Less hand-holding; students can fill conceptual gaps. "
        "If code is included, real production-grade snippets (12-20 lines) with assumptions stated."
    ),
}


def generate_outline(topic, objectives, rough_notes, module, duration_minutes,
                     recent_examples=None, style_profile=None,
                     target_slides=None, include_code=False, include_homework=False,
                     include_activity=False, version_angle: str | None = None,
                     prior_memory: list | None = None, include_recap: bool = True,
                     audience_level: str = "standard",
                     primary_textbook: str = ""):
    style_block = ""
    if style_profile:
        from pipeline.style_analyzer import profile_to_prompt_block
        style_block = profile_to_prompt_block(style_profile)

    memory_block = ""
    if prior_memory:
        from pipeline.course_memory import memory_to_prompt_block
        memory_block = memory_to_prompt_block(prior_memory, include_recap=include_recap)

    # Anchor source citations to the syllabus's verified primary textbook so
    # Claude doesn't have to guess / hallucinate. If empty, sourcing prompt
    # tells Claude to fall back to foundational papers + named frameworks only.
    textbook_block = ""
    if primary_textbook and primary_textbook.strip():
        textbook_block = (
            f"\nPRIMARY_TEXTBOOK (use this as the anchor for slide-level `source` "
            f"citations whenever the slide content maps to a chapter):\n"
            f"{primary_textbook.strip()}\n"
            f"Format chapter citations as: '<Author Last> Ch. <number>: <topic>'. "
            f"Example: 'Anderson Ch. 4.6: Bayes' Theorem'. "
            f"For topics NOT in this textbook, fall back to foundational papers / "
            f"named frameworks per the SOURCING rules. NEVER fabricate a chapter."
        )
    else:
        textbook_block = (
            "\nNo primary textbook specified. For slide-level `source` field, ONLY "
            "cite foundational papers (e.g. 'Akerlof (1970)') or named frameworks "
            "('Porter's 5 Forces') that you are >95% certain are real. "
            "When unsure, use empty string."
        )

    # Combine style + memory + textbook into the system prompt's extra section
    system_extras = "\n\n".join(b for b in [style_block, memory_block, textbook_block] if b)
    system = _load_system(module, system_extras)

    examples_block = ""
    if recent_examples:
        examples_block = "Recent real-world examples to consider:\n" + "\n".join(
            f"- {e['title']} ({e.get('date','recent')}): {e.get('snippet','')[:280]}"
            for e in recent_examples)

    directives = []
    if target_slides:
        directives.append(f"Target slide count: produce around {target_slides} entries in the 'slides' array. Hit this by extending the narrative (more short slides), NOT by cramming more lines per slide.")
    if include_code:
        directives.append("include_code = TRUE. Use type='code' slides where useful. Real, runnable code, 8-15 lines.")
    else:
        directives.append("include_code = FALSE. No type='code' slides.")
    if include_homework:
        directives.append("include_homework = TRUE. Fill top-level homework{} with problem + real dataset link + deliverables. Do NOT put homework in slides array.")
    else:
        directives.append("include_homework = FALSE. Omit homework field.")
    if include_activity:
        directives.append(
            "include_activity = TRUE. Add a top-level 'activity' field for a 10-minute in-class warm-up. "
            "Pick type='excel_simulation' for data-manipulation topics (stats, A/B testing, Simpson's paradox, forecasting, pricing). "
            "Pick type='web_link' for visualization/exploration topics (recommend Seeing Theory, Gapminder, Google Trends, FRED, etc.). "
            "If excel_simulation: use ONLY basic formulas (AVERAGEIF, SUMIF, COUNTIF, IF, VLOOKUP, basic math) — NO dynamic arrays or 365-only functions. "
            "Only ONE activity per deck."
        )
    else:
        directives.append("include_activity = FALSE. Omit activity field.")
    if version_angle:
        directives.append(f"VERSION ANGLE — bias the outline toward this approach: {version_angle}")
    # Audience-level directive (always include — defaults to standard)
    if audience_level in AUDIENCE_LEVELS:
        _label, _level_directive = AUDIENCE_LEVELS[audience_level]
        directives.append(_level_directive)
    directives_block = "Directives for this outline:\n" + "\n".join(f"- {d}" for d in directives)

    user_msg = f"""Session topic: {topic}
Duration: {duration_minutes} minutes
Module: {module}

Learning objectives:
{chr(10).join(f"- {o}" for o in objectives)}

Rough notes:
{rough_notes or "(none)"}

{examples_block}

{directives_block}

Build the deck as a narrative. One idea per slide. Question-form titles where natural.
Return a JSON outline matching the schema. JSON only — no prose, no fences."""

    resp = _client.messages.create(model=_MODEL, max_tokens=12000, system=system,
                                    messages=[{"role":"user","content":user_msg}])
    text = _strip_fences(resp.content[0].text)
    parsed = json.loads(text)
    # Stamp the primary_textbook into the outline so build_html can use it
    # for the aggregated References slide. Doesn't override if Claude already
    # included one (it shouldn't — we only ask for slide-level sources).
    if primary_textbook and primary_textbook.strip() and not parsed.get("primary_textbook"):
        parsed["primary_textbook"] = primary_textbook.strip()
        text = json.dumps(parsed, indent=2)
    return text
