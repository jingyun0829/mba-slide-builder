"""Export an HTML deck file to PDF via headless Chrome/Chromium.

Uses Chrome's built-in --print-to-pdf flag. No Python dependency beyond
subprocess + pathlib. Chrome renders the HTML exactly like the user sees
it in the browser — Prism syntax highlighting, SVG diagrams, rich colors,
and dark code backgrounds all preserved.

The HTML's @page CSS rule controls page size (set to 13.33in x 7.5in
for 16:9 slide aspect ratio).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

_CHROME_CANDIDATES = [
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    # Linux
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def _find_chrome() -> str | None:
    # Allow an env override for unusual installs
    env_path = os.environ.get("CHROME_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    for p in _CHROME_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def export_html_to_pdf(html_path: str, pdf_path: str, wait_ms: int = 8000) -> str:
    """Render the HTML file to a PDF using headless Chrome.

    wait_ms: virtual time to let the page run JS (Prism highlighting, SVG rendering).
    """
    chrome = _find_chrome()
    if not chrome:
        raise RuntimeError(
            "Couldn't find Chrome/Chromium. Install Google Chrome (chrome.google.com) or "
            "set CHROME_PATH in your .env to the browser binary. "
            "Fallback: open the .html in your browser and use Cmd+P → Save as PDF."
        )

    html_abs = Path(html_path).resolve()
    if not html_abs.exists():
        raise FileNotFoundError(f"HTML deck not found: {html_abs}")

    pdf_abs = Path(pdf_path).resolve()
    pdf_abs.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",          # remove URL / date headers
        f"--virtual-time-budget={wait_ms}", # let JS (Prism, custom injection) finish
        f"--print-to-pdf={pdf_abs}",
        f"file://{html_abs}",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Chrome headless timed out after 3 minutes.")

    if result.returncode != 0 or not pdf_abs.exists():
        raise RuntimeError(
            f"Chrome headless PDF generation failed.\n"
            f"Return code: {result.returncode}\n"
            f"stderr: {result.stderr[:500]}"
        )

    return str(pdf_abs)
