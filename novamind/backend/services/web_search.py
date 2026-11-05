"""
services/web_search.py  -  live internet search through DuckDuckGo.

WHY THIS FILE EXISTS
    Your documents cannot answer "what happened today?". When the router
    decides a question needs fresh information (or the documents do not
    contain the answer), we fetch a few search results and give them to
    the AI as context.

IMPORTANT POINTS
    * No API key is needed.
    * The library was renamed: the new name is `ddgs`, the old one
      `duckduckgo_search`. We try the new name first, then the old one.
    * DuckDuckGo sometimes blocks very frequent requests, so every failure
      is caught and an empty list is returned (the app keeps working).
"""

from typing import Dict, List

try:
    from ddgs import DDGS                      # new package name
except ImportError:                            # pragma: no cover
    try:
        from duckduckgo_search import DDGS     # old package name
    except ImportError:
        DDGS = None                            # search simply becomes unavailable


def web_search(query: str, max_results: int = 5) -> List[Dict]:
    """Return [{title, url, snippet}] or [] if search is unavailable."""
    if DDGS is None:
        return []
    try:
        raw = DDGS().text(query, max_results=max_results)
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", ""),
            }
            for item in raw
        ]
    except Exception:
        return []
