from __future__ import annotations

import argparse
import ast
import json
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


# Avoid interactive Hugging Face prompt inside Docker.
os.environ.setdefault("HF_DATASETS_TRUST_REMOTE_CODE", "1")


SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_]+")


def safe_id(value: Any) -> str:
    text = str(value or "problem").strip().lower()
    text = SAFE_ID_RE.sub("_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80] or "problem"


def load_json_maybe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None

        try:
            return json.loads(s)
        except Exception:
            return value

    return value


def parse_value(text: Any) -> Any:
    if not isinstance(text, str):
        return text

    s = text.strip()

    if not s:
        return ""

    lowered = s.lower()

    if lowered == "true":
        return True

    if lowered == "false":
        return False

    if lowered in {"null", "none"}:
        return None

    if s.endswith(";"):
        s = s[:-1].strip()

    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(s)
        except Exception:
            pass

    return s


def get_signature_params(starter_code: str, func_name: str) -> List[str]:
    pattern = re.compile(r"def\s+" + re.escape(func_name) + r"\s*\(([^)]*)\)")
    match = pattern.search(starter_code or "")

    if not match:
        return []

    raw = match.group(1).strip()
    params: List[str] = []

    for part in raw.split(","):
        name = part.strip()

        if not name:
            continue

        name = name.split(":", 1)[0].split("=", 1)[0].strip()

        if name and name != "self":
            params.append(name)

    return params


def extract_function_starter(starter_code: str, func_name: str) -> str:
    starter_code = starter_code or ""
    lines = starter_code.splitlines()

    def_line_idx: Optional[int] = None
    indent = ""

    for i, line in enumerate(lines):
        if re.search(r"\bdef\s+" + re.escape(func_name) + r"\s*\(", line):
            def_line_idx = i
            indent = line[: len(line) - len(line.lstrip())]
            break

    if def_line_idx is None:
        return f"from typing import *\n\n\ndef {func_name}(*args):\n    pass"

    selected: List[str] = []

    for line in lines[def_line_idx:]:
        if selected and line.strip() and not line.startswith(indent + " ") and line.startswith(indent):
            break

        if line.startswith(indent):
            line = line[len(indent):]

        selected.append(line)

    code = "\n".join(selected).strip("\n")

    code = re.sub(
        r"def\s+" + re.escape(func_name) + r"\s*\(\s*self\s*,\s*",
        f"def {func_name}(",
        code,
        count=1,
    )

    code = re.sub(
        r"def\s+" + re.escape(func_name) + r"\s*\(\s*self\s*\)",
        f"def {func_name}()",
        code,
        count=1,
    )

    if "pass" not in code and "..." not in code:
        stripped = code.rstrip()
        if stripped.endswith(":") or not stripped.splitlines()[-1].strip():
            code = stripped + "\n    pass"
        elif len(code.splitlines()) == 1:
            code += "\n    pass"

    return "from typing import *\n\n\n" + code


def parse_lcb_test_case(
    test_case: Dict[str, Any],
    param_names: Sequence[str],
) -> Optional[Dict[str, Any]]:
    inp = test_case.get("input")
    out = test_case.get("output", test_case.get("expected"))

    args: Optional[List[Any]] = None

    if isinstance(inp, dict):
        if param_names and all(name in inp for name in param_names):
            args = [parse_value(inp[name]) for name in param_names]
        else:
            args = [parse_value(v) for v in inp.values()]

    elif isinstance(inp, list):
        args = [parse_value(v) for v in inp]

    elif isinstance(inp, str):
        text = inp.strip()
        assignments: Dict[str, Any] = {}

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            match = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", line)

            if match:
                assignments[match.group(1)] = parse_value(match.group(2))

        if assignments and param_names and all(name in assignments for name in param_names):
            args = [assignments[name] for name in param_names]
        elif assignments:
            args = list(assignments.values())
        elif len(param_names) == 1:
            args = [parse_value(text)]
        else:
            return None

    if args is None:
        return None

    expected = parse_value(out)

    return {
        "args": args,
        "expected": expected,
    }


def convert_lcb_row(
    row: Dict[str, Any],
    max_tests: int = 5,
    include_private: bool = False,
) -> Optional[Dict[str, Any]]:
    platform = str(row.get("platform", ""))

    # Keep only LeetCode-style function problems for your current test runner.
    if "leetcode" not in platform.lower():
        return None

    meta = load_json_maybe(row.get("meta_data", row.get("metadata"))) or {}

    if not isinstance(meta, dict):
        return None

    func_name = meta.get("func_name") or meta.get("function_name")

    if not func_name:
        return None

    starter_code = row.get("starter_code") or ""
    param_names = get_signature_params(starter_code, str(func_name))
    function_starter = extract_function_starter(starter_code, str(func_name))

    public_cases = load_json_maybe(row.get("public_test_cases")) or []
    private_cases = load_json_maybe(row.get("private_test_cases")) or []

    if not isinstance(public_cases, list):
        return None

    cases = list(public_cases)

    if include_private and isinstance(private_cases, list):
        cases += list(private_cases[:max_tests])

    tests: List[Dict[str, Any]] = []

    for test_case in cases:
        if not isinstance(test_case, dict):
            continue

        parsed = parse_lcb_test_case(test_case, param_names)

        if parsed is not None:
            tests.append(parsed)

        if len(tests) >= max_tests:
            break

    if len(tests) < 2:
        return None

    qid = row.get("question_id") or row.get("contest_id") or row.get("question_title") or func_name
    pid = "lcb_" + safe_id(qid)

    title = row.get("question_title") or f"LiveCodeBench {qid}"
    difficulty = str(row.get("difficulty") or "medium").lower()

    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    return {
        "id": pid,
        "title": str(title),
        "source": "LiveCodeBench code_generation_lite",
        "description": str(row.get("question_content") or ""),
        "starter_code": function_starter,
        "function_name": str(func_name),
        "level": difficulty,
        "required": False,
        "tests": tests,
        "livecodebench": {
            "platform": row.get("platform"),
            "question_id": row.get("question_id"),
            "contest_id": row.get("contest_id"),
            "contest_date": row.get("contest_date"),
        },
    }


def load_livecodebench(
    dataset_name: str,
    split: Optional[str],
    limit: int = 50,
) -> List[Dict[str, Any]]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency. Add this to requirements.txt:\n"
            "datasets==3.6.0\n"
            "huggingface_hub[hf_xet]>=0.23.0"
        ) from exc

    if not split:
        split = "test"

    print(f"Streaming only {limit} rows from {dataset_name}, split={split} ...")

    try:
        dataset = load_dataset(
            dataset_name,
            split=split,
            streaming=True,
            trust_remote_code=True,
        )

        rows: List[Dict[str, Any]] = []

        for row in dataset:
            rows.append(dict(row))

            if len(rows) >= limit:
                break

        return rows

    except Exception as exc:
        raise RuntimeError(
            f"Could not stream {dataset_name}. Last error: {exc}"
        ) from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def patch_app_js(project_root: Path, problem_ids: Sequence[str]) -> bool:
    app_js = project_root / "frontend" / "app.js"

    if not app_js.exists():
        return False

    text = app_js.read_text(encoding="utf-8")

    replacement = "const PROBLEM_IDS = " + json.dumps(list(problem_ids), indent=2) + ";"

    new_text, count = re.subn(
        r"const\s+PROBLEM_IDS\s*=\s*\[[\s\S]*?\]\s*;",
        replacement,
        text,
        count=1,
    )

    if count == 0:
        return False

    app_js.write_text(new_text, encoding="utf-8")

    return True


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--project-root",
        default=".",
        help="Path to empowered_agent_study root",
    )

    parser.add_argument(
        "--out",
        default="problems",
        help="Problem output directory relative to project root",
    )

    parser.add_argument(
        "--dataset",
        default="livecodebench/code_generation_lite",
    )

    parser.add_argument(
        "--split",
        default="test",
        help="HF split to stream from. Default: test.",
    )

    parser.add_argument(
        "--count",
        type=int,
        default=8,
        help="Number of random LiveCodeBench problems to write",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling",
    )

    parser.add_argument(
        "--stream-limit",
        type=int,
        default=50,
        help="Only stream this many raw LiveCodeBench rows. Default: 50.",
    )

    parser.add_argument(
        "--max-tests",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Also include some private tests if parseable",
    )

    parser.add_argument(
        "--clear-old-lcb",
        action="store_true",
        help="Delete old lcb_*.json files before writing new sample",
    )

    parser.add_argument(
        "--patch-app-js",
        action="store_true",
        help="Patch frontend/app.js const PROBLEM_IDS if present",
    )

    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    out_dir = project_root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.clear_old_lcb:
        for old_file in out_dir.glob("lcb_*.json"):
            old_file.unlink()

    rows = load_livecodebench(
        args.dataset,
        args.split,
        limit=args.stream_limit,
    )

    print(f"Streamed {len(rows)} raw LiveCodeBench rows")

    candidates: List[Dict[str, Any]] = []
    seen_ids = set()

    for row in rows:
        converted = convert_lcb_row(
            row,
            max_tests=args.max_tests,
            include_private=args.include_private,
        )

        if not converted:
            continue

        problem_id = converted["id"]

        if problem_id in seen_ids:
            continue

        seen_ids.add(problem_id)
        candidates.append(converted)

    print(f"Found {len(candidates)} convertible LeetCode-style LiveCodeBench problems")

    if len(candidates) < args.count:
        raise SystemExit(
            f"Only found {len(candidates)} convertible problems from {args.stream_limit} streamed rows, "
            f"but --count is {args.count}. Try increasing --stream-limit to 100 or 200."
        )

    rng = random.Random(args.seed)
    selected_lcb = rng.sample(candidates, args.count)

    for problem in selected_lcb:
        write_json(out_dir / f"{problem['id']}.json", problem)

    selected_ids = [problem["id"] for problem in selected_lcb]

    manifest = {
        "name": "livecodebench_random_streamed",
        "description": "Random LiveCodeBench LeetCode-style problems streamed from a small raw row pool.",
        "seed": args.seed,
        "stream_limit": args.stream_limit,
        "total_count": len(selected_ids),
        "compulsory_problem_ids": [],
        "livecodebench_count": len(selected_lcb),
        "problem_ids": selected_ids,
    }

    write_json(out_dir / "study_manifest.json", manifest)
    write_json(out_dir / "study_problem_ids.json", selected_ids)

    patched = False

    if args.patch_app_js:
        patched = patch_app_js(project_root, selected_ids)

    print("\nCreated study dataset:")

    for index, problem_id in enumerate(selected_ids, start=1):
        print(f"{index:02d}. {problem_id} [LCB]")

    print(f"\nManifest: {out_dir / 'study_manifest.json'}")
    print(f"Problem IDs: {out_dir / 'study_problem_ids.json'}")

    if args.patch_app_js:
        if patched:
            print("Patched frontend/app.js")
        else:
            print("Could not patch frontend/app.js automatically")


if __name__ == "__main__":
    main()