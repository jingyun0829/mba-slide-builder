"""Extract a teaching-style profile from the instructor's past .pptx decks.

Reads EVERY shape's text frame — not just placeholders — so instructors who
compose slides with text boxes + images get their style captured accurately.
"""
from __future__ import annotations
import json, os, statistics
from pathlib import Path
from anthropic import Anthropic
from pptx import Presentation

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
_PICTURE_SHAPE_TYPE = 13


def _extract_deck(pptx_path):
    prs = Presentation(pptx_path)
    slides = []
    for slide in prs.slides:
        lines = []
        images = 0
        for shape in slide.shapes:
            if shape.shape_type == _PICTURE_SHAPE_TYPE:
                images += 1
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = para.text.strip()
                    if t:
                        lines.append(t)
        slides.append({"lines": lines, "images": images})
    return {"name": Path(pptx_path).name, "slides": slides}


def _compute_quant(decks):
    all_slides = [s for d in decks for s in d["slides"]]
    if not all_slides:
        return {"decks_analyzed": len(decks), "total_slides_analyzed": 0}
    slide_counts = [len(d["slides"]) for d in decks]
    lines_per_slide = [len(s["lines"]) for s in all_slides]
    titles = [s["lines"][0] for s in all_slides if s["lines"]]
    body_lines = [l for s in all_slides for l in s["lines"][1:]]
    title_words = [len(t.split()) for t in titles]
    body_words = [len(l.split()) for l in body_lines]
    question_titles = sum(1 for t in titles if "?" in t)
    short_titles = sum(1 for t in titles if len(t.split()) <= 5)
    slides_with_images = sum(1 for s in all_slides if s["images"] > 0)

    def _avg(xs):
        return round(statistics.mean(xs), 2) if xs else 0
    def _med(xs):
        return round(statistics.median(xs), 1) if xs else 0

    return {
        "decks_analyzed": len(decks),
        "total_slides_analyzed": sum(slide_counts),
        "avg_slides_per_lecture": _avg(slide_counts),
        "avg_lines_per_slide": _avg(lines_per_slide),
        "median_lines_per_slide": _med(lines_per_slide),
        "avg_words_per_title": _avg(title_words),
        "avg_words_per_body_line": _avg(body_words),
        "question_title_ratio": round(question_titles/len(titles),2) if titles else 0,
        "short_title_ratio": round(short_titles/len(titles),2) if titles else 0,
        "image_slide_ratio": round(slides_with_images/len(all_slides),2),
    }


def _build_style_sample(decks, max_slides=80):
    chunks = []
    emitted = 0
    for d_idx, d in enumerate(decks, 1):
        chunks.append(f"=== Deck {d_idx}: {d['name']} ({len(d['slides'])} slides) ===")
        for s_idx, s in enumerate(d["slides"], 1):
            if emitted >= max_slides:
                chunks.append(f"(...and {len(d['slides']) - s_idx + 1} more slides)")
                break
            img_tag = f" [{s['images']} image{'s' if s['images']>1 else ''}]" if s['images'] else ""
            chunks.append(f"Slide {s_idx}{img_tag}")
            for line in s["lines"]:
                chunks.append(f"  {line}")
            chunks.append("")
            emitted += 1
        if emitted >= max_slides:
            break
    return "\n".join(chunks)


def _qualitative_from_claude(decks, quant):
    system = (_PROMPT_DIR / "style_extraction.md").read_text()
    sample = _build_style_sample(decks)
    user_msg = f"""Quantitative stats from these decks:
{json.dumps(quant, indent=2)}

Raw slide content (every shape's text, in reading order, across the sample):
{sample}

Return the style-profile JSON matching the schema. JSON only."""
    resp = _client.messages.create(model=_MODEL, max_tokens=2500, system=system,
                                    messages=[{"role":"user","content":user_msg}])
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    return json.loads(text)


def extract_style_profile(pptx_paths):
    if not pptx_paths:
        raise ValueError("No .pptx files provided.")
    decks = [_extract_deck(p) for p in pptx_paths]
    quant = _compute_quant(decks)
    qual = _qualitative_from_claude(decks, quant)
    return {"quantitative": quant, "qualitative": qual, "sources": [Path(p).name for p in pptx_paths]}


def save_style_profile(profile, path="style_profiles/current.json"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(profile, indent=2))
    return path


def load_style_profile(path="style_profiles/current.json"):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else None


def compute_dimensions(profile: dict) -> dict[str, int]:
    """Reduce the noisy raw profile to 6 normalized 0-100 dimension scores.

    These are what get plotted on the radar chart in Stage 2 — much easier
    to read at a glance than the raw quantitative + qualitative fields.
    """
    if not profile:
        return {}
    q = profile.get("quantitative", {}) or {}
    qual = profile.get("qualitative", {}) or {}

    def _clamp(x: float) -> int:
        return max(0, min(100, int(round(x))))

    # ----- Derived from quantitative numbers -----
    awpl = float(q.get("avg_words_per_body_line") or 12)
    # 5 words = 100, 18 words = 0 (linear)
    concise = _clamp(100 - (awpl - 5) * (100 / 13))

    qtr = float(q.get("question_title_ratio") or 0)
    questions = _clamp(qtr * 100 * 1.4)  # boost: 70% question titles → 100

    isr = float(q.get("image_slide_ratio") or 0)
    visual = _clamp(isr * 100 * 1.5)  # boost: 67% image slides → 100

    aspl = float(q.get("avg_slides_per_lecture") or 25)
    # 50+ slides/lecture = rapid pacing; 15 = methodical
    pacing = _clamp((aspl / 50) * 100)

    # ----- Derived from qualitative text (keyword scoring) -----
    tone = (qual.get("tone") or "").lower()
    conv_keywords = ("conversational", "informal", "casual", " we ", "you ", "friendly")
    conversational = _clamp(85 if any(k in tone for k in conv_keywords) else 45)

    ex_density = (qual.get("example_density") or "").lower()
    if "high" in ex_density:
        real_cases = 90
    elif "medium" in ex_density:
        real_cases = 60
    elif "low" in ex_density:
        real_cases = 25
    else:
        real_cases = 50

    return {
        "Concise lines":     concise,
        "Question-driven":   questions,
        "Visual-rich":       visual,
        "Rapid pacing":      pacing,
        "Conversational":    conversational,
        "Real-case heavy":   real_cases,
    }


def profile_to_prompt_block(profile):
    if not profile:
        return ""
    q = profile.get("quantitative", {}) or {}
    qual = profile.get("qualitative", {}) or {}
    lines = [
        "INSTRUCTOR TEACHING STYLE — match this as closely as possible.",
        "",
        "Quantitative targets (match these averages tightly):",
        f"- Slides per lecture: {q.get('avg_slides_per_lecture','?')} (within plus/minus 15%)",
        f"- Lines per slide: {q.get('avg_lines_per_slide','?')} avg, {q.get('median_lines_per_slide','?')} median",
        f"- Words per title: {q.get('avg_words_per_title','?')} avg",
        f"- Words per body line: {q.get('avg_words_per_body_line','?')} avg",
        f"- Question-form titles: {int(q.get('question_title_ratio',0)*100)}% — use question titles at this rate",
        f"- Short titles (<=5 words): {int(q.get('short_title_ratio',0)*100)}%",
        f"- Image/diagram slides: {int(q.get('image_slide_ratio',0)*100)}% — insert image-type slides at this rate",
        "",
        "Qualitative style:",
    ]
    for key, val in qual.items():
        if isinstance(val, list):
            val = "; ".join(str(v) for v in val)
        lines.append(f"- {key}: {val}")
    lines.append("")
    lines.append("Critical: build the deck as a narrative of many short slides, NOT a few dense slides. Mirror the titling voice, line length, and image rhythm. Do NOT produce mechanical labels like 'Topic — key points'.")
    return "\n".join(lines)
