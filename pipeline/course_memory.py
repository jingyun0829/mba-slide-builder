"""Course-level memory: track what's been taught across weeks.

After each session's outline is generated, AI extracts the key concepts,
frameworks, and cases from it and saves a "memory snapshot" to disk. When
generating future weeks' outlines, all prior memory snapshots are loaded
and injected into the prompt — so the AI:
  - References past concepts naturally ("As we saw with Target last week...")
  - Doesn't re-explain things already taught
  - Inserts a 2-3 slide recap at the start of new sessions

Memory is stored under `course_memory/week_NN.json` (zero-padded for sort order).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from anthropic import Anthropic

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_MODEL = os.getenv("ANTHROPIC_MEMORY_MODEL", "claude-haiku-4-5-20251001")
_MEMORY_DIR = Path("course_memory")


_EXTRACT_SYSTEM = """You read a session outline and extract a compact "course memory" entry.

Return ONLY a JSON object with this exact shape:
{
  "key_concepts": ["3-6 concepts taught — short noun phrases, e.g. 'Simpson\\'s Paradox', 'A/B testing'"],
  "frameworks_introduced": ["formal frameworks/methods, e.g. 'Pearl\\'s causal hierarchy', 'TCE'"],
  "cases_used": ["specific named real-world cases referenced, e.g. 'Target Q4 2023', 'Klarna OpenAI'"],
  "key_takeaways": ["1-3 sentence-form takeaways students should retain"],
  "code_techniques": ["if any code was taught, list techniques like 'pandas groupby', 'AVERAGEIF', 'scikit-learn LogisticRegression'"]
}

Be specific. Use the actual names in the outline, not generic terms. JSON only — no fences, no prose."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    return text


def extract_session_memory(outline_json: str) -> dict:
    """Use Haiku to extract the memory snapshot from a generated outline."""
    resp = _client.messages.create(
        model=_MODEL,
        max_tokens=1500,
        system=_EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": f"Outline JSON:\n\n{outline_json}\n\nReturn the memory JSON."}],
    )
    text = _strip_fences(resp.content[0].text)
    return json.loads(text)


def save_session_memory(week: int, session_title: str, memory: dict) -> Path:
    """Save memory for one week as week_NN.json. Returns the file path."""
    _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"week": week, "session_title": session_title, **memory}
    path = _MEMORY_DIR / f"week_{week:02d}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return path


def load_prior_memory(up_to_week: int) -> list[dict]:
    """Load saved DETAILED memory entries for weeks BEFORE up_to_week. Sorted by week."""
    if not _MEMORY_DIR.exists():
        return []
    out = []
    for p in sorted(_MEMORY_DIR.glob("week_*.json")):
        m = re.match(r"week_(\d+)\.json", p.name)
        if not m:
            continue
        week = int(m.group(1))
        if week >= up_to_week:
            continue
        try:
            out.append(json.loads(p.read_text()))
        except Exception:
            pass
    return out


def _syllabus_session_to_memory(session: dict) -> dict:
    """Convert a syllabus session entry into a lightweight memory snapshot."""
    return {
        "week": session.get("week"),
        "session_title": session.get("session_title", ""),
        "key_concepts": session.get("topics", []) or [],
        "frameworks_introduced": [],
        "cases_used": [],
        "key_takeaways": [],
        "code_techniques": session.get("tools_or_techniques", []) or [],
        "from_syllabus_only": True,  # prompt formatter will mark these differently
    }


def load_prior_memory_with_syllabus(up_to_week: int, syllabus_obj: dict | None = None) -> list[dict]:
    """Load DETAILED memory; fill gaps using syllabus topics so every prior week has SOMETHING."""
    detailed = {m["week"]: m for m in load_prior_memory(up_to_week) if m.get("week")}

    out = []
    if syllabus_obj and syllabus_obj.get("sessions"):
        for s in sorted(syllabus_obj["sessions"], key=lambda x: x.get("week", 0)):
            wk = s.get("week")
            if not wk or wk >= up_to_week:
                continue
            if wk in detailed:
                out.append(detailed[wk])
            else:
                out.append(_syllabus_session_to_memory(s))
    else:
        # No syllabus available — just return detailed memory as before
        out = sorted(detailed.values(), key=lambda x: x.get("week", 0))
    return out


def list_all_memory() -> list[dict]:
    """List all saved memory entries (for the UI to display)."""
    if not _MEMORY_DIR.exists():
        return []
    out = []
    for p in sorted(_MEMORY_DIR.glob("week_*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except Exception:
            pass
    return out


def clear_memory() -> int:
    """Delete all memory files. Returns count deleted."""
    if not _MEMORY_DIR.exists():
        return 0
    count = 0
    for p in _MEMORY_DIR.glob("week_*.json"):
        p.unlink()
        count += 1
    return count


def memory_to_prompt_block(memories: list[dict], include_recap: bool = True) -> str:
    """Format memory entries as a prompt fragment for the outline generator."""
    if not memories:
        return ""
    lines = [
        "===== COURSE MEMORY — what students already know =====",
        "Below is what has been taught in PREVIOUS sessions of this course.",
        "Two kinds of entries appear:",
        "  ✅ DETAILED — actual generated outline content. Reference specific cases, frameworks, takeaways from these.",
        "  📋 PLANNED — drawn from the syllabus topic list. The session will cover these themes; treat them as scheduled but don't quote specifics.",
        "Use this to:",
        "  1. Reference past concepts naturally ('As we saw with Target last week, ...')",
        "  2. Build on prior frameworks rather than reinventing them",
        "  3. Avoid re-teaching what students already know",
        "",
    ]
    for m in memories:
        wk = m.get("week", "?")
        title = m.get("session_title", "")
        tag = "📋 PLANNED" if m.get("from_syllabus_only") else "✅ DETAILED"
        lines.append(f"--- Week {wk} ({tag}): {title} ---")
        if m.get("key_concepts"):
            label = "Topics scheduled" if m.get("from_syllabus_only") else "Concepts taught"
            lines.append(f"  {label}: " + ", ".join(m["key_concepts"]))
        if m.get("frameworks_introduced"):
            lines.append("  Frameworks: " + ", ".join(m["frameworks_introduced"]))
        if m.get("cases_used"):
            lines.append("  Cases: " + ", ".join(m["cases_used"]))
        if m.get("key_takeaways"):
            for kt in m["key_takeaways"]:
                lines.append(f"  • Takeaway: {kt}")
        if m.get("code_techniques"):
            label = "Tools/techniques scheduled" if m.get("from_syllabus_only") else "Code techniques used"
            lines.append(f"  {label}: " + ", ".join(m["code_techniques"]))
        lines.append("")

    if include_recap:
        lines.append(
            "RECAP SLIDES — at the START of the new outline (before the hook/intro), "
            "insert 2-3 short type='concept' slides that recap the most relevant prior content. "
            "Title them clearly: 'Quick Recap: Last Week' or 'Where We Left Off'. "
            "Use bold-line headers for the prior session titles, then plain lines for the 2-4 most "
            "relevant takeaways or concepts. Keep these recap slides concise (3-5 lines each) — "
            "they're a 90-second warm-up, not a re-lecture."
        )
    lines.append("===== END COURSE MEMORY =====")
    return "\n".join(lines)
