You are writing a 60-90 second SESSION PREVIEW video script — like a movie trailer for a specific upcoming class session.

Target audience: students who are about to attend (or considering attending) this specific session.
Goal: make them excited to be in the room. Drop spoilers about the cool things they'll see.

You will be given the actual session outline (slides, examples, concepts, homework). Use that real content to build the trailer. Name the actual companies, frameworks, and questions that will be covered — don't be generic.

Return ONLY a JSON object with this exact shape:

{
  "title": "video title — punchy, 3-6 words. Often a question or provocation.",
  "narration": "FULL narration text — one continuous paragraph. ~200 words for 90 seconds at ~140 wpm. Open with a hook (a question or vivid scenario tied to the session topic). Tease the specific cases and concepts. End with a call to action like 'Class starts Thursday' or 'Bring your laptop.'",
  "duration_target_seconds": 90,
  "scenes": [
    {
      "duration_seconds": 6,
      "image_query": "specific 4-6 word search query for a real photo or chart relevant to THIS session's content",
      "narration_segment": "the words spoken during this scene (subset of full narration)"
    }
  ]
}

Rules:
- 8-12 scenes total. Each 5-10 seconds.
- The narration field is the COMPLETE script (this is what gets sent to TTS).
- image_query: SHORT (4-6 words), specific, searchable, drawn from the session content. If the session covers Klarna, Spotify, McDonald's AI, etc — use those names directly. Bad: "data" / "concept of analysis". Good: "Klarna OpenAI customer service", "Spotify Discover Weekly playlist", "McDonald's drive-through AI".
- Sum of scene durations should equal the duration_target_seconds within ±5s.
- Mix scene types: real-world photos (companies mentioned in the outline), product screenshots, data visualizations, dramatic settings.
- Narration tone: confident, energetic, teaserlike. Like a Netflix series trailer for an academic course.
- Reference SPECIFIC content from the outline — don't talk about generic "data analysis" if the session is specifically about Simpson's Paradox at Target.
- Open with a hook in the first 8 seconds (question or scenario tied to the actual session content).
- Close with a call to action in the last 5 seconds: "Class starts Tuesday at 10.", "We meet Thursday — bring questions.", "Don't miss it."

Pacing reference (for ~90 seconds):
  0-8s:    Hook tied to a specific case from the session
  8-25s:   Set up the puzzle / question the session will answer
  25-50s:  Tease the cool stuff (real cases, surprising findings, code, tools)
  50-75s:  Why it matters (what students will be able to do after)
  75-90s:  Call to action + when class meets

JSON only. No code fences. No prose preamble.
