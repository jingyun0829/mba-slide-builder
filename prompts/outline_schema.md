Return a JSON object with exactly this shape:

{
  "session_title": "string — 3-8 words",
  "duration_minutes": 90,
  "learning_objectives": ["4-6 short, measurable objectives"],
  "slides": [
    {
      "type": "title | concept | question | example | image | code | exercise | discussion | summary",
      "title": "Short title — 3-10 words, often a question",
      "lines": [
        "plain line",
        {"text": "Bold category header", "bold": true},
        {"text": "smaller explanation or sub-detail", "small": true},
        {"text": "red emphasized term", "red": true}
      ],
      "key_takeaway": "Red bold punchline at the bottom — optional",
      "image_hint": "Short description of diagram to insert — only for type=image",
      "code": {
        "language": "python | r | sql | excel",
        "caption": "one-sentence description",
        "steps": [
          {"description": "Step 1: Load the data", "code": "df = pd.read_csv('ads.csv')"},
          {"description": "Step 2: Filter rows", "code": "treated = df[df.treatment == 1]"},
          {"description": "Step 3: Compute means", "code": "mean_t = treated.y.mean()"}
        ]
      }
    }
  ],
  "homework": {
    "title": "Homework name",
    "problem_statement": "1-2 paragraphs",
    "dataset": {"description": "...", "source": "...", "columns": ["..."]},
    "deliverables": ["..."],
    "hints": ["..."],
    "grading_rubric": "brief rubric with weights"
  }
}

CRITICAL STYLE RULES.

1. NARRATIVE, NOT TEMPLATE. Story arc: problem → observation → examples → challenge → question → mechanism → resolution. One idea per slide. NEVER "Topic — key points / — frameworks / — examples / — discuss".

2. LINE TYPES — use all of them:
   - Plain string: normal 24pt body line
   - {"text": ..., "bold": true}: bold category header (e.g., "Amazon", "World 1 (Treatment)", "Question:")
   - {"text": ..., "small": true}: smaller 18pt line for explanations/sub-details/context
   - {"text": ..., "red": true}: red-bold word/phrase for key terminology ("counterfactual", "confounding")

3. KEY_TAKEAWAY — use liberally. Most concept slides end with a single red 30pt bold punchline (5-15 words). Examples from the instructor's style:
   "If we change X, what happens to Y?"
   "We observe change — but we don't know why"
   "Causal inference is a missing data problem"
   "Patterns repeat over time"
   "Correlation ≠ Causation"
   "Seasonality is NOT random. It is predictable."

4. SLIDE LENGTH — CONSISTENT 3-6 LINES per slide. No walls of text. No mass of one-line slides (except intentional pacing/image slides). Keep rhythm even.

5. QUESTION-FORWARD TITLES. Many titles are questions. Avoid mechanical subtitles.

6. GROUPED CONTENT. For contrasts (Prediction vs Causation, World 1 vs World 2), use bold headers + plain sub-items:
   lines: [
     "Two possible worlds:",
     {"text": "World 1 (Treatment)", "bold": true},
     "Customer sees the ad",
     {"text": "World 2 (No Treatment)", "bold": true},
     "Customer does NOT see the ad"
   ]

7. REAL, RECENT, NAMED. Specific companies, last 24 months.

8. SLIDE TYPES:
   - title: 1 at start
   - concept: 3-6 lines + usually key_takeaway
   - question: title + 0-2 lines + optional key_takeaway
   - example: bold company names + their question
   - image: title + image_hint ONLY
   - code: MUST use code.steps — each step = 1 slide titled "Step N: ..."
   - exercise: hands-on task
   - discussion: Socratic prompt
   - summary: 3-5 takeaways

9. TARGET SLIDE COUNT — lengthen narrative, don't cram.

10. CODE SLIDES (include_code=true) — MANDATORY RULES:
    - You MUST include at least 2 type="code" slides in the deck when include_code=true.
    - Each code slide MUST have a `code` object with `steps` array. Each step = one slide rendered with syntax-highlighted monospace code on a dark background.
    - **BROWSER-RUNNABLE CONSTRAINT**: Python code is executed live in the browser via Pyodide when students click "▶ Run". This means:
      * NO file reads (`pd.read_csv('file.csv')` will fail — there's no filesystem in the browser).
      * NO network calls (`requests.get(...)` won't work).
      * Use INLINE DATA: build small DataFrames from Python dicts in the code itself.
        Example: `df = pd.DataFrame({'region':['N','S','E','W'], 'sales':[100,120,85,140]})`
      * For "loading the data" steps, hardcode 5-15 representative rows as a Python dict, then build the DataFrame.
      * Mention in the explanation: "In production you'd load this from a CSV — here we hardcode a sample so it runs in the browser."
      * If the code MUST reference a real CSV (e.g., to teach pd.read_csv syntax), still build the DataFrame inline AFTER showing the read_csv line, so the rest of the code works:
        ```python
        # df = pd.read_csv('sales.csv')  # in production
        df = pd.DataFrame({...})  # browser-friendly version
        ```
      * Pyodide pre-loads pandas, numpy, matplotlib. scipy, statsmodels, sklearn are available via auto-install on first import.
      * Use MODERN pandas 2.x APIs only. Specifically AVOID:
         - `infer_datetime_format=True` (removed in pandas 2.x — `pd.to_datetime` auto-infers now)
         - `df.append(...)` (removed — use `pd.concat([df1, df2])`)
         - `df.iteritems()` (removed — use `df.items()`)
         - `pd.np` (removed — `import numpy as np` separately)
    - Each step MUST have THREE non-empty fields:
      * `description`: "Step N: short verb phrase" (e.g., "Step 1: Load the dataset")
      * `code`: 3–8 lines of REAL, RUNNABLE code
      * `explanation`: 1–3 sentences explaining what the code does and why — rendered in italic gray below the code block. Students read this when reviewing the deck without the professor. Make it pedagogical: point out the key idea, any gotchas, what decision this enables.
    - Language: pick based on module — Python (pandas, sklearn, matplotlib, seaborn) for analytics, R for stats, SQL for data engineering, Excel for intro. Never invent "Tableau code" — if the session is about a visual tool, still include Python/R to process/analyze the underlying data.
    - Description format: "Step N: short verb phrase". Do NOT end with em-dash and nothing else. Never leave description empty.
    - Example valid code slide:
      {
        "type": "code",
        "title": "Detect a truncated y-axis numerically",
        "code": {
          "language": "python",
          "caption": "Compute the axis range ratio to flag misleading charts",
          "steps": [
            {
              "description": "Step 1: Load the time series",
              "code": "import pandas as pd\ndf = pd.read_csv('sales.csv', parse_dates=['date'])\nprint(df.head())",
              "explanation": "We import pandas and load a CSV of daily sales. parse_dates converts the date column to proper datetime objects so we can compute ranges correctly."
            },
            {
              "description": "Step 2: Compute the axis range",
              "code": "y_min, y_max = df.sales.min(), df.sales.max()\nrange_ratio = (y_max - y_min) / y_max\nprint(f'Axis range ratio: {range_ratio:.2%}')",
              "explanation": "The axis range ratio measures how much of the y-axis is actually used by the data. Values close to 1.0 mean the chart starts near zero; values near 0.0 mean the axis is heavily truncated."
            },
            {
              "description": "Step 3: Flag suspicious charts",
              "code": "if range_ratio < 0.15:\n    print('WARNING: axis truncated — range <15% of max')",
              "explanation": "A rule-of-thumb threshold: if the chart's visible range is less than 15% of the max value, it's probably misleading. You'd run this as a lint step before publishing."
            }
          ]
        }
      }
    - Do NOT create concept slides with titles like "Lab Step 1 —" that contain instructions but no code. Use type="code" or don't create the slide at all.

11. HOMEWORK (include_homework=true): top-level homework{} only.

12. IN-CLASS ACTIVITY (include_activity=true) — 10-minute warm-up.
    Add a top-level "activity" field:

    {
      "type": "excel_simulation" | "web_link",
      "title": "short name — 3-6 words",
      "learning_goal": "1 sentence — what students learn",
      "duration_minutes": 10,
      "scenario": "2-3 sentence scenario hook (e.g., 'You are a regional manager at Target...')",
      "instructions": "step-by-step what students do (paragraph or list)",
      "facilitation_notes": "what the professor does while students work + how to debrief",
      "debrief_questions": ["1-3 questions to ask after the activity"],

      // If type = "excel_simulation":
      "excel_spec": {
        "sheets": [
          {
            "name": "Data",
            "data": [
              ["Region", "Month", "Revenue", "Customers"],
              ["North", "Jan", 102000, 450],
              ["North", "Feb", 108000, 470]
              // ... 10-30 rows of realistic synthetic data
            ]
          },
          {
            "name": "Your Task",
            "cells": [
              {"cell": "A1", "value": "Your Task", "bold": true, "size": 14},
              {"cell": "A3", "value": "Compute the mean revenue by region below:"},
              {"cell": "A5", "value": "North:", "bold": true},
              {"cell": "B5", "value": "(your answer)"},
              {"cell": "A6", "value": "South:", "bold": true},
              {"cell": "B6", "value": "(your answer)"},
              {"cell": "D5", "formula": "=AVERAGEIF(Data!A:A,\"North\",Data!C:C)"},
              {"cell": "D6", "formula": "=AVERAGEIF(Data!A:A,\"South\",Data!C:C)"},
              {"cell": "D4", "value": "Solution (check after):", "bold": true, "size": 11}
            ]
          }
        ]
      },

      // If type = "web_link":
      "url": "real, stable, free URL (e.g., https://seeing-theory.brown.edu/basic-probability/)",
      "source_name": "publisher — e.g., 'Seeing Theory (Brown University)'",
      "what_to_do": "specific steps to do on that site (e.g., 'Click The Law of Large Numbers and run 1000 coin flips')"
    }

    TYPE SELECTION — pick intelligently:
    - excel_simulation for: data manipulation (stats, A/B testing, Simpson's paradox, forecasting, pricing, optimization). Students compute something in Excel using the data you provide.
    - web_link for: visualization-heavy topics (global data, probability intuitions, network effects, economics). Recommend existing free tools — Seeing Theory, Gapminder, Google Trends, FRED, Observable, Kaggle Public, Our World in Data.

    EXCEL CONSTRAINTS — MAX COMPATIBILITY:
    - ONLY these formulas: SUM, AVERAGE, COUNT, MIN, MAX, SUMIF, AVERAGEIF, COUNTIF, IF, AND, OR, NOT, VLOOKUP, INDEX, MATCH, ROUND, basic arithmetic.
    - DO NOT use LET, LAMBDA, FILTER, SORT, UNIQUE, XLOOKUP, dynamic arrays, or anything Excel 365-only.
    - Cross-sheet references use format: Data!A:A or Data!B2:B20.
    - Keep each sheet to ≤ 30 rows. Keep cell formulas readable.
    - Student answer cells should be labeled "(your answer)" so students know where to type.
    - Solution formulas should be in hidden/side cells (like column D) that students can reveal after attempting.

    Only ONE activity per deck. 10-minute warm-up, NOT a 30-minute deep exercise.

No markdown outside schema. No code fences. Return the JSON object only.
