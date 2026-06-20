def count_characters(text: str) -> int:
    """
    Count characters in the helper response.
    """
    return len(text or "")


def compute_completion_metrics(suggestion: str) -> dict:
    """
    Metrics collected every time the participant asks for help.

    One backend response = one helper suggestion.
    Suggestion count can be calculated later by counting rows in completion_logs.csv.
    """
    return {
        "suggestion_length": count_characters(suggestion),
    }