from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    tier: int
    name: str
    agents: tuple[str, ...]
    model_calls: int


def classify(query: str) -> Route:
    """Cheap initial rules; replace/augment with retrieval and measured thresholds."""
    text = query.lower()
    investigation_markers = ("why", "keeps failing", "repeated", "three times", "root cause")
    contextual_markers = ("recently", "relate", "relationship", "who owns", "changed")
    if any(marker in text for marker in investigation_markers):
        return Route(3, "investigation", ("context", "history", "investigation", "verification", "response"), 2)
    if any(marker in text for marker in contextual_markers) or text.count(" and "):
        return Route(2, "contextual", ("context", "response"), 1)
    return Route(1, "lookup", ("context", "response"), 0)
