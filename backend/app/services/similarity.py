"""Question similarity. Pure text, no dependencies on the rest of the app.

Lives in its own module because both validation.py and interview.py need
it, and importing it from either into the other would make a cycle.
"""

from __future__ import annotations

import re

# Words carrying no topical signal, ignored when comparing two questions.
# Interview questions are dense with these ("can you tell me about how you
# handled..."), and leaving them in makes every question look alike.
_STOPWORDS = frozenset(
    ["a", "an", "the", "and", "or", "but", "if", "then", "than", "that", "this", "these", "those", "of", "in", "on", "at", "to", "for", "with", "from", "by", "about", "into", "over", "after", "before", "you", "your", "yours", "we", "our", "us", "they", "them", "their", "it", "its", "is", "are", "was", "were", "be", "been", "being", "do", "does", "did", "doing", "done", "have", "has", "had", "having", "can", "could", "would", "should", "will", "shall", "may", "might", "must", "what", "which", "who", "whom", "whose", "when", "where", "why", "how", "me", "my", "mine", "i", "as", "so", "such", "there", "here", "any", "some", "more", "most", "other", "another", "each", "both", "few", "many", "much", "tell", "describe", "explain", "walk", "through", "give", "example"]
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def content_words(question: str) -> set[str]:
    return {
        w
        for w in _WORD_RE.findall(question.lower())
        if w not in _STOPWORDS and len(w) > 2
    }


def similarity(a: str, b: str) -> float:
    """Jaccard overlap of content words, 0 to 1.

    Deliberately crude. This guards against the model re-asking something
    in near identical words; the interview state is what prevents topic
    level repetition, by telling the model which criteria are already
    covered.
    """
    wa, wb = content_words(a), content_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def most_similar_prior(question: str, prior: list[str]) -> tuple[str | None, float]:
    """The closest earlier question and how close it is."""
    best: tuple[str | None, float] = (None, 0.0)
    for candidate in prior:
        score = similarity(question, candidate)
        if score > best[1]:
            best = (candidate, score)
    return best
