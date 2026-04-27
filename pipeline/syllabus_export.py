"""Export the syllabus JSON to a nicely-formatted document.

Provides:
- syllabus_to_markdown(syl_json) -> str       (downloadable .md, easy to edit)
- syllabus_to_html(syl_json)     -> str       (printable HTML)
- syllabus_to_pdf(syl_json, out_path) -> str  (HTML → headless Chrome PDF)
"""
from __future__ import annotations
import html as html_mod
import json
from pathlib import Path


def _esc(s):
    return html_mod.escape(str(s or ""), quote=True)


# ──────────────────────────────────────────────────────────────
#  Markdown — clean, editable, works everywhere
# ──────────────────────────────────────────────────────────────
def syllabus_to_markdown(syl_json) -> str:
    syl = json.loads(syl_json) if isinstance(syl_json, str) else syl_json
    lines = []
    lines.append(f"# {syl.get('course_title', 'Untitled Course')}")
    meta_bits = []
    if syl.get("course_level"): meta_bits.append(syl["course_level"].title())
    if syl.get("total_weeks"):  meta_bits.append(f"{syl['total_weeks']} weeks")
    if syl.get("module_area"):  meta_bits.append(syl["module_area"].replace("_", " ").title())
    if meta_bits:
        lines.append(f"_{ ' · '.join(meta_bits) }_")
    lines.append("")

    if syl.get("primary_textbook"):
        lines.append("## 📖 Primary textbook")
        lines.append(f"{syl['primary_textbook']}")
        lines.append("")

    recs = syl.get("textbook_recommendations") or []
    if recs and not syl.get("primary_textbook"):
        lines.append("## 📚 Recommended textbooks (choose one)")
        for r in recs:
            lines.append(f"- {r}")
        lines.append("")

    if syl.get("learning_outcomes"):
        lines.append("## Learning outcomes")
        for lo in syl["learning_outcomes"]:
            lines.append(f"- {lo}")
        lines.append("")

    if syl.get("prerequisites"):
        lines.append("## Prerequisites")
        lines.append(syl["prerequisites"])
        lines.append("")

    if syl.get("assessment_summary"):
        lines.append("## Assessment")
        lines.append(syl["assessment_summary"])
        lines.append("")

    if syl.get("sessions"):
        lines.append("## Weekly schedule")
        lines.append("")
        for s in syl["sessions"]:
            wk = s.get("week", "?")
            title = s.get("session_title", "(untitled)")
            module = s.get("module", "")
            topics = s.get("topics", [])
            tools = s.get("tools_or_techniques", [])
            assess = s.get("assessment_touchpoint", "")
            lines.append(f"### Week {wk}: {title}")
            if module: lines.append(f"_Module: {module}_")
            if topics: lines.append(f"**Topics:** {', '.join(topics)}")
            if tools:  lines.append(f"**Tools / techniques:** {', '.join(tools)}")
            if assess and assess.lower() not in ("none", "n/a", ""):
                lines.append(f"**Assessment:** {assess}")
            lines.append("")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
#  HTML — printable, used as the source for PDF export
# ──────────────────────────────────────────────────────────────
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+Pro:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');
@page { size: letter; margin: 0.7in 0.8in; }
:root { --teal:#0d9488; --teal-dk:#042f2e; --mint:#a7f3d0; --text:#0f172a; --muted:#64748b; --line:#e2e8f0; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0;
  font-family: 'Inter', -apple-system, "Helvetica Neue", sans-serif;
  color: var(--text); line-height: 1.55; background: white;
  font-size: 11pt;
}
.page { max-width: 7.2in; margin: 0 auto; padding: 24px 0; }
.hero {
  border-left: 6px solid var(--teal); padding: 8px 0 8px 22px;
  margin-bottom: 28px;
}
h1 {
  font-family: 'Source Serif Pro', Georgia, serif;
  font-size: 28pt; font-weight: 700; line-height: 1.1; margin: 0 0 6px;
  color: var(--teal-dk); letter-spacing: -0.5px;
}
.meta {
  font-family: ui-monospace, "SF Mono", monospace;
  font-size: 9pt; letter-spacing: 1.5px; text-transform: uppercase;
  color: var(--teal); margin-top: 6px;
}
h2 {
  font-family: 'Source Serif Pro', Georgia, serif;
  font-size: 15pt; font-weight: 700; color: var(--teal-dk);
  margin: 28px 0 10px; padding-bottom: 4px;
  border-bottom: 2px solid var(--mint);
}
h3 {
  font-family: 'Source Serif Pro', Georgia, serif;
  font-size: 13pt; font-weight: 600; color: var(--teal-dk);
  margin: 16px 0 6px;
}
.callout {
  background: #f0fdfa; border-left: 4px solid var(--teal);
  padding: 10px 16px; border-radius: 6px; margin: 10px 0;
  font-size: 10.5pt;
}
.callout .label {
  display: block; font-size: 8.5pt; font-weight: 700;
  color: var(--teal); letter-spacing: 1.2px; text-transform: uppercase;
  margin-bottom: 3px;
}
ul, ol { margin: 6px 0 12px; padding-left: 22px; }
li { margin: 3px 0; }
.session {
  border: 1px solid var(--line); border-radius: 8px;
  padding: 12px 16px; margin: 8px 0;
  page-break-inside: avoid;
  background: #fafbfc;
}
.session .week-label {
  display: inline-block; font-size: 8.5pt; font-weight: 700;
  background: var(--teal); color: white;
  padding: 2px 9px; border-radius: 12px;
  letter-spacing: 1px; text-transform: uppercase;
  margin-right: 10px; vertical-align: middle;
}
.session-title {
  font-family: 'Source Serif Pro', Georgia, serif;
  font-size: 13pt; font-weight: 600; color: var(--teal-dk);
  display: inline; vertical-align: middle;
}
.session .module {
  font-size: 9pt; color: var(--muted); font-style: italic;
  margin: 4px 0 8px;
}
.session .row {
  font-size: 10.5pt; margin: 3px 0;
}
.session .row strong { color: var(--teal-dk); }
.session .assess {
  display: inline-block;
  background: #fef9c3; padding: 1px 8px; border-radius: 6px;
  font-size: 9.5pt; font-weight: 600; color: #854d0e;
}
.footer {
  margin-top: 36px; padding-top: 14px; border-top: 1px solid var(--line);
  font-size: 9pt; color: var(--muted); text-align: center;
  font-family: ui-monospace, monospace; letter-spacing: 0.5px;
}
@media print {
  body { font-size: 10.5pt; }
  .page { padding: 0; }
}
</style>
</head><body><div class="page">
__BODY__
<div class="footer">Generated with SlideGen · AI course decks for business school instructors</div>
</div></body></html>
"""


def _render_section_html(title, inner_html):
    return f"<h2>{_esc(title)}</h2>\n{inner_html}\n"


def syllabus_to_html(syl_json) -> str:
    syl = json.loads(syl_json) if isinstance(syl_json, str) else syl_json

    course_title = syl.get("course_title", "Untitled Course")
    meta_bits = []
    if syl.get("course_level"): meta_bits.append(syl["course_level"].title())
    if syl.get("total_weeks"):  meta_bits.append(f"{syl['total_weeks']} weeks")
    if syl.get("module_area"):  meta_bits.append(syl["module_area"].replace("_", " ").title())
    meta_line = " · ".join(meta_bits)

    body_parts = [
        f'<div class="hero">'
        f'<h1>{_esc(course_title)}</h1>'
        f'<div class="meta">{_esc(meta_line)}</div>'
        f'</div>'
    ]

    # Primary textbook (if set)
    tb = (syl.get("primary_textbook") or "").strip()
    if tb:
        body_parts.append(
            f'<div class="callout">'
            f'<span class="label">📖 Primary textbook</span>'
            f'{_esc(tb)}'
            f'</div>'
        )
    # Recommended textbooks (only if no primary picked yet)
    recs = syl.get("textbook_recommendations") or []
    if recs and not tb:
        rec_html = "<ul>" + "".join(f"<li>{_esc(r)}</li>" for r in recs) + "</ul>"
        body_parts.append(
            f'<div class="callout">'
            f'<span class="label">📚 Recommended textbooks</span>'
            f'{rec_html}'
            f'</div>'
        )

    # Learning outcomes
    if syl.get("learning_outcomes"):
        lo_html = "<ul>" + "".join(f"<li>{_esc(lo)}</li>" for lo in syl["learning_outcomes"]) + "</ul>"
        body_parts.append(_render_section_html("Learning outcomes", lo_html))

    # Prerequisites
    if syl.get("prerequisites"):
        body_parts.append(_render_section_html("Prerequisites", f"<p>{_esc(syl['prerequisites'])}</p>"))

    # Assessment
    if syl.get("assessment_summary"):
        body_parts.append(_render_section_html("Assessment", f"<p>{_esc(syl['assessment_summary'])}</p>"))

    # Weekly schedule
    if syl.get("sessions"):
        sess_html = []
        for s in syl["sessions"]:
            wk = _esc(s.get("week", "?"))
            title = _esc(s.get("session_title", "(untitled)"))
            module = _esc(s.get("module", ""))
            topics = s.get("topics") or []
            tools = s.get("tools_or_techniques") or []
            assess = (s.get("assessment_touchpoint") or "").strip()

            rows = []
            if topics:
                rows.append(f'<div class="row"><strong>Topics:</strong> {_esc(", ".join(topics))}</div>')
            if tools:
                rows.append(f'<div class="row"><strong>Tools:</strong> {_esc(", ".join(tools))}</div>')
            if assess and assess.lower() not in ("none", "n/a", ""):
                rows.append(f'<div class="row"><span class="assess">📝 {_esc(assess)}</span></div>')

            sess_html.append(
                f'<div class="session">'
                f'<span class="week-label">Week {wk}</span>'
                f'<span class="session-title">{title}</span>'
                + (f'<div class="module">{module}</div>' if module else "")
                + "".join(rows)
                + '</div>'
            )
        body_parts.append(_render_section_html("Weekly schedule", "\n".join(sess_html)))

    return (_HTML_TEMPLATE
            .replace("__TITLE__", _esc(course_title))
            .replace("__BODY__", "\n".join(body_parts)))


# ──────────────────────────────────────────────────────────────
#  PDF — uses headless Chrome via existing pdf_export.py
# ──────────────────────────────────────────────────────────────
def syllabus_to_pdf(syl_json, output_path) -> str:
    """Render syllabus → HTML → PDF (via headless Chrome)."""
    from pipeline.pdf_export import export_html_to_pdf
    html_str = syllabus_to_html(syl_json)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    # Write a temp HTML file (Chrome needs a file://, not raw string)
    html_path = str(Path(output_path).with_suffix(".html"))
    Path(html_path).write_text(html_str, encoding="utf-8")
    return export_html_to_pdf(html_path, str(output_path))
