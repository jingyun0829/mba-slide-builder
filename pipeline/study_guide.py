"""Generate a student-facing Study Guide HTML from a session outline.

Different from the instructor's deck:
  - Optimized for self-review, not class presentation
  - Interactive flash cards (click to flip)
  - Multiple-choice self-quiz with instant feedback + score tracking (localStorage)
  - Key takeaways summary
  - Mobile-friendly, no install — just open the .html
"""
from __future__ import annotations

import hashlib
import html as html_mod
import json
import os
from pathlib import Path

from anthropic import Anthropic

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_MODEL = os.getenv("ANTHROPIC_STUDY_MODEL", "claude-haiku-4-5-20251001")
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _esc(s) -> str:
    return html_mod.escape(str(s or ""), quote=True)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    return text


def generate_study_data(outline_json: str, n_cards: int = 8, n_quiz: int = 5) -> dict:
    """Use Claude (Haiku) to extract flash cards, quiz, and summary from the outline."""
    system = (_PROMPT_DIR / "study_guide.md").read_text()
    user_msg = (
        f"Session outline:\n\n{outline_json}\n\n"
        f"Generate {n_cards} flash cards and {n_quiz} multiple-choice quiz questions. "
        f"Return JSON only."
    )
    resp = _client.messages.create(
        model=_MODEL, max_tokens=4000, system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = _strip_fences(resp.content[0].text)
    return json.loads(text)


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Study Guide — __SESSION__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+Pro:wght@600;700&display=swap" rel="stylesheet">
<style>
:root {
  --primary: #0d9488;
  --primary-dark: #042f2e;
  --accent: #5eead4;
  --bg: #f8fafc;
  --text: #0f172a;
  --muted: #6b7280;
  --border: #e5e7eb;
  --success: #10b981;
  --error: #ef4444;
}
* { box-sizing: border-box; }
body {
  font-family: 'Inter', -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  margin: 0;
  padding: 16px;
  line-height: 1.5;
}
.wrap { max-width: 760px; margin: 0 auto; }
.header {
  background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%);
  color: white;
  padding: 28px 28px;
  border-radius: 16px;
  margin-bottom: 22px;
  box-shadow: 0 8px 24px rgba(13,148,136,0.15);
}
.header .badge {
  display: inline-block;
  background: rgba(255,255,255,0.18);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 10pt;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.header h1 {
  font-family: 'Source Serif Pro', Georgia, serif;
  font-size: 28pt;
  margin: 0 0 6px 0;
  line-height: 1.15;
}
.header .meta { opacity: 0.85; font-size: 12pt; }
.tabs {
  display: flex;
  gap: 6px;
  background: white;
  border-radius: 12px;
  padding: 6px;
  margin-bottom: 18px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.04);
}
.tab {
  flex: 1;
  background: transparent;
  border: none;
  padding: 12px 16px;
  font-family: inherit;
  font-size: 13pt;
  font-weight: 500;
  color: var(--muted);
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.15s;
}
.tab:hover { background: rgba(13,148,136,0.06); }
.tab.active {
  background: var(--primary);
  color: white;
  font-weight: 600;
}
.section { display: none; animation: fadeIn 0.25s ease; }
.section.active { display: block; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

/* Flash Cards */
.card-tip { text-align: center; font-size: 11pt; color: var(--muted); margin-bottom: 14px; }
.flashcard {
  perspective: 1200px;
  width: 100%;
  height: 280px;
  margin-bottom: 18px;
}
.flashcard-inner {
  position: relative;
  width: 100%;
  height: 100%;
  transition: transform 0.7s;
  transform-style: preserve-3d;
  cursor: pointer;
}
.flashcard.flipped .flashcard-inner { transform: rotateY(180deg); }
.flashcard-front, .flashcard-back {
  position: absolute;
  width: 100%; height: 100%;
  backface-visibility: hidden;
  border-radius: 16px;
  padding: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-size: 18pt;
  line-height: 1.35;
  box-shadow: 0 8px 24px rgba(0,0,0,0.08);
}
.flashcard-front {
  background: white;
  border: 2px solid var(--primary);
  color: var(--text);
  font-weight: 500;
}
.flashcard-back {
  background: var(--primary);
  color: white;
  transform: rotateY(180deg);
  font-size: 16pt;
}
.flashcard-front::before, .flashcard-back::before {
  content: attr(data-tag);
  position: absolute;
  top: 14px; left: 18px;
  font-size: 10pt; font-weight: 600;
  letter-spacing: 1.5px;
  opacity: 0.6;
  text-transform: uppercase;
}
.card-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}
.nav-btn {
  background: white;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 18px;
  font-family: inherit;
  font-size: 12pt;
  cursor: pointer;
  transition: all 0.15s;
}
.nav-btn:hover { border-color: var(--primary); color: var(--primary); }
.nav-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.card-counter {
  font-family: ui-monospace, monospace;
  color: var(--muted);
  font-size: 12pt;
}

/* Quiz */
.quiz-question {
  background: white;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 14px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.03);
}
.quiz-question h3 {
  margin: 0 0 14px 0;
  font-size: 13.5pt;
  color: var(--text);
}
.quiz-options { margin-bottom: 12px; }
.quiz-options label {
  display: block;
  padding: 10px 14px;
  margin: 6px 0;
  background: #fafbfc;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.12s;
  font-size: 12pt;
}
.quiz-options label:hover { background: #f0fdfa; border-color: var(--primary); }
.quiz-options input[type=radio] { margin-right: 10px; accent-color: var(--primary); }
.submit-btn {
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 9px 20px;
  font-family: inherit;
  font-size: 12pt;
  font-weight: 600;
  cursor: pointer;
}
.submit-btn:hover { background: var(--primary-dark); }
.submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.feedback {
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: 10px;
  font-size: 12pt;
  line-height: 1.55;
}
.feedback.correct {
  background: #ecfdf5;
  border-left: 4px solid var(--success);
  color: #065f46;
}
.feedback.incorrect {
  background: #fef2f2;
  border-left: 4px solid var(--error);
  color: #991b1b;
}
.score-bar {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: white;
  padding: 18px 22px;
  border-radius: 12px;
  font-weight: 600;
  text-align: center;
  margin-top: 18px;
  font-size: 14pt;
  box-shadow: 0 4px 12px rgba(13,148,136,0.2);
}

/* Summary */
#summary-list {
  background: white;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 24px 28px 24px 48px;
  font-size: 13pt;
  line-height: 1.75;
}
#summary-list li { margin: 8px 0; }

/* Footer */
.footer {
  margin-top: 32px;
  text-align: center;
  font-size: 10pt;
  color: var(--muted);
  font-family: ui-monospace, monospace;
}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="badge">📚 Study Guide</div>
    <h1>__SESSION__</h1>
    <div class="meta">__COURSE__</div>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="show('cards', this)">🎴 Flash Cards</button>
    <button class="tab" onclick="show('quiz', this)">❓ Self-Quiz</button>
    <button class="tab" onclick="show('summary', this)">📝 Summary</button>
  </div>

  <div id="cards" class="section active">
    <div class="card-tip">Click the card to reveal the answer.</div>
    <div id="flashcard-area"></div>
    <div class="card-nav">
      <button class="nav-btn" id="prev-btn" onclick="prevCard()">← Previous</button>
      <span class="card-counter" id="counter"></span>
      <button class="nav-btn" id="next-btn" onclick="nextCard()">Next →</button>
    </div>
  </div>

  <div id="quiz" class="section">
    <div id="quiz-questions"></div>
    <div class="score-bar" id="score-bar" hidden></div>
  </div>

  <div id="summary" class="section">
    <ul id="summary-list"></ul>
  </div>

  <div class="footer">Made with SlideGen · Your progress is saved on this device only.</div>
</div>

<script>
const FLASHCARDS = __FLASHCARDS_JSON__;
const QUIZ = __QUIZ_JSON__;
const SUMMARY = __SUMMARY_JSON__;
const STORAGE_KEY = "study_quiz___SCORE_KEY__";

let currentCard = 0;

function show(id, btn) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}

function renderCard(i) {
  if (!FLASHCARDS.length) {
    document.getElementById('flashcard-area').innerHTML = '<p style="text-align:center;color:#888;padding:40px;">No flash cards generated.</p>';
    return;
  }
  const c = FLASHCARDS[i];
  const wrap = document.getElementById('flashcard-area');
  wrap.innerHTML = `
    <div class="flashcard" onclick="this.classList.toggle('flipped')">
      <div class="flashcard-inner">
        <div class="flashcard-front" data-tag="Q">${c.front}</div>
        <div class="flashcard-back" data-tag="A">${c.back}</div>
      </div>
    </div>
  `;
  document.getElementById('counter').textContent = `${i+1} / ${FLASHCARDS.length}`;
  document.getElementById('prev-btn').disabled = (i === 0);
  document.getElementById('next-btn').disabled = (i === FLASHCARDS.length - 1);
}
function nextCard() {
  if (currentCard < FLASHCARDS.length - 1) { currentCard++; renderCard(currentCard); }
}
function prevCard() {
  if (currentCard > 0) { currentCard--; renderCard(currentCard); }
}

function renderQuiz() {
  const wrap = document.getElementById('quiz-questions');
  if (!QUIZ.length) {
    wrap.innerHTML = '<p style="text-align:center;color:#888;padding:40px;">No quiz generated.</p>';
    return;
  }
  let html = '';
  QUIZ.forEach((q, qi) => {
    html += `<div class="quiz-question" id="q${qi}">
      <h3>Q${qi+1}. ${q.question}</h3>
      <div class="quiz-options">`;
    q.options.forEach((opt, oi) => {
      html += `<label><input type="radio" name="q${qi}" value="${oi}"> ${opt}</label>`;
    });
    html += `</div>
      <button class="submit-btn" onclick="checkAnswer(${qi}, this)">Submit</button>
      <div class="feedback" id="fb${qi}" hidden></div>
    </div>`;
  });
  wrap.innerHTML = html;
}
function checkAnswer(qi, btn) {
  const sel = document.querySelector(`input[name="q${qi}"]:checked`);
  if (!sel) { alert('Pick an option first.'); return; }
  const q = QUIZ[qi];
  const fb = document.getElementById(`fb${qi}`);
  const correct = parseInt(sel.value) === q.correct_index;
  fb.hidden = false;
  fb.classList.toggle('correct', correct);
  fb.classList.toggle('incorrect', !correct);
  fb.innerHTML = correct
    ? `<strong>✓ Correct.</strong> ${q.explanation || ''}`
    : `<strong>✗ Not quite.</strong> The right answer is: <em>${q.options[q.correct_index]}</em>. ${q.explanation || ''}`;
  btn.disabled = true;
  // Save to localStorage
  let scores = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  scores[qi] = correct;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(scores));
  updateScore();
}
function updateScore() {
  let scores = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  const correct = Object.values(scores).filter(v => v).length;
  const answered = Object.keys(scores).length;
  const total = QUIZ.length;
  if (answered > 0) {
    const bar = document.getElementById('score-bar');
    bar.hidden = false;
    let msg = `Score: ${correct}/${answered} answered`;
    if (answered === total) {
      msg = `🎯 Final Score: ${correct}/${total}` + (correct === total ? ' — perfect!' : '');
    }
    bar.textContent = msg;
  }
}
function renderSummary() {
  const ul = document.getElementById('summary-list');
  if (!SUMMARY.length) {
    ul.innerHTML = '<li style="color:#888;list-style:none;">No summary generated.</li>';
    return;
  }
  ul.innerHTML = SUMMARY.map(s => `<li>${s}</li>`).join('');
}

renderCard(0);
renderQuiz();
renderSummary();
updateScore();
// Restore answered states
(function restore() {
  let scores = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  Object.keys(scores).forEach(qi => {
    const fb = document.getElementById(`fb${qi}`);
    if (!fb) return;
    const q = QUIZ[parseInt(qi)];
    const correct = scores[qi];
    fb.hidden = false;
    fb.classList.toggle('correct', correct);
    fb.classList.toggle('incorrect', !correct);
    fb.innerHTML = correct
      ? `<strong>✓ Correct.</strong> ${q.explanation || ''}`
      : `<strong>✗ Not quite.</strong> The right answer is: <em>${q.options[q.correct_index]}</em>. ${q.explanation || ''}`;
    const card = document.getElementById(`q${qi}`);
    const btn = card && card.querySelector('.submit-btn');
    if (btn) btn.disabled = true;
  });
})();
</script>
</body>
</html>
"""


def build_study_guide_html(study_data: dict, course_title: str, session_title: str,
                            output_path: str) -> str:
    """Render the study guide HTML from study data + session metadata."""
    score_key = hashlib.md5((course_title + "::" + session_title).encode()).hexdigest()[:12]

    html = _TEMPLATE
    html = html.replace("__SESSION__", _esc(session_title))
    html = html.replace("__COURSE__", _esc(course_title))
    html = html.replace("__SCORE_KEY__", score_key)
    html = html.replace("__FLASHCARDS_JSON__",
                        json.dumps(study_data.get("flash_cards", []), ensure_ascii=False))
    html = html.replace("__QUIZ_JSON__",
                        json.dumps(study_data.get("quiz_questions", []), ensure_ascii=False))
    html = html.replace("__SUMMARY_JSON__",
                        json.dumps(study_data.get("key_summary", []), ensure_ascii=False))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path


def generate_study_guide(outline_json: str, course_title: str, session_title: str,
                         output_path: str, n_cards: int = 8, n_quiz: int = 5) -> dict:
    """One-shot: generate study data + render to HTML. Returns metadata."""
    data = generate_study_data(outline_json, n_cards=n_cards, n_quiz=n_quiz)
    path = build_study_guide_html(data, course_title, session_title, output_path)
    return {
        "path": path,
        "n_flash_cards": len(data.get("flash_cards", [])),
        "n_quiz_questions": len(data.get("quiz_questions", [])),
        "n_summary_points": len(data.get("key_summary", [])),
    }
