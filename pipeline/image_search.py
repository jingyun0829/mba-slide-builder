"""Search the web for a real image matching a slide topic via Tavily.

Tries multiple query variations to maximize hit rate, then filters
returned URLs leniently (any HTTP URL, prefer image extensions but
don't require them — many CDNs serve images without extensions).
"""
from __future__ import annotations

import os


_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")
_IMAGE_HOST_HINTS = (
    "/images/", "/image/", "/img/", "/photo/", "/photos/",
    "/media/", "/uploads/", "/assets/", "/static/",
    "wikimedia.org", "wikipedia.org", "imgur.com", "cloudfront.net",
    "googleusercontent.com", "ggpht.com", "fbcdn.net", "twimg.com",
    "cdninstagram.com", "pinimg.com", "alicdn.com", "shopify.com",
)


def _pick_best_image(images: list) -> dict | None:
    """From Tavily's image results, pick the most likely real image URL.

    Stricter than before: ONLY accept URLs that look like real image files
    (ext-based) or are on known image-host domains. Webpage URLs are
    rejected — they cause broken-image icons in the browser.
    """
    if not images:
        return None

    candidates = []
    for img in images:
        if isinstance(img, dict):
            url = img.get("url") or ""
            desc = img.get("description") or ""
        else:
            url = str(img)
            desc = ""
        if not url or not url.startswith("http"):
            continue
        candidates.append((url, desc))

    # Pass 1: URLs whose path ends in an image extension
    for url, desc in candidates:
        lower = url.lower().split("?")[0].split("#")[0]
        if any(lower.endswith(ext) for ext in _IMAGE_EXTS):
            return {"url": url, "description": desc}

    # Pass 2: URLs on known image hosts / CDNs (no extension required)
    for url, desc in candidates:
        lower = url.lower()
        if any(hint in lower for hint in _IMAGE_HOST_HINTS):
            return {"url": url, "description": desc}

    # Reject everything else — webpage URLs cause broken images.
    return None


def search_image(query: str) -> dict | None:
    """Return {"url": ..., "description": ...} for the best matching image, or None."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or not query.strip():
        return None
    try:
        from tavily import TavilyClient
    except ImportError:
        return None

    client = TavilyClient(api_key=api_key)
    base = query.strip()

    # Build a list of query variants to try in order — short & visual-leaning first.
    words = base.split()
    queries: list[str] = []

    # Short version (≤ 6 words) tends to match best
    queries.append(" ".join(words[:6]))
    # Add visual keywords for chart/diagram-type topics
    queries.append(" ".join(words[:6]) + " chart")
    queries.append(" ".join(words[:6]) + " example")
    # Original full query as last resort
    if len(words) > 6:
        queries.append(base)

    # Dedupe while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            unique_queries.append(q)

    for q in unique_queries:
        try:
            results = client.search(
                query=q,
                include_images=True,
                include_image_descriptions=True,
                search_depth="advanced",   # advanced returns more images than basic
                max_results=5,
            )
        except Exception:
            continue
        images = results.get("images") or []
        best = _pick_best_image(images)
        if best:
            return best

    return None
