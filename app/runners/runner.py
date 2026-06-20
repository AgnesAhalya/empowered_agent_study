import re


def run_function_tests(code: str, problem: dict):
    namespace = {"re": re}

    safe_builtins = {
        "True": True,
        "False": False,
        "None": None,
        "len": len,
        "range": range,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "enumerate": enumerate,
        "reversed": reversed,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "all": all,
        "any": any,
        "sorted": sorted,
        "ord": ord,
        "chr": chr,
        "__import__": __import__,
    }

    try:
        exec(code, {"__builtins__": safe_builtins, "re": re}, namespace)
    except Exception as e:
        return {
            "passed": False,
            "error": f"Code execution error: {str(e)}",
            "results": [],
        }

    function_name = problem["function_name"]

    if function_name not in namespace:
        return {
            "passed": False,
            "error": f"Function {function_name} was not defined.",
            "results": [],
        }

    fn = namespace[function_name]
    results = []

    for test in problem["tests"]:
        args = test.get("args", [])
        kwargs = test.get("kwargs", {})
        expected = test["expected"]

        try:
            actual = fn(*args, **kwargs)
            passed = actual == expected
        except Exception as e:
            actual = f"Error: {str(e)}"
            passed = False

        results.append(
            {
                "args": args,
                "kwargs": kwargs,
                "expected": expected,
                "actual": actual,
                "passed": passed,
            }
        )

    return {
        "passed": all(item["passed"] for item in results),
        "error": None,
        "results": results,
    }
