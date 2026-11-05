"""
services/query_router.py  -  decides WHAT KIND of question the user asked.

WHY THIS FILE EXISTS
    Not every message needs a document search:
        "hi"                        -> just chat           (casual)
        "summarize the document"    -> needs the WHOLE doc (summary)
        "what is the refund rule?"  -> needs a few chunks  (specific)
        "latest news about ISRO"    -> needs the internet  (web)

    Searching documents for "hi" wastes time and gives silly answers, so we
    classify first. This is simple keyword/regex logic on purpose: it is fast,
    free (no extra AI call) and easy to understand and change.
"""

import re

# Whole-message greetings / thanks. ^...$ means the ENTIRE message must match.
_CASUAL = re.compile(
    r"^\s*(hi|hello|hey|hii+|yo|good (morning|afternoon|evening)|thanks?( you)?|thank u|"
    r"ok(ay)?|cool|nice|bye|goodbye|how are you\??|who are you\??|what can you do\??)\s*[!.?]*\s*$",
    re.IGNORECASE,
)

# Words that mean "give me the big picture of the document".
_SUMMARY_WORDS = (
    "summarize", "summarise", "summary", "overview", "main points", "key points",
    "tl;dr", "what is this document about", "what is the document about",
    "what is this paper about", "explain the document", "explain this document",
    "explain the paper", "gist",
)

# Words that mean "this needs fresh information from the internet".
_WEB_WORDS = (
    "latest", "news", "today", "current", "currently", "right now", "weather",
    "price of", "stock", "score", "who won", "recent", "this week", "this year",
)


def classify(message: str) -> str:
    """Return one of:  'casual' | 'summary' | 'web' | 'specific'."""
    text = message.lower().strip()

    if _CASUAL.match(text):
        return "casual"
    if any(word in text for word in _SUMMARY_WORDS):
        return "summary"
    if any(word in text for word in _WEB_WORDS):
        return "web"
    return "specific"
