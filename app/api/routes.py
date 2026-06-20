import json

from fastapi import APIRouter, HTTPException

from app.assistants.openrouter_client import METHOD_CONFIG, call_openrouter
from app.config import OPENROUTER_MODEL, PROBLEMS_DIR, SUBMISSIONS_DIR
from app.core.logger import log_completion, log_submission, option_usage_summary
from app.core.metrics import compute_completion_metrics
from app.models.schemas import CompletionRequest, CompletionResponse, SubmissionRequest
from app.runners.runner import run_function_tests


router = APIRouter()


@router.get("/")
def root():
    return {
        "name": "Soft-Empower Coding Study",
        "status": "running",
        "methods": list(METHOD_CONFIG.keys()),
        "model": OPENROUTER_MODEL,
    }


@router.get("/health")
def health():
    return {
        "status": "ok",
        "model": OPENROUTER_MODEL,
    }


@router.get("/stats/options")
def option_stats(
    participant_id: str | None = None,
    problem_id: str | None = None,
    method: str | None = None,
    model: str | None = None,
):
    usage = option_usage_summary(
        participant_id=participant_id,
        problem_id=problem_id,
        method=method,
        model=model,
    )

    return {
        "participant_id": participant_id,
        "problem_id": problem_id,
        "method": method,
        "model": model,
        "option_counts": usage["counts"],
        "option_percentages": usage["percentages"],
        "option_total": usage["total"],
    }


@router.get("/problems")
def list_problems():
    problems = []

    for path in PROBLEMS_DIR.glob("*.json"):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        problems.append(
            {
                "id": data["id"],
                "title": data["title"],
                "description": data["description"],
                "starter_code": data["starter_code"],
            }
        )

    return {"problems": problems}


@router.get("/problems/{problem_id}")
def get_problem(problem_id: str):
    path = PROBLEMS_DIR / f"{problem_id}.json"

    if not path.exists():
        raise HTTPException(status_code=404, detail="Problem not found")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "id": data["id"],
        "title": data["title"],
        "description": data["description"],
        "starter_code": data["starter_code"],
    }


@router.post("/complete", response_model=CompletionResponse)
def complete(req: CompletionRequest):
    problem_description = ""

    if req.problem_id:
        problem_path = PROBLEMS_DIR / f"{req.problem_id}.json"

        if problem_path.exists():
            with problem_path.open("r", encoding="utf-8") as f:
                problem = json.load(f)
                problem_description = problem.get("description", "")

    model_choice = call_openrouter(
        prefix=req.prefix,
        method=req.method,
        problem_description=problem_description,
    )

    suggestion = model_choice["suggestion"]
    selected_option = model_choice["selected_option"]
    raw_response = model_choice.get("raw_response", "")

    metrics = compute_completion_metrics(suggestion)

    log_completion(
        req=req,
        suggestion=suggestion,
        metrics=metrics,
        selected_option=selected_option,
        raw_response=raw_response,
    )

    usage = option_usage_summary(
        participant_id=req.participant_id,
        problem_id=req.problem_id,
        method=req.method,
        model=OPENROUTER_MODEL,
    )

    return CompletionResponse(
        suggestion=suggestion,
        selected_option=selected_option,
        method=req.method,
        problem_id=req.problem_id,
        model=OPENROUTER_MODEL,
        suggestion_length=metrics["suggestion_length"],
        option_counts=usage["counts"],
        option_percentages=usage["percentages"],
        option_total=usage["total"],
    )


@router.post("/submit")
def submit(req: SubmissionRequest):
    problem_path = PROBLEMS_DIR / f"{req.problem_id}.json"

    if not problem_path.exists():
        raise HTTPException(status_code=404, detail="Problem not found")

    with problem_path.open("r", encoding="utf-8") as f:
        problem = json.load(f)

    result = run_function_tests(req.code, problem)

    submission_path = SUBMISSIONS_DIR / (
        f"{req.participant_id}_{req.problem_id}_{req.method}.py"
    )

    submission_path.write_text(req.code, encoding="utf-8")

    log_submission(req, result["passed"])

    return result