"""Stage 4 — slide-centric outline JSON → self-contained HTML deck.

SVG generation runs in parallel (ThreadPoolExecutor, up to 8 concurrent
Haiku calls) so build time scales by the slowest single SVG, not the
number of image slides.
"""
from __future__ import annotations
import json, html as html_mod
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

def _esc(s): return html_mod.escape(str(s or ""), quote=True)

# Slide-type emoji icons for title prefix (Stage 4 fancy upgrade)
TYPE_ICONS = {
    "concept":    "💡",
    "question":   "❓",
    "example":    "🏢",
    "image":      "🖼️",
    "code":       "💻",
    "exercise":   "⚙️",
    "discussion": "💬",
    "summary":    "✨",
}

def _icon_html(slide_type: str) -> str:
    icon = TYPE_ICONS.get((slide_type or "").lower())
    return f'<span class="type-icon">{icon}</span>' if icon else ''

def _line_to_html(line):
    if isinstance(line, str):
        return f'<p>{_esc(line)}</p>'
    if isinstance(line, dict):
        classes = []
        if line.get("bold"): classes.append("bold")
        if line.get("small"): classes.append("small")
        if line.get("red"): classes.append("red")
        cls = f' class="{" ".join(classes)}"' if classes else ""
        return f'<p{cls}>{_esc(line.get("text",""))}</p>'
    return f'<p>{_esc(str(line))}</p>'

def _render_title_slide(session_title, duration):
    return f'''<section class="slide title-slide" data-type="title">
  <h1>{_esc(session_title)}</h1>
  <div class="subtitle">{_esc(duration)} min</div>
</section>'''

def _render_content_slide(slide):
    title = slide.get("title","")
    lines = slide.get("lines", []) or []
    kt = slide.get("key_takeaway","")
    body = "\n    ".join(_line_to_html(l) for l in lines if l)
    stype = (slide.get("type") or "concept").lower()
    icon = _icon_html(stype)
    takeaway = (
        f'<div class="key-takeaway"><div class="key-takeaway-text">{_esc(kt)}</div></div>'
        if kt and kt.strip() else ""
    )
    return f'''<section class="slide content-slide" data-type="{_esc(stype)}">
  <h2 class="slide-title">{icon}<span>{_esc(title)}</span></h2>
  <div class="slide-title-accent"></div>
  <div class="slide-body">
    {body}
  </div>
  {takeaway}
</section>'''

def _render_code_step_slide(step_title, code, language, explanation="",
                              group_id="", step_idx=1):
    expl_html = ""
    if explanation and explanation.strip():
        expl_html = f'<div class="code-explanation">{_esc(explanation.strip())}</div>'
    runnable = language.lower() == "python"
    run_html = ""
    if runnable:
        run_html = (
            '<div class="run-toolbar">'
            '<button class="run-btn" type="button" onclick="runCode(this)">▶ Run in browser</button>'
            '<span class="run-status"></span>'
            '</div>'
            '<div class="output" hidden></div>'
        )
    # data-code-group + data-step-idx let the JS auto-run prior steps in the same group
    grp_attr = f' data-code-group="{_esc(group_id)}" data-step-idx="{step_idx}"' if group_id else ""
    return f'''<section class="slide code-slide" data-type="code"{grp_attr}>
  <h2 class="slide-title">{_icon_html("code")}<span>{_esc(step_title)} <span class="lang-tag">({_esc(language)})</span></span></h2>
  <div class="slide-title-accent"></div>
  <pre><code class="language-{_esc(language)}">{_esc(code)}</code></pre>
  {run_html}
  {expl_html}
</section>'''

def _render_code_slides(slide):
    co = slide.get("code") or {}
    lang = co.get("language","python")
    steps = co.get("steps") or []
    out = []
    if not steps:
        raw = co.get("content","")
        if raw:
            out.append(_render_code_step_slide(slide.get("title","Code"), raw, lang,
                                               explanation=co.get("caption","")))
        return out
    # Generate a stable group id so all steps in this code block share it.
    # Stable across calls: hash of the first step's description + first 40 chars of code.
    import hashlib
    seed = ((steps[0] or {}).get("description","") + (steps[0] or {}).get("code","")[:40])
    group_id = "cg" + hashlib.md5(seed.encode()).hexdigest()[:10]
    for idx, s in enumerate(steps, 1):
        raw_desc = ((s or {}).get("description") or "").strip().rstrip("—-: ").strip()
        desc = raw_desc if raw_desc else f"Step {idx}"
        if not desc.lower().startswith("step"):
            desc = f"Step {idx}: {desc}"
        code_text = ((s or {}).get("code") or "").strip()
        if not code_text:
            continue
        explanation = ((s or {}).get("explanation") or "").strip()
        out.append(_render_code_step_slide(desc, code_text, lang,
                                            explanation=explanation,
                                            group_id=group_id, step_idx=idx))
    return out

def _hint_to_text_lines(hint: str) -> list:
    """Convert an image_hint (written for AI) into student-readable bullets.

    Strips wrapper junk like 'Diagram:', '[ ... ]'; recognizes common patterns
    like 'Top-left: X. Top-right: Y' and 'A → B → C'; falls back to sentence
    splits when no structure is detected.
    """
    import re
    h = (hint or "").strip()
    if not h:
        return ["(No content available for this slide.)"]

    # Remove '[' and ']' wrappers
    h = re.sub(r'^\[\s*', '', h)
    h = re.sub(r'\s*\]$', '', h)
    # Strip leading "Diagram:", "Image:", "Visual:" etc.
    h = re.sub(
        r'^(?:Diagram|Image|Visual|Illustration|Chart|Graph|Picture|Figure|Infographic)\s*[:.\-—–]\s*',
        '', h, flags=re.IGNORECASE,
    )
    h = h.strip()

    # Pattern 1: pipeline / arrow flow → keep on one bold line
    if h.count('→') >= 2 or h.count('->') >= 2:
        m = re.search(r'([\w\s&,]+(?:\s*(?:→|->)\s*[\w\s&,]+){2,})', h)
        if m:
            chain = m.group(1).strip()
            rest = (h[:m.start()] + h[m.end():]).strip(' .,;:')
            # Remove leftover "Left-to-right pipeline diagram", "Flowchart", etc.
            rest = re.sub(
                r'(?:Left-to-right|Right-to-left|Top-down|Vertical|Horizontal)?\s*'
                r'(?:pipeline|flow(?:chart)?|process|sequence|workflow)\s*'
                r'(?:diagram|chart)?\s*[:.\-—–]?\s*',
                '', rest, flags=re.IGNORECASE,
            ).strip(' .,;:')
            lines = [{"text": f"📊 Flow: {chain}", "bold": True}]
            if rest:
                for s in re.split(r'(?<=[.!?])\s+', rest):
                    s = s.strip(' .,;:')
                    if s and len(s) > 3:
                        lines.append(s)
            return lines

    # Pattern 2: positional / grid layout (Top-left:, Top-right:, etc.)
    pos_pattern = re.compile(
        r'(Top[-\s]?left|Top[-\s]?right|Bottom[-\s]?left|Bottom[-\s]?right|Center|Middle|Left|Right|Top|Bottom)\s*[:\-—–]\s*([^.]+?)(?=(?:\s+(?:Top|Bottom|Center|Middle|Left|Right))|$)',
        re.IGNORECASE,
    )
    matches = pos_pattern.findall(h)
    if len(matches) >= 2:
        return [
            {"text": f"{label.strip().title()}: {text.strip(' .')}", "bold": False}
            for label, text in matches
        ]

    # Pattern 3: generic sentence split
    sentences = re.split(r'(?<=[.!?])\s+', h)
    sentences = [s.strip(' .') for s in sentences if s.strip() and len(s.strip()) > 5]
    if sentences:
        return sentences

    # Last resort
    return [h]


def _render_image_slide(slide, precomputed=None):
    """precomputed: either an SVG string starting with '<svg', or a dict
    {"url": ..., "description": ...} from web image search, or None.

    When precomputed is None (no image — either skipped, dropped by user, or
    failed to fetch), the slide is re-rendered as a TEXT-ONLY concept slide
    using the cleaned-up image_hint as content. Much friendlier than dumping
    raw '[Diagram: ...]' placeholder text at students."""
    title = slide.get("title","")
    hint = slide.get("image_hint","")

    if isinstance(precomputed, str) and precomputed.lstrip().startswith("<svg"):
        body = f'<div class="svg-wrapper">{precomputed}</div>'
    elif isinstance(precomputed, dict) and precomputed.get("url"):
        url = precomputed["url"]
        caption = precomputed.get("description") or hint
        # JS onerror: if the image fails to load (404, CORS, hotlink-block),
        # hide it and re-render as a text slide via DOM rewrite.
        fallback_lines = _hint_to_text_lines(hint)
        # Build a simple inline HTML representation for the JS fallback
        fallback_html_parts = []
        for ln in fallback_lines:
            if isinstance(ln, dict):
                fallback_html_parts.append(f'<p><strong>{_esc(ln.get("text",""))}</strong></p>')
            else:
                fallback_html_parts.append(f'<p>{_esc(str(ln))}</p>')
        fallback_html = "".join(fallback_html_parts).replace('"', '&quot;')
        fallback_js = (
            "this.style.display='none';"
            "this.parentElement.innerHTML="
            f"'<div class=&quot;slide-body&quot;>{fallback_html}</div>';"
        )
        body = (
            f'<div class="img-wrapper">'
            f'<img src="{_esc(url)}" alt="" loading="lazy" '
            f'onerror="{fallback_js}"/>'
            f'<div class="img-caption">{_esc(caption)[:140]}</div>'
            f'</div>'
        )
    else:
        # No image at all — render the slide as a clean text concept slide
        # using the cleaned-up image_hint. This is what the user sees when
        # they uncheck an image in the preview workflow, or when search/fetch
        # returned nothing.
        return _render_content_slide({
            "type": "concept",
            "title": title,
            "lines": _hint_to_text_lines(hint),
        })

    return f'''<section class="slide image-slide" data-type="image">
  <h2 class="slide-title">{_icon_html("image")}<span>{_esc(title)}</span></h2>
  <div class="slide-title-accent"></div>
  {body}
</section>'''


def _parallel_fetch_images(image_slides, mode="search"):
    """Given [(idx, slide), ...] and mode, return {idx: result_or_None}.

    mode:
      - 'search' : web image URL via Tavily (returns dict)
      - 'svg'    : AI-generated SVG via Haiku (returns string)
      - 'skip'   : no fetch (returns {})
    Up to 8 calls in parallel.
    """
    if not image_slides or mode == "skip":
        return {}

    if mode == "search":
        try:
            from pipeline.image_search import search_image
            def _fetch(slide):
                # Use the slide title as primary query — it's short and topical.
                # The image_hint is usually a long description meant for AI drawing,
                # not for keyword search, so it would garble the query.
                title = (slide.get("title") or "").strip()
                if not title:
                    # Fall back to first few words of image_hint
                    title = " ".join((slide.get("image_hint") or "").split()[:6])
                return search_image(title)
        except Exception:
            return {}
    else:  # 'svg'
        try:
            from pipeline.svg_generator import generate_svg
            def _fetch(slide):
                return generate_svg(slide.get("title",""), slide.get("image_hint",""))
        except Exception:
            return {}

    results = {}
    max_workers = min(8, len(image_slides))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch, s): idx for idx, s in image_slides}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results[idx] = fut.result()
            except Exception:
                results[idx] = None
    return results


# Back-compat alias (older code may reference this name)
def _parallel_generate_svgs(image_slides):
    return _parallel_fetch_images(image_slides, mode="svg")


def fetch_image_previews(outline_json, image_mode="search"):
    """Fetch image candidates for an outline WITHOUT building the deck.
    Returns: {slide_idx: image_data, ...} suitable for passing back to
    build_html(precomputed_images=...) after the user picks which to keep.
    """
    outline = json.loads(outline_json) if isinstance(outline_json, str) else outline_json
    slides_list = outline.get("slides") or []
    image_slides = [(i, s) for i, s in enumerate(slides_list)
                    if (s.get("type") or "").lower().strip() == "image"]
    return _parallel_fetch_images(image_slides, mode=image_mode)

def _split_steps(text_or_list):
    """Turn '1. Do X. 2. Do Y. 3. Do Z' (or any list-shaped string) into a list
    of clean step strings. If already a list, just clean each item.

    Detects:
      - Numbered: '1.', '2.', '1)', '2)', etc.
      - Bulleted: '•', '-', '*', '–'
    Falls back to a single-item list if no markers are found.
    """
    import re
    if isinstance(text_or_list, list):
        # Already a list — just strip and drop empties
        return [str(s).strip().lstrip("•·-*– ").strip() for s in text_or_list if s and str(s).strip()]
    s = str(text_or_list or "").strip()
    if not s:
        return []
    # Try numbered pattern: split on " 1. " " 2. " etc. (but keep number from start)
    # Pattern: number followed by . or ) followed by space
    parts = re.split(r'(?:^|\s+)(\d+[\.\)])\s+', s)
    # re.split with capturing group returns: [pre, '1.', 'text1', '2.', 'text2', ...]
    if len(parts) >= 3:
        steps = []
        # parts[0] is leading text (usually empty); pairs after that are (number, text)
        if parts[0].strip():
            steps.append(parts[0].strip())
        for i in range(1, len(parts) - 1, 2):
            num = parts[i]
            text = parts[i + 1].strip().rstrip('.').strip() + '.'
            steps.append(f"{num} {text}")
        if len(steps) >= 2:
            return steps
    # Try bullet pattern
    if re.search(r'(?:^|\s)[•·\-*–]\s+', s):
        bullets = re.split(r'(?:^|\s)[•·\-*–]\s+', s)
        bullets = [b.strip().rstrip('.').strip() for b in bullets if b.strip()]
        if len(bullets) >= 2:
            return bullets
    # No structure detected — return as single item
    return [s]


def _render_activity_slides(activity):
    """Render 2-3 slides for the in-class warm-up activity."""
    if not activity:
        return []
    title = activity.get("title", "Warm-up Activity")
    atype = activity.get("type", "web_link")
    duration = activity.get("duration_minutes", 10)

    out = [f'''<section class="slide section-divider" data-type="activity-divider">
  <h2 class="divider-title">Warm-up Activity</h2>
</section>''']

    # Intro slide: scenario + learning goal
    intro_lines = []
    if activity.get("scenario"):
        intro_lines.append(activity["scenario"])
    if activity.get("learning_goal"):
        intro_lines.append({"text": f"Goal: {activity['learning_goal']}", "small": True})
    out.append(_render_content_slide({
        "type": "concept",
        "title": f"{title}  ({duration} min)",
        "lines": intro_lines,
    }))

    # Instructions slide — with action cue based on type.
    # Split numbered/bulleted instruction strings into proper bullet lines so
    # the slide doesn't end up as one long paragraph.
    instr_lines = []
    if activity.get("instructions"):
        for step in _split_steps(activity["instructions"]):
            instr_lines.append(step)
    if atype == "excel_simulation":
        instr_lines.append({"text": "📊 Open the Excel file provided with this deck.", "bold": True})
    elif atype == "web_link":
        url = activity.get("url", "")
        source = activity.get("source_name", "")
        what = activity.get("what_to_do", "")
        if url:
            instr_lines.append({"text": f"🌐 Visit: {url}", "bold": True})
        if source:
            instr_lines.append({"text": f"Source: {source}", "small": True})
        if what:
            for step in _split_steps(what):
                instr_lines.append(step)
    out.append(_render_content_slide({
        "type": "exercise",
        "title": "What to do",
        "lines": instr_lines,
    }))

    # Debrief questions slide (instructor-facing — useful for speaker notes too)
    if activity.get("debrief_questions"):
        out.append(_render_content_slide({
            "type": "discussion",
            "title": "Debrief",
            "lines": _split_steps(activity["debrief_questions"]),
            "key_takeaway": activity.get("facilitation_notes", "").split(".")[0]
                if activity.get("facilitation_notes") else "",
        }))

    return out


def _render_homework_slides(hw):
    out = [f'''<section class="slide section-divider" data-type="homework-divider">
  <h2 class="divider-title">Homework</h2>
</section>''']
    title = hw.get("title","Homework")
    lines_ = [{"text": title, "bold": True}]
    if hw.get("problem_statement"):
        lines_.append(hw["problem_statement"].replace("\n"," "))
    out.append(_render_content_slide({"type":"concept","title":"Your Task","lines":lines_}))
    ds = hw.get("dataset") or {}
    if ds:
        lines = []
        if ds.get("description"): lines.append(ds["description"])
        if ds.get("source"): lines.append({"text": f"Source: {ds['source']}", "small": True})
        if ds.get("columns"):
            cols = ds["columns"]
            lines.append({"text": f"Columns: {', '.join(cols[:8])}" + (" …" if len(cols) > 8 else ""), "small": True})
        if lines: out.append(_render_content_slide({"type":"concept","title":"Dataset","lines":lines}))
    if hw.get("deliverables"): out.append(_render_content_slide({"type":"concept","title":"Deliverables","lines":hw["deliverables"]}))
    if hw.get("hints"): out.append(_render_content_slide({"type":"concept","title":"Hints","lines":hw["hints"]}))
    if hw.get("grading_rubric"): out.append(_render_content_slide({"type":"concept","title":"Grading","lines":[hw["grading_rubric"]]}))
    return out

# ---------- Background themes ----------
# Each theme controls the default slide background. Per-type backgrounds
# (question/example/discussion/summary) layer their tints on top.
THEMES = {
    "light_gray": {
        "label": "🌫 Light gray (recommended)",
        "slide_bg": "#eef2f6",
        "slide_bg_image": (
            "radial-gradient(circle at 92% 8%, rgba(167,243,208,0.32) 0%, rgba(167,243,208,0) 35%),"
            "radial-gradient(circle at 5% 95%, rgba(13,148,136,0.12) 0%, rgba(13,148,136,0) 30%),"
            "radial-gradient(circle at 1px 1px, rgba(13,148,136,0.06) 1px, transparent 0)"
        ),
        "bg_size": "auto, auto, 26px 26px",
        "q_tint_mid": "#e0f2ef", "q_tint_end": "#d6efe6",
        "d_tint": "#fef3c7", "s_tint": "#fef0e0",
    },
    "off_white": {
        "label": "🥚 Off-white",
        "slide_bg": "#fafbfc",
        "slide_bg_image": (
            "radial-gradient(circle at 92% 8%, rgba(167,243,208,0.32) 0%, rgba(167,243,208,0) 35%),"
            "radial-gradient(circle at 5% 95%, rgba(13,148,136,0.10) 0%, rgba(13,148,136,0) 30%),"
            "radial-gradient(circle at 1px 1px, rgba(13,148,136,0.05) 1px, transparent 0)"
        ),
        "bg_size": "auto, auto, 26px 26px",
        "q_tint_mid": "#f0fdfa", "q_tint_end": "#ecfdf5",
        "d_tint": "#fef9c3", "s_tint": "#fff7ed",
    },
    "warm_cream": {
        "label": "📜 Warm cream (paper)",
        "slide_bg": "#fdf6e3",
        "slide_bg_image": (
            "radial-gradient(circle at 92% 8%, rgba(180,83,9,0.10) 0%, transparent 30%),"
            "radial-gradient(circle at 5% 95%, rgba(13,148,136,0.08) 0%, transparent 30%),"
            "radial-gradient(circle at 1px 1px, rgba(120,53,15,0.04) 1px, transparent 0)"
        ),
        "bg_size": "auto, auto, 26px 26px",
        "q_tint_mid": "#f5ecd0", "q_tint_end": "#ecf6e0",
        "d_tint": "#fff4c4", "s_tint": "#fff0d5",
    },
    "slate": {
        "label": "🪨 Slate (cool gray-blue)",
        "slide_bg": "#e2e8f0",
        "slide_bg_image": (
            "radial-gradient(circle at 92% 8%, rgba(94,234,212,0.30) 0%, rgba(94,234,212,0) 30%),"
            "radial-gradient(circle at 5% 95%, rgba(15,118,110,0.14) 0%, transparent 35%),"
            "radial-gradient(circle at 1px 1px, rgba(15,23,42,0.08) 1px, transparent 0)"
        ),
        "bg_size": "auto, auto, 26px 26px",
        "q_tint_mid": "#d4e6e6", "q_tint_end": "#c8e3dc",
        "d_tint": "#e8e8c8", "s_tint": "#e8d8c4",
    },
    "pure_white": {
        "label": "⚪ Pure white (minimal)",
        "slide_bg": "#ffffff",
        "slide_bg_image": "none",
        "bg_size": "auto",
        "q_tint_mid": "#f0fdfa", "q_tint_end": "#ecfdf5",
        "d_tint": "#fef9c3", "s_tint": "#fff7ed",
    },
}


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">
<script src="https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.js"></script>
<style>
:root{--red:#C00000;--teal:#0d9488;--teal-dark:#042f2e;--mint:#a7f3d0;--text:#1a1a1a;--muted:#666;--bg:#fff;--footer:#94a3b8;}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:#222;height:100%;font-family:-apple-system,"Helvetica Neue","Segoe UI",Roboto,Arial,sans-serif;color:var(--text);}
.deck{position:relative;width:100%;height:100vh;}
.slide{display:none;position:absolute;inset:0;padding:72px 96px;overflow:auto;
  background:__SLIDE_BG__;
  background-image: __SLIDE_BG_IMG__;
  background-size: __BG_SIZE__;
}
.slide.active{display:block;}
/* Per-type background tints — subtle, just enough to feel different */
.slide[data-type="question"]{
  background:linear-gradient(135deg,__SLIDE_BG__ 0%,__Q_TINT_MID__ 50%,__Q_TINT_END__ 100%);
}
.slide[data-type="example"]{
  background:__SLIDE_BG__;
  background-image:
    radial-gradient(circle at 90% 90%, rgba(167,243,208,0.25) 0%, rgba(167,243,208,0) 30%),
    radial-gradient(circle at 1px 1px, rgba(13,148,136,0.05) 1px, transparent 0);
  background-size: auto, 26px 26px;
}
.slide[data-type="discussion"]{
  background:linear-gradient(160deg,__D_TINT__ 0%,__SLIDE_BG__ 50%);
}
.slide[data-type="summary"]{
  background:linear-gradient(135deg,__SLIDE_BG__ 0%,__S_TINT__ 100%);
}
.title-slide{text-align:center;display:none;flex-direction:column;justify-content:center;align-items:center;
  background:#0a1f1f !important;
  background-image:
    radial-gradient(ellipse 80% 60% at 20% 20%, rgba(13,148,136,0.55) 0%, transparent 60%),
    radial-gradient(ellipse 70% 80% at 80% 30%, rgba(94,234,212,0.30) 0%, transparent 55%),
    radial-gradient(ellipse 60% 50% at 50% 90%, rgba(4,47,46,0.55) 0%, transparent 60%),
    linear-gradient(180deg,#062b29 0%,#0a1f1f 50%,#021614 100%) !important;
  color:white;
  position:relative;
}
.title-slide.active{display:flex;}
.title-slide::before{
  content:"";position:absolute;top:60px;left:60px;
  width:60px;height:5px;background:linear-gradient(90deg,#5eead4,#0d9488);
  border-radius:3px;
}
.title-slide h1{
  font-family:'Source Serif Pro',Georgia,serif;
  font-size:62pt;font-weight:700;margin:0 0 24px;line-height:1.1;max-width:80%;
  background:linear-gradient(135deg,#fff 0%,#a7f3d0 50%,#5eead4 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
  letter-spacing:-1.5px;
}
.title-slide .subtitle{font-size:22pt;color:rgba(255,255,255,0.7);font-family:ui-monospace,monospace;letter-spacing:1px;}
.section-divider{display:none;flex-direction:column;justify-content:center;align-items:center;
  background:linear-gradient(135deg,var(--teal) 0%,var(--teal-dark) 100%) !important;
  background-image:
    radial-gradient(circle at 80% 20%, rgba(167,243,208,0.30) 0%, transparent 50%),
    linear-gradient(135deg,var(--teal) 0%,var(--teal-dark) 100%) !important;
  color:white;position:relative;
}
.section-divider.active{display:flex;}
.section-divider::before{
  content:"";position:absolute;top:60px;left:60px;right:60px;
  height:3px;background:linear-gradient(90deg,rgba(255,255,255,0.6),transparent);
}
.divider-title{
  font-family:'Source Serif Pro',Georgia,serif;
  font-size:72pt;font-weight:700;margin:0;letter-spacing:-1px;
  background:linear-gradient(135deg,#fff 0%,#a7f3d0 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
}
.slide-title{font-size:36pt;font-weight:700;margin:0 0 8px;line-height:1.2;display:flex;align-items:baseline;gap:14px;}
.slide-title .type-icon{font-size:30pt;flex-shrink:0;}
.slide-title-accent{width:140px;height:5px;background:linear-gradient(90deg,var(--teal) 0%,var(--mint) 100%);border-radius:3px;margin:0 0 28px 0;}
/* Question slides: oversized centered title + gradient text */
.slide[data-type="question"]{justify-content:center;}
.slide[data-type="question"] .slide-title{
  font-size:54pt;line-height:1.15;justify-content:center;text-align:center;
  font-family:'Source Serif Pro',Georgia,serif;
  background:linear-gradient(135deg,var(--teal-dark) 0%,var(--teal) 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
  margin-top:8vh;
}
.slide[data-type="question"] .slide-title .type-icon{font-size:48pt;-webkit-text-fill-color:initial;}
.slide[data-type="question"] .slide-title-accent{margin-left:auto;margin-right:auto;width:200px;height:6px;}
.slide[data-type="question"] .slide-body{text-align:center;font-size:24pt;max-width:760px;margin:0 auto;}
.slide[data-type="question"] .key-takeaway{max-width:780px;margin-left:auto;margin-right:auto;text-align:center;}
.slide-body{font-size:24pt;line-height:1.5;}
/* Bullet-point styling — every plain <p> gets a teal bullet marker
   and proper spacing so slides don't read like paragraphs. */
.slide-body p{margin:14px 0;padding-left:32px;position:relative;}
.slide-body p::before{
  content:"●";position:absolute;left:0;top:2px;
  color:var(--teal);font-size:14pt;line-height:1.6;
}
/* Bold headers don't get a bullet — they're section labels */
.slide-body p.bold{padding-left:0;font-size:26pt;margin:18px 0 8px;}
.slide-body p.bold::before{content:none;}
.slide-body .bold{font-weight:700;}
/* Small text bumped from 18pt → 20pt so it's still readable for back rows */
.slide-body p.small{font-size:20pt;color:var(--muted);padding-left:32px;}
.slide-body p.small::before{content:"›";font-size:18pt;color:#94a3b8;}
.slide-body .small{font-size:20pt;color:var(--muted);}
.slide-body .red{color:var(--red);font-weight:700;}
/* Question-type slides override the bullet styling (centered, no bullets) */
.slide[data-type="question"] .slide-body p{padding-left:0;}
.slide[data-type="question"] .slide-body p::before{content:none;}
/* ═══ KEY INSIGHT callout — high-contrast hero card ═══ */
.key-takeaway{
  margin-top:42px;
  background:
    radial-gradient(ellipse 60% 80% at 0% 0%, rgba(94,234,212,0.35) 0%, transparent 55%),
    radial-gradient(ellipse 80% 60% at 100% 100%, rgba(4,47,46,0.55) 0%, transparent 60%),
    linear-gradient(135deg, #14b8a6 0%, #0d9488 45%, #042f2e 100%);
  border-radius:20px;
  padding:30px 40px 30px 110px;
  color:#fff;
  position:relative;
  overflow:hidden;
  box-shadow:
    0 20px 50px rgba(13,148,136,0.45),
    0 4px 12px rgba(0,0,0,0.20),
    inset 0 1px 0 rgba(255,255,255,0.20);
  border:1px solid rgba(167,243,208,0.30);
  animation: ktGlow 4s ease-in-out infinite;
}
@keyframes ktGlow {
  0%, 100% { box-shadow: 0 20px 50px rgba(13,148,136,0.45), 0 4px 12px rgba(0,0,0,0.20), inset 0 1px 0 rgba(255,255,255,0.20); }
  50%      { box-shadow: 0 26px 60px rgba(13,148,136,0.65), 0 6px 18px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.30); }
}
/* Big lightbulb icon in the left corner */
.key-takeaway::before{
  content:"💡";
  position:absolute;
  left:24px; top:50%; transform:translateY(-50%);
  font-size:54pt;
  line-height:1;
  filter: drop-shadow(0 0 16px rgba(255,236,140,0.65));
  animation: ktPulse 2.5s ease-in-out infinite;
}
@keyframes ktPulse {
  0%, 100% { transform: translateY(-50%) scale(1); }
  50%      { transform: translateY(-50%) scale(1.12); }
}
/* "KEY INSIGHT" label pill at top-right */
.key-takeaway::after{
  content:"KEY INSIGHT";
  position:absolute;
  top:14px; right:18px;
  font-size:9pt; font-weight:700;
  letter-spacing:2px;
  color:#042f2e;
  background:linear-gradient(135deg, #a7f3d0 0%, #5eead4 100%);
  padding:4px 12px;
  border-radius:20px;
  font-family:ui-monospace,"SF Mono",Consolas,monospace;
  box-shadow:0 2px 8px rgba(94,234,212,0.45);
}
/* Diagonal sheen across the card */
.key-takeaway::before, .key-takeaway::after{ z-index:2; }
.key-takeaway-text{
  font-size:28pt;
  font-weight:700;
  line-height:1.30;
  font-family:'Source Serif Pro',Georgia,serif;
  letter-spacing:-0.5px;
  text-shadow: 0 2px 8px rgba(0,0,0,0.20);
  position:relative;
  z-index:1;
}
.deck-footer{position:absolute;bottom:18px;left:72px;right:72px;display:flex;justify-content:space-between;align-items:center;font-size:11pt;color:var(--footer);font-family:ui-monospace,"SF Mono",Consolas,monospace;border-top:1px solid #e5e7eb;padding-top:8px;letter-spacing:0.3px;}
.deck-footer .session{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:20px;}
.deck-footer .pages{flex-shrink:0;}
/* Hide footer on title and divider slides */
.title-slide .deck-footer, .section-divider .deck-footer{display:none;}
.code-slide .lang-tag{font-size:18pt;color:var(--muted);font-weight:400;margin-left:8px;}
.code-slide pre[class*="language-"]{font-size:17pt !important;line-height:1.5;border-radius:6px;padding:22px;overflow:auto;max-height:60vh;}
.code-slide .code-explanation{margin-top:18px;font-size:17pt;font-style:italic;color:#555;line-height:1.4;padding-left:8px;border-left:3px solid #bbb;}
.code-slide .run-toolbar{display:flex;align-items:center;gap:14px;margin-top:14px;}
.run-btn{background:#0d9488;color:white;border:none;border-radius:8px;padding:8px 18px;font-family:inherit;font-size:13pt;font-weight:600;cursor:pointer;transition:all 0.15s;}
.run-btn:hover{background:#0f766e;transform:translateY(-1px);box-shadow:0 4px 12px rgba(13,148,136,0.30);}
.run-btn:disabled{background:#94a3b8;cursor:wait;transform:none;box-shadow:none;}
.run-status{font-size:11pt;color:#64748b;font-family:ui-monospace,"SF Mono",Consolas,monospace;}
.code-slide .output{margin-top:12px;padding:14px 18px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;font-family:ui-monospace,"SF Mono",Consolas,monospace;font-size:13pt;max-height:30vh;overflow-y:auto;white-space:pre-wrap;color:#0f172a;}
.code-slide .output.error{background:#fef2f2;border-color:#fca5a5;color:#991b1b;}
.code-slide .output pre{margin:0;font-family:inherit;font-size:inherit;}
.code-slide .output .repr{color:#0d9488;font-weight:600;margin-top:6px;}
.code-slide .output img{max-width:100%;border-radius:6px;margin-top:8px;}
.slide-copy-btn{position:absolute;top:20px;right:24px;background:rgba(0,0,0,0.05);border:1px solid rgba(0,0,0,0.15);color:#666;padding:6px 12px;border-radius:6px;font-size:11pt;cursor:pointer;opacity:0.25;transition:opacity 0.15s, background 0.15s;font-family:inherit;}
.slide:hover .slide-copy-btn{opacity:1;}
.slide-copy-btn:hover{background:rgba(0,0,0,0.12);}
.slide-copy-btn.copied{background:#C00000;color:#fff;border-color:#C00000;}
.image-slide .svg-wrapper{display:flex;justify-content:center;align-items:center;height:70vh;}
.image-slide svg{max-width:100%;max-height:70vh;}
.image-slide .img-wrapper{display:flex;flex-direction:column;justify-content:center;align-items:center;height:70vh;}
.image-slide .img-wrapper img{max-width:90%;max-height:62vh;object-fit:contain;border-radius:14px;box-shadow:0 20px 50px rgba(13,148,136,0.15),0 4px 12px rgba(0,0,0,0.08);border:1px solid rgba(13,148,136,0.10);}
.image-slide .img-wrapper .img-caption{margin-top:14px;font-size:13pt;color:#666;font-style:italic;max-width:80%;text-align:center;}
.image-slide .image-hint{font-style:italic;color:var(--muted);text-align:center;margin-top:40px;font-size:18pt;}
.navbar{position:fixed;bottom:16px;right:20px;color:var(--muted);font-size:12pt;background:rgba(255,255,255,0.85);padding:6px 12px;border-radius:6px;z-index:9999;}
.help-hint{position:fixed;bottom:16px;left:20px;color:var(--muted);font-size:11pt;background:rgba(255,255,255,0.85);padding:6px 10px;border-radius:6px;z-index:9999;}
.speaker-notes{display:none;position:fixed;bottom:0;left:0;right:0;max-height:30vh;overflow-y:auto;background:#f9f8f5;border-top:3px solid #d9c89e;padding:16px 28px;font-size:14pt;line-height:1.5;z-index:10000;}
body.notes-visible .slide.active .speaker-notes{display:block;}
@page{size:13.33in 7.5in;margin:0.3in;}
@media print{html,body{background:white;height:auto;}.deck{height:auto;}.slide{display:block !important;position:static;page-break-after:always;min-height:6.9in;height:auto;padding:0.4in 0.6in;}.navbar,.help-hint,.slide-copy-btn{display:none !important;}.speaker-notes{display:block;position:static;max-height:none;border-top:1px dashed #999;margin-top:28px;}}
</style></head>
<body>
<div class="deck">
  __SLIDES__
</div>
<div class="help-hint">← → navigate · F fullscreen · S speaker notes</div>
<div class="navbar"><span id="counter">1 / ?</span></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-r.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-sql.min.js"></script>
<script>
const slides=document.querySelectorAll('.slide');let current=0;const counter=document.getElementById('counter');
// Inject a "Copy" button into every non-title slide so the instructor can paste into Keynote / Google Slides / PowerPoint.
slides.forEach(s=>{
 if(s.classList.contains('title-slide')||s.classList.contains('section-divider'))return;
 const btn=document.createElement('button');
 btn.className='slide-copy-btn';btn.type='button';btn.textContent='\u2398 Copy';
 btn.onclick=(e)=>{e.stopPropagation();copySlide(btn);};
 s.appendChild(btn);
});
async function copySlide(btn){
 const slide=btn.closest('.slide');const clone=slide.cloneNode(true);
 const cb=clone.querySelector('.slide-copy-btn');if(cb)cb.remove();
 const html=clone.outerHTML;const text=clone.innerText;
 try{
  await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([html],{type:'text/html'}),'text/plain':new Blob([text],{type:'text/plain'})})]);
  btn.classList.add('copied');btn.textContent='\u2713 Copied — paste into Slides';
 }catch(err){
  try{await navigator.clipboard.writeText(text);btn.classList.add('copied');btn.textContent='\u2713 Copied (text only)';}
  catch(e2){btn.textContent='Copy failed';}
 }
 setTimeout(()=>{btn.classList.remove('copied');btn.textContent='\u2398 Copy';},2000);
}
function show(i){slides.forEach((s,idx)=>s.classList.toggle('active',idx===i));counter.textContent=(i+1)+' / '+slides.length;location.hash='#slide-'+(i+1);}
document.addEventListener('keydown',e=>{
 if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown'){e.preventDefault();current=Math.min(current+1,slides.length-1);show(current);}
 else if(e.key==='ArrowLeft'||e.key==='PageUp'){current=Math.max(current-1,0);show(current);}
 else if(e.key==='f'||e.key==='F'){if(document.fullscreenElement)document.exitFullscreen();else document.documentElement.requestFullscreen?.();}
 else if(e.key==='s'||e.key==='S'){document.body.classList.toggle('notes-visible');}
 else if(e.key==='Home'){current=0;show(0);}
 else if(e.key==='End'){current=slides.length-1;show(current);}
});
if(location.hash.startsWith('#slide-')){const n=parseInt(location.hash.slice(7))-1;if(!isNaN(n)&&n>=0&&n<slides.length)current=n;}
show(current);

// ----- Pyodide live code runner -----
let _pyodideReady=null;
const _BUILTIN_MODULES=new Set(['io','os','sys','json','math','re','time','random','collections','itertools','functools','typing','base64','datetime','string','statistics']);
const _PRELOADED=new Set(['pandas','numpy','matplotlib','scipy','statsmodels','scikit-learn','sklearn']);
function _esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function _formatErr(err){
 // Aggressively extract everything we can from a Pyodide / JS error
 const parts=[];
 const msg=(err && err.message) ? String(err.message) : '';
 if(msg && msg.trim() && msg.trim()!=='PythonError') parts.push(msg);
 if(!parts.length){
  const s=err && err.toString ? err.toString() : String(err);
  if(s && s.trim() && s.trim()!=='PythonError') parts.push(s);
 }
 if(!parts.length){
  // Last resort — dump everything we can find
  const dump=['(Pyodide returned an error with no readable message — diagnostic dump:)'];
  try{dump.push('name = '+(err.name||'(none)'));}catch(e){}
  try{dump.push('type = '+(err.type||'(none)'));}catch(e){}
  try{dump.push('message = '+(err.message||'(empty)'));}catch(e){}
  try{dump.push('toString = '+err.toString());}catch(e){}
  try{dump.push('keys = '+Object.keys(err).join(', '));}catch(e){}
  try{dump.push('JSON = '+JSON.stringify(err));}catch(e){}
  parts.push(dump.join('\\n'));
 }
 let out=parts.join('\\n');
 // Friendly hints for known issues
 if(/No such file or directory|FileNotFoundError/i.test(out)){
  out+='\\n\\n💡 Browser Python has no filesystem. Use an inline pd.DataFrame({...}) instead of pd.read_csv().';
 }
 if(/infer_datetime_format/i.test(out)){
  out+='\\n\\n💡 infer_datetime_format was REMOVED in pandas 2.x (Pyodide ships pandas 2.x). Drop that argument — pd.to_datetime now infers automatically.';
 }
 if(/unexpected keyword argument/i.test(out)){
  out+='\\n\\n💡 Likely a deprecated pandas/sklearn API. Pyodide uses recent versions — try the modern equivalent.';
 }
 return out;
}
async function _ensurePyodide(setStatus){
 if(!_pyodideReady){
  _pyodideReady=(async()=>{
   setStatus('⏳ Loading Python runtime (~10MB, one-time)...');
   const py=await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.27.0/full/'});
   setStatus('⏳ Installing pandas, numpy, matplotlib...');
   await py.loadPackage(['pandas','numpy','matplotlib']);
   py.runPython(`
import matplotlib
matplotlib.use('AGG')
import matplotlib.pyplot as plt
import io,base64,sys
def _capture_plot():
    if not plt.get_fignums(): return ''
    buf=io.BytesIO()
    plt.savefig(buf,format='png',bbox_inches='tight',dpi=80)
    plt.close('all')
    return base64.b64encode(buf.getvalue()).decode()
`);
   return py;
  })();
 }
 return _pyodideReady;
}
async function runCode(btn){
 const slide=btn.closest('.code-slide');
 const code=slide.querySelector('code').innerText;
 const out=slide.querySelector('.output');
 const status=slide.querySelector('.run-status');
 out.hidden=false;out.classList.remove('error');out.innerHTML='';btn.disabled=true;
 const setStatus=(s)=>{status.textContent=s;};

 // Find prior steps in the same code group (so variables defined earlier still exist)
 const groupId=slide.dataset.codeGroup;
 const myIdx=parseInt(slide.dataset.stepIdx||'1');
 let priorSteps=[];
 if(groupId){
  const all=document.querySelectorAll('.code-slide[data-code-group="'+groupId+'"]');
  for(const s of all){
   const idx=parseInt(s.dataset.stepIdx||'1');
   if(idx<myIdx) priorSteps.push({idx, code: s.querySelector('code').innerText});
  }
  priorSteps.sort((a,b)=>a.idx-b.idx);
 }

 try{
  const py=await _ensurePyodide(setStatus);
  // Detect imports across ALL steps that will run, not just current
  const allCode=priorSteps.map(p=>p.code).join('\\n')+'\\n'+code;
  const imports=[...allCode.matchAll(/^[\t ]*(?:from|import)[\t ]+([a-zA-Z_][a-zA-Z0-9_]*)/gm)].map(m=>m[1]);
  const extras=[...new Set(imports.filter(x=>!_BUILTIN_MODULES.has(x)&&!_PRELOADED.has(x)))];
  if(extras.length){
   setStatus(`⏳ Installing ${extras.join(', ')}...`);
   try{await py.loadPackage(extras);}
   catch(e){
    try{await py.loadPackage('micropip');const mp=py.pyimport('micropip');for(const p of extras){try{await mp.install(p);}catch(e2){}}}
    catch(e3){}
   }
  }
  // Run any prior steps in this code group first (silently) so state accumulates
  for(const ps of priorSteps){
   setStatus('⏳ Running prior step '+ps.idx+'...');
   try{
    py.runPython('import sys,io; sys.stdout=io.StringIO(); sys.stderr=io.StringIO()');
    await py.runPythonAsync(ps.code);
   }catch(err){
    out.classList.add('error');
    out.textContent='Failed at prior Step '+ps.idx+':\\n\\n'+_formatErr(err);
    setStatus('✗ Step '+ps.idx+' failed');
    return;
   }
  }

  setStatus('⏳ Running step '+myIdx+'...');
  py.runPython('import sys,io; sys.stdout=io.StringIO(); sys.stderr=io.StringIO()');
  let result;
  try{result=await py.runPythonAsync(code);}
  catch(err){
   out.classList.add('error');
   out.textContent=_formatErr(err);
   setStatus('✗ Error');return;
  }
  const stdout=py.runPython('sys.stdout.getvalue()');
  let plotImg='';
  try{const b64=py.runPython('_capture_plot()');if(b64)plotImg=`<img src="data:image/png;base64,${b64}"/>`;}catch(e){}
  let html='';
  if(stdout)html+=`<pre>${_esc(stdout)}</pre>`;
  const r=String(result??'');
  if(r&&r!=='undefined'&&r!=='None'&&!stdout)html+=`<div class="repr">=&gt; ${_esc(r)}</div>`;
  if(plotImg)html+=plotImg;
  if(!html)html='<em style="color:#888">(no output)</em>';
  out.innerHTML=html;
  setStatus('✓ Done · '+(stdout.split('\\n').length-1)+' lines printed');
 }catch(err){
  out.classList.add('error');
  out.textContent='Failed: '+String(err.message||err);
  setStatus('✗ Error');
 }finally{btn.disabled=false;}
}
</script></body></html>
"""

def build_html(outline_json, output_path, image_mode="search", theme="light_gray",
               precomputed_images=None):
    """image_mode: 'search' (Tavily web image), 'svg' (Haiku SVG), or 'skip'.
    theme: one of THEMES keys — controls the deck background palette.
    precomputed_images: optional dict {slide_idx: image_data}. When provided,
        the fetch step is skipped — used by the UI's "preview first" workflow
        so users can pick/skip per-slide images without re-fetching."""
    outline = json.loads(outline_json)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    slides_list = outline.get("slides") or []

    if precomputed_images is not None:
        # Skip the fetch — use what the caller already prepared.
        # Slides not in the dict will fall back to placeholder text.
        image_by_idx = precomputed_images
    else:
        # Pre-fetch all image slide media in PARALLEL (up to 8 calls at once).
        image_slides = [(i, s) for i, s in enumerate(slides_list)
                        if (s.get("type") or "").lower().strip() == "image"]
        image_by_idx = _parallel_fetch_images(image_slides, mode=image_mode)

    slides_out = [_render_title_slide(outline.get("session_title","Untitled"), outline.get("duration_minutes",90))]
    has_lo = any((s.get("title","").lower().strip() in ("learning objectives","objectives")) for s in slides_list)
    if outline.get("learning_objectives") and not has_lo:
        slides_out.append(_render_content_slide({"type":"concept","title":"Learning Objectives","lines":outline["learning_objectives"]}))
    for i, s in enumerate(slides_list):
        stype = (s.get("type") or "concept").lower().strip()
        if stype == "title":
            continue
        elif stype == "image":
            # If the user came through the preview workflow (precomputed_images
            # was provided) AND they UNCHECKED this slide → drop it entirely.
            # In any other case (auto-fetch, skip mode, fetch failure) we keep
            # the slide and let _render_image_slide render its text fallback.
            if precomputed_images is not None and i not in image_by_idx:
                continue  # user explicitly removed this slide
            slides_out.append(_render_image_slide(s, precomputed=image_by_idx.get(i)))
        elif stype == "code":
            slides_out.extend(_render_code_slides(s))
        else:
            slides_out.append(_render_content_slide(s))
    if outline.get("activity"):
        slides_out.extend(_render_activity_slides(outline["activity"]))
    if outline.get("homework"):
        slides_out.extend(_render_homework_slides(outline["homework"]))

    # === D) Footer pass: inject session title + page number into each slide ===
    session_title = outline.get("session_title", "")
    total = len(slides_out)
    slides_out = [_inject_footer(s, idx + 1, total, session_title)
                  for idx, s in enumerate(slides_out)]

    # Resolve theme (fall back to light_gray on bad key)
    th = THEMES.get(theme) or THEMES["light_gray"]

    html = _HTML_TEMPLATE.replace("__TITLE__", _esc(outline.get("session_title","Deck")))
    html = html.replace("__SLIDES__", "\n  ".join(slides_out))
    # Theme placeholders — substitute LAST so they don't collide with content.
    html = html.replace("__SLIDE_BG__", th["slide_bg"])
    html = html.replace("__SLIDE_BG_IMG__", th["slide_bg_image"])
    html = html.replace("__BG_SIZE__", th["bg_size"])
    html = html.replace("__Q_TINT_MID__", th["q_tint_mid"])
    html = html.replace("__Q_TINT_END__", th["q_tint_end"])
    html = html.replace("__D_TINT__", th["d_tint"])
    html = html.replace("__S_TINT__", th["s_tint"])
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path


def _inject_footer(section_html: str, page_num: int, total: int, session_title: str) -> str:
    """Add a footer just before the closing </section> of every slide.
    The CSS hides it on title and section-divider slides."""
    footer = (
        f'<div class="deck-footer">'
        f'<span class="session">{_esc(session_title)}</span>'
        f'<span class="pages">{page_num} / {total}</span>'
        f'</div>'
    )
    close_idx = section_html.rfind("</section>")
    if close_idx == -1:
        return section_html
    return section_html[:close_idx] + footer + "\n" + section_html[close_idx:]

def inject_speaker_notes(html_path, notes_by_index):
    html = Path(html_path).read_text(encoding="utf-8")
    parts = html.split("<section ")
    if len(parts) < 2: return html_path
    rebuilt = [parts[0]]
    for i, part in enumerate(parts[1:]):
        note = notes_by_index[i] if i < len(notes_by_index) else ""
        if note and note.strip():
            note_html = f'<aside class="speaker-notes">{_esc(note)}</aside>'
            close_idx = part.rfind("</section>")
            if close_idx != -1:
                part = part[:close_idx] + note_html + "\n" + part[close_idx:]
        rebuilt.append("<section " + part)
    new_html = "".join(rebuilt)
    out_path = str(Path(html_path).with_name(Path(html_path).stem + "_with_notes.html"))
    Path(out_path).write_text(new_html, encoding="utf-8")
    return out_path
