import json
import re
from copy import deepcopy
from typing import Any, Iterator

from app.workflow.exceptions import WorkflowValidationError


EXPRESSION = re.compile(r"\{\{\s*(.*?)\s*\}\}")
FULL_EXPRESSION = re.compile(r"^\s*\{\{\s*(.*?)\s*\}\}\s*$")
STEP_REFERENCE = re.compile(r"^steps\.([A-Za-z0-9_-]+)\.output(?:\.(.+))?$")


def iter_expressions(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield from (match.group(1).strip() for match in EXPRESSION.finditer(value))
    elif isinstance(value, dict):
        for nested in value.values():
            yield from iter_expressions(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_expressions(nested)


def referenced_step(expression: str) -> str | None:
    match = STEP_REFERENCE.fullmatch(expression)
    return match.group(1) if match else None


def resolve_inputs(
    mapping: dict[str, Any],
    *,
    results: dict[str, Any],
    runtime_inputs: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    return resolve_value(
        mapping,
        results=results,
        runtime_inputs=runtime_inputs,
        run_id=run_id,
    )


def resolve_value(
    value: Any,
    *,
    results: dict[str, Any],
    runtime_inputs: dict[str, Any],
    run_id: str,
) -> Any:
    if isinstance(value, dict):
        return {
            key: resolve_value(
                nested,
                results=results,
                runtime_inputs=runtime_inputs,
                run_id=run_id,
            )
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [
            resolve_value(
                nested,
                results=results,
                runtime_inputs=runtime_inputs,
                run_id=run_id,
            )
            for nested in value
        ]
    if not isinstance(value, str):
        return value

    full = FULL_EXPRESSION.fullmatch(value)
    if full:
        return deepcopy(_resolve_expression(full.group(1).strip(), results, runtime_inputs, run_id))

    def replace(match: re.Match[str]) -> str:
        resolved = _resolve_expression(match.group(1).strip(), results, runtime_inputs, run_id)
        if isinstance(resolved, (dict, list)):
            return json.dumps(resolved, ensure_ascii=False)
        return str(resolved)

    return EXPRESSION.sub(replace, value)


def _resolve_expression(
    expression: str,
    results: dict[str, Any],
    runtime_inputs: dict[str, Any],
    run_id: str,
) -> Any:
    if expression in {"run.id", "run_id"}:
        return run_id
    if expression.startswith("runtime."):
        return _read_path(runtime_inputs, expression.removeprefix("runtime."), expression)

    step_match = STEP_REFERENCE.fullmatch(expression)
    if step_match:
        node_id, path = step_match.groups()
        if node_id not in results:
            raise WorkflowValidationError(
                f"Expression references step '{node_id}' before it has produced output"
            )
        return _read_path(results[node_id], path, expression) if path else results[node_id]
    raise WorkflowValidationError(f"Unsupported expression '{{{{ {expression} }}}}'")


def _read_path(value: Any, path: str | None, expression: str) -> Any:
    current = value
    for segment in (path or "").split(".") if path else []:
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            raise WorkflowValidationError(
                f"Expression '{{{{ {expression} }}}}' cannot find '{segment}'"
            )
    return current
