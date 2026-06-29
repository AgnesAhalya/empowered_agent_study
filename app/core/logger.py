import csv
import json
import re
import time
from datetime import datetime
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


HEADERLESS_COMPLETION_FIELDS = COMPLETION_FIELDS


def canonical_option(value: Optional[object]) -> Optional[str]:
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
    method: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    counts = count_option_usage(
        participant_id=participant_id,
        problem_id=problem_id,
        method=method,
        model=model,
    )
    total = sum(int(counts.get(option, 0) or 0) for option in OPTION_ORDER)

    return {
        "counts": counts,
        "percentages": calculate_percentages(counts),
        "total": total,
    }


def _file_is_empty(path: Path) -> bool:
    return not path.exists() or path.stat().st_size == 0


def _matches_filter(row_value: Optional[object], wanted_value: Optional[str]) -> bool:
    if wanted_value is None or str(wanted_value).strip() == "":
        return True

    return str(row_value or "").strip() == str(wanted_value).strip()


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
    if not path.exists() or path.stat().st_size == 0:
        return

    with path.open("r", newline="", encoding="utf-8") as f:
        sample = f.readline()
        f.seek(0)

        has_header = sample.lower().startswith("timestamp,")
        if has_header:
            reader = csv.DictReader(f)
        else:
            reader = csv.DictReader(f, fieldnames=HEADERLESS_COMPLETION_FIELDS)

        for row in reader:
            if not row:
                continue

            for field in COMPLETION_FIELDS:
                row.setdefault(field, "")

            yield row


def count_option_usage(
    participant_id: Optional[str] = None,
    problem_id: Optional[str] = None,
    method: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    path = LOGS_DIR / "completion_logs.csv"
    counts = Counter()

    if not path.exists():
        return empty_option_counts()

    for row in _iter_completion_rows(path):
        if not _matches_filter(row.get("participant_id"), participant_id):
            continue

        if not _matches_filter(row.get("problem_id"), problem_id):
            continue

        if not _matches_filter(row.get("method"), method):
            continue

        if not _matches_filter(row.get("model"), model):
            continue

        selected_option = canonical_option(row.get("selected_option"))

        if not selected_option:
            selected_option = _option_from_raw_response(row.get("raw_response"))

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

def _iter_submission_rows(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return

    with path.open("r", newline="", encoding="utf-8") as f:
        sample = f.readline()
        f.seek(0)

        has_header = sample.lower().startswith("timestamp,")
        if has_header:
            reader = csv.DictReader(f)
        else:
            reader = csv.DictReader(f, fieldnames=SUBMISSION_FIELDS)

        for row in reader:
            if not row:
                continue

            for field in SUBMISSION_FIELDS:
                row.setdefault(field, "")

            yield row


def _to_int(value: Optional[object], default: int = 0) -> int:
    """Convert Unix numeric or ISO timestamp strings to an integer timestamp."""
    if value is None:
        return default

    text = str(value).strip()
    if not text:
        return default

    try:
        return int(float(text))
    except Exception:
        pass

    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except Exception:
        return default


def _to_bool(value: Optional[object]) -> bool:
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes", "y", "passed"}


def _empty_summary_counts() -> dict:
    return {
        "helper_requests": 0,
        "test_runs": 0,
        "passed_test_runs": 0,
        "failed_test_runs": 0,
        "option_counts": empty_option_counts(),
        "suggestion_length_total": 0,
        "suggestion_length_avg": 0.0,
    }


def _bump_option(counts: dict, selected_option: Optional[object]) -> None:
    option = canonical_option(selected_option)
    if option in OPTION_ORDER:
        counts[option] = int(counts.get(option, 0) or 0) + 1


def _finalize_counts(counts: dict) -> dict:
    helper_requests = int(counts.get("helper_requests", 0) or 0)
    suggestion_total = int(counts.get("suggestion_length_total", 0) or 0)
    counts["suggestion_length_avg"] = round(
        suggestion_total / helper_requests, 2
    ) if helper_requests else 0.0
    counts["option_percentages"] = calculate_percentages(counts.get("option_counts", {}))
    return counts


def study_summary(
    participant_id: Optional[str] = None,
    method: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """
    Human-readable study summary source.

    Combines completion_logs.csv and submission_logs.csv and returns both:
    - overall totals
    - problem-wise totals
    """
    completion_path = LOGS_DIR / "completion_logs.csv"
    submission_path = LOGS_DIR / "submission_logs.csv"

    overall = _empty_summary_counts()
    problems = {}

    def get_problem_bucket(problem_id: str) -> dict:
        if problem_id not in problems:
            problems[problem_id] = {
                "problem_id": problem_id,
                "first_event_timestamp": None,
                "last_event_timestamp": None,
                "passed_once": False,
                "latest_passed": False,
                **_empty_summary_counts(),
            }
        return problems[problem_id]

    for row in _iter_completion_rows(completion_path) or []:
        if not _matches_filter(row.get("participant_id"), participant_id):
            continue
        if not _matches_filter(row.get("method"), method):
            continue
        if not _matches_filter(row.get("model"), model):
            continue

        problem_id = str(row.get("problem_id") or "unknown_problem")
        bucket = get_problem_bucket(problem_id)
        timestamp = _to_int(row.get("timestamp"), 0)

        for target in (overall, bucket):
            target["helper_requests"] += 1
            target["suggestion_length_total"] += _to_int(row.get("suggestion_length"), 0)
            _bump_option(target["option_counts"], row.get("selected_option"))

        if timestamp:
            if bucket["first_event_timestamp"] is None or timestamp < bucket["first_event_timestamp"]:
                bucket["first_event_timestamp"] = timestamp
            if bucket["last_event_timestamp"] is None or timestamp > bucket["last_event_timestamp"]:
                bucket["last_event_timestamp"] = timestamp

    for row in _iter_submission_rows(submission_path) or []:
        if not _matches_filter(row.get("participant_id"), participant_id):
            continue
        if not _matches_filter(row.get("method"), method):
            continue
        if not _matches_filter(row.get("model"), model):
            continue

        problem_id = str(row.get("problem_id") or "unknown_problem")
        bucket = get_problem_bucket(problem_id)
        timestamp = _to_int(row.get("timestamp"), 0)
        passed = _to_bool(row.get("passed"))

        for target in (overall, bucket):
            target["test_runs"] += 1
            if passed:
                target["passed_test_runs"] += 1
            else:
                target["failed_test_runs"] += 1

        bucket["latest_passed"] = passed
        bucket["passed_once"] = bool(bucket["passed_once"] or passed)

        if timestamp:
            if bucket["first_event_timestamp"] is None or timestamp < bucket["first_event_timestamp"]:
                bucket["first_event_timestamp"] = timestamp
            if bucket["last_event_timestamp"] is None or timestamp > bucket["last_event_timestamp"]:
                bucket["last_event_timestamp"] = timestamp

    problem_list = sorted(
        (_finalize_counts(problem) for problem in problems.values()),
        key=lambda item: (
            item.get("first_event_timestamp") is None,
            item.get("first_event_timestamp") or 0,
            item.get("problem_id") or "",
        ),
    )

    attempted_problem_count = len(problem_list)
    solved_problem_count = sum(1 for problem in problem_list if problem.get("passed_once"))
    latest_passed_problem_count = sum(1 for problem in problem_list if problem.get("latest_passed"))

    overall = _finalize_counts(overall)
    overall.update(
        {
            "attempted_problem_count": attempted_problem_count,
            "solved_problem_count": solved_problem_count,
            "latest_passed_problem_count": latest_passed_problem_count,
            "completion_log_exists": completion_path.exists(),
            "submission_log_exists": submission_path.exists(),
        }
    )

    return {
        "participant_id": participant_id,
        "method": method,
        "model": model,
        "overall": overall,
        "problems": problem_list,
    }
