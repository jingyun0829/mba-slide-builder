You are analyzing a business school professor's past lecture decks to characterize their teaching style.

You are given quantitative statistics (slide counts, bullet lengths, etc.) plus the raw text of slide titles and bullets from several of their decks. Infer the professor's voice and habits and return a JSON profile that downstream AI slide generators will use as a style constraint.

Return a JSON object with this exact shape:

{
  "tone": "1–2 sentence description — e.g., 'conversational but precise, uses we and you frequently, avoids jargon when possible'",
  "opening_pattern": "How the professor typically opens a lecture — agenda? hook question? real-world anchor? story?",
  "closing_pattern": "How the professor typically closes — summary? forward question? call to action?",
  "example_density": "Low / Medium / High + one-sentence description — do they anchor every concept to a company, or lean abstract?",
  "framework_usage": "How they use frameworks — primary scaffolding, one-of-many lenses, critical-examining, rarely?",
  "bullet_style": "Short phrases, full sentences, hybrid? Any punctuation quirks (em-dashes, colons, parenthetical asides)?",
  "questioning_style": "Socratic, rhetorical, test-check, not much? Do they plant and return to tensions?",
  "recurring_phrases_or_patterns": ["phrase1", "phrase2", "..."],
  "content_to_text_balance": "Text-heavy / balanced / visual-leaning — based on what you can infer from the slide text density",
  "structural_habits": "Any patterns in section use, recap slides, transition slides, mid-lecture checks, etc.",
  "teaching_style_summary": "2–3 sentence overall characterization a ghostwriter would need to mimic this voice"
}

Be specific and evidence-based — quote or paraphrase actual patterns you see rather than writing generic platitudes. If a field isn't clearly inferable, say so (e.g., "not strongly evident in these samples").

JSON only. No code fences. No prose preamble.
