You are designing a semester syllabus for a business school course.

Input: course description + target number of weeks + course level (undergraduate / MBA / executive) + primary module area.

Output: a JSON object with this exact shape:

{
  "course_title": "string",
  "course_level": "undergraduate | mba | executive",
  "total_weeks": 14,
  "module_area": "analytics | strategy | finance | marketing | operations | information_systems | statistics",
  "learning_outcomes": [
    "By the end of this course, students will be able to ...",
    "..."
  ],
  "prerequisites": "string describing expected prior knowledge / tools",
  "primary_textbook": "Full citation of the recommended textbook, or empty string if none specified",
  "assessment_summary": "e.g., 30% homework, 30% midterm, 40% final project",
  "sessions": [
    {
      "week": 1,
      "session_title": "string",
      "module": "Module 1: Foundations",
      "topics": ["specific topic 1", "specific topic 2"],
      "tools_or_techniques": ["Excel", "Python pandas"],
      "suggested_readings": ["Chapter X of Textbook", "HBR article name", "recent FT piece"],
      "assessment_touchpoint": "e.g., 'HW1 released' or 'midterm' or 'none'"
    }
  ]
}

Rules:
- Generate exactly `total_weeks` session entries (one per week).
- Group sessions into 3–5 coherent modules with clear progression.
- Build complexity over time — foundations → methods → application → synthesis.
- At least one assessment touchpoint per module.
- For analytics/data/IS courses, every session should name specific tools or techniques.
- Readings mix textbook chapters + recent HBR/FT/MIT Sloan Review + one current event per module when relevant.
- If the instructor specified a recommended textbook, set the `primary_textbook` field to that citation, and lead each session's `suggested_readings` with the relevant chapter/section from that textbook (e.g., "Anderson Ch. 3.1-3.4: Numerical Measures"). Then add 1 supplemental current article per session. If no textbook was specified, leave `primary_textbook` as an empty string and use generic chapter references.
- Learning outcomes: 4–6 total, measurable, start with action verbs.
- No markdown, no code fences, just the JSON object.
