import csv
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Optional

from app.config import LOGS_DIR, OPENROUTER_MODEL
from app.models.schemas import CompletionRequest, SubmissionRequest


COMPLETION_FIELDS = [
    "timestamp",
    "participant_id",
    "problem_id",
    "method",
    "selected_option",
    "model",
    "suggestion_length",
    "suggestion",
    "raw_response",
]


SUBMISSION_FIELDS = [
    "timestamp",
    "participant_id",
    "problem_id",
    "method",
    "selected_option",
    "model",
    "passed",
]


OPTION_ORDER = [
    "concept_suggestion",
    "code_suggestion",
    "direct_code",
]


def canonical_option(value: Optional[object]) -> Optional[str]:
    """
    Convert model/front-end option formats into one canonical label.

    Important mapping:
    1 -> concept_suggestion
    2 -> code_suggestion
    3 -> direct_code
    """
    if value is None:
        return None

    key = str(value).strip().lower()
    if not key:
        return None

    key = key.replace("_", " ").replace("-", " ")
    key = re.sub(r"[^a-z0-9\s.]", " ", key)
    key = re.sub(r"\s+", " ", key).strip()

    if (
        key == "1"
        or key.startswith("1 ")
        or "concept" in key
        or "hint" in key
        or "empower" in key
        or "general" in key
    ):
        return "concept_suggestion"

    if (
        key == "2"
        or key.startswith("2 ")
        or "code suggestion" in key
        or "code suggest" in key
        or "snippet" in key
        or key == "code"
    ):
        return "code_suggestion"

    if (
        key == "3"
        or key.startswith("3 ")
        or "direct code" in key
        or "full code" in key
        or "complete code" in key
        or ("direct" in key and "code" in key)
    ):
        return "direct_code"

    return None


def empty_option_counts() -> dict:
    return {option: 0 for option in OPTION_ORDER}


def calculate_percentages(counts: dict) -> dict:
    total = sum(int(counts.get(option, 0) or 0) for option in OPTION_ORDER)

    if total == 0:
        return {option: 0.0 for option in OPTION_ORDER}

    return {
        option: round((int(counts.get(option, 0) or 0) / total) * 100, 2)
        for option in OPTION_ORDER
    }


def option_usage_summary(
    participant_id: Optional[str] = None,
    problem_id: Optional[str] = None,
) -> dict:
    counts = count_option_usage(
        participant_id=participant_id,
        problem_id=problem_id,
    )
    total = sum(int(counts.get(option, 0) or 0) for option in OPTION_ORDER)

    return {
        "counts": counts,
        "percentages": calculate_percentages(counts),
        "total": total,
    }


def _file_is_empty(path: Path) -> bool:
    return not path.exists() or path.stat().st_size == 0


def log_completion(
    req: CompletionRequest,
    suggestion: str,
    metrics: dict,
    selected_option: str,
    raw_response: str = "",
):
    path = LOGS_DIR / "completion_logs.csv"
    should_write_header = _file_is_empty(path)

    clean_selected_option = canonical_option(selected_option) or selected_option

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COMPLETION_FIELDS)

        if should_write_header:
            writer.writeheader()

        writer.writerow(
            {
                "timestamp": int(time.time()),
                "participant_id": req.participant_id,
                "problem_id": req.problem_id,
                "method": req.method,
                "selected_option": clean_selected_option,
                "model": OPENROUTER_MODEL,
                "suggestion_length": metrics["suggestion_length"],
                "suggestion": suggestion,
                "raw_response": raw_response,
            }
        )


def _option_from_raw_response(raw_response: Optional[str]) -> Optional[str]:
    """Recover the selected option from the model JSON stored in raw_response."""
    if not raw_response:
        return None

    text = str(raw_response).strip()
    text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
    text = re.sub(r"```$", "", text).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    return canonical_option(
        parsed.get("selected_option")
        or parsed.get("option")
        or parsed.get("help_type")
        or parsed.get("choice")
    )


def _iter_completion_rows(path: Path):
    """
    Read both new CSV logs with headers and old headerless logs.

    The uploaded project had a headerless completion_logs.csv, so csv.DictReader
    treated the first data row as the header and made counts look broken.
    """
    if not path.exists() or path.stat().st_size == 0:
        return

    with path.open("r", newline="", encoding="utf-8") as f:
        sample = f.readline()
        f.seek(0)

        has_header = sample.lower().startswith("timestamp,")
        if has_header:
            reader = csv.DictReader(f)
        else:
            reader = csv.DictReader(f, fieldnames=COMPLETION_FIELDS)

        for row in reader:
            if not row:
                continue
            yield row


def count_option_usage(
    participant_id: Optional[str] = None,
    problem_id: Optional[str] = None,
) -> dict:
    path = LOGS_DIR / "completion_logs.csv"
    counts = Counter()

    if not path.exists():
        return empty_option_counts()

    for row in _iter_completion_rows(path):
        if participant_id and row.get("participant_id") != participant_id:
            continue

        if problem_id and row.get("problem_id") != problem_id:
            continue

        # Prefer the model JSON if available because earlier versions could
        # write the wrong selected_option column due to the 2/3 mapping bug.
        selected_option = _option_from_raw_response(row.get("raw_response"))
        if not selected_option:
            selected_option = canonical_option(row.get("selected_option"))
        if not selected_option:
            selected_option = canonical_option(row.get("method"))

        if selected_option in OPTION_ORDER:
            counts[selected_option] += 1

    return {option: counts.get(option, 0) for option in OPTION_ORDER}


def log_submission(req: SubmissionRequest, passed: bool):
    path = LOGS_DIR / "submission_logs.csv"
    should_write_header = _file_is_empty(path)

    clean_selected_option = canonical_option(req.selected_option) or req.selected_option

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUBMISSION_FIELDS)

        if should_write_header:
            writer.writeheader()

        writer.writerow(
            {
                "timestamp": int(time.time()),
                "participant_id": req.participant_id,
                "problem_id": req.problem_id,
                "method": req.method,
                "selected_option": clean_selected_option,
                "model": OPENROUTER_MODEL,
                "passed": passed,
            }
        )
