"""Generate a realistic synthetic Excel dataset for a homework assignment."""
from __future__ import annotations
import json, os
from pathlib import Path
from anthropic import Anthropic

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
# Haiku handles synthetic JSON data generation fine — much cheaper than Opus.
_MODEL = os.getenv("ANTHROPIC_DATASET_MODEL", "claude-haiku-4-5-20251001")

_SYSTEM = """You generate realistic synthetic datasets for business school homework.

Return ONLY a JSON object:
{"columns": ["col1","col2",...], "rows": [[...],[...],...]}

Rules:
- columns MUST match the requested names exactly
- rows: generate the requested number of rows
- Values must be plausible: real-sounding names, recent ISO dates, realistic amounts, consistent types per column
- Include interesting structure relevant to the homework — groups, trends, outliers, confounders, seasonality, imbalance, missing values
- No explanations, no code, no markdown. JSON only."""

def _strip_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"): text = text[4:]
        text = text.strip("` \n")
    return text

def generate_dataset(homework, output_path, rows=150):
    import pandas as pd
    ds = homework.get("dataset") or {}
    columns = ds.get("columns") or []
    description = ds.get("description") or ""
    problem = homework.get("problem_statement") or ""
    hw_title = homework.get("title", "Homework")
    if not columns:
        raise ValueError("Homework dataset has no columns defined.")
    user_msg = f"""Homework title: {hw_title}

Homework problem:
{problem}

Dataset description: {description}
Required columns (in order): {columns}
Rows to generate: {rows}

Return the JSON object only."""
    resp = _client.messages.create(model=_MODEL, max_tokens=12000, system=_SYSTEM,
                                    messages=[{"role":"user","content":user_msg}])
    text = _strip_fences(resp.content[0].text)
    data = json.loads(text)
    cols = data.get("columns") or columns
    rows_out = data.get("rows") or []
    df = pd.DataFrame(rows_out, columns=cols)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False, engine="openpyxl")
    return output_path
