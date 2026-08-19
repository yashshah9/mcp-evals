"""Behavioral eval runner: mock matcher and OpenAI-compatible tool calling."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Protocol

import structlog

from mcp_evals.errors import EvalRunError
from mcp_evals.models.spec import EvalSuite, ToolCatalog, ToolDefinition
from mcp_evals.runner.eval_runner import CaseResult, RunReport

log = structlog.get_logger()


class ToolSelector(Protocol):
    def select(self, request: str, tools: list[ToolDefinition]) -> tuple[str, dict[str, object]]:
        ...


class KeywordSelector:
    """Deterministic selector for CI: highest token overlap with tool name+description."""

    def select(self, request: str, tools: list[ToolDefinition]) -> tuple[str, dict[str, object]]:
        request_tokens = {w.lower() for w in request.replace("_", " ").split() if len(w) > 2}
        if not tools:
            raise EvalRunError("No tools available for selection.")
        best = tools[0]
        best_score = -1
        for tool in tools:
            blob = f"{tool.name} {tool.description}".replace("_", " ")
            tokens = {w.lower() for w in blob.split()}
            score = len(request_tokens & tokens)
            if score > best_score:
                best = tool
                best_score = score
        return best.name, {}


class OpenAICompatibleSelector:
    """Call an OpenAI-compatible /chat/completions endpoint with tools."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def select(self, request: str, tools: list[ToolDefinition]) -> tuple[str, dict[str, object]]:
        import urllib.error
        import urllib.request

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": request}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters or {"type": "object", "properties": {}},
                    },
                }
                for tool in tools
            ],
            "tool_choice": "auto",
        }
        data = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise EvalRunError(f"LLM request failed: {exc}") from exc

        message = body["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            raise EvalRunError("Model returned no tool call.")
        fn = calls[0]["function"]
        args: dict[str, object] = {}
        raw_args = fn.get("arguments") or "{}"
        if isinstance(raw_args, str):
            parsed = json.loads(raw_args or "{}")
            if isinstance(parsed, dict):
                args = parsed
        elif isinstance(raw_args, dict):
            args = raw_args
        return str(fn["name"]), args


@dataclass
class EvalMetrics:
    selection_accuracy: float
    argument_validity: float
    cases: int
    samples: int
    latency_ms_total: int = 0


@dataclass
class SampledCaseResult(CaseResult):
    expected_tool: str = ""
    actual_tool: str = ""
    latency_ms: int = 0
    samples_passed: int = 0
    samples_total: int = 1


def run_eval_suite(
    suite: EvalSuite,
    catalog: ToolCatalog,
    selector: ToolSelector,
    samples: int = 1,
    pass_threshold: float | None = None,
) -> tuple[RunReport, EvalMetrics]:
    """Run each case `samples` times; pass if majority selects the expected tool."""
    threshold = pass_threshold if pass_threshold is not None else suite.pass_threshold
    results: list[CaseResult] = []
    passed_cases = 0
    arg_ok = 0
    arg_scored = 0
    latency_total = 0
    n = max(1, samples)

    for case in suite.cases:
        hits = 0
        last_tool = ""
        last_args: dict[str, object] = {}
        case_latency = 0
        for _ in range(n):
            start = time.monotonic()
            actual, args = selector.select(case.request, catalog.tools)
            case_latency += int((time.monotonic() - start) * 1000)
            last_tool, last_args = actual, args
            if actual == case.expected_tool.name:
                hits += 1
        latency_total += case_latency
        selected = hits * 2 >= n
        if selected:
            passed_cases += 1
        # Skip arg scoring when the selector did not attempt arguments (mock).
        if last_args or not case.expected_tool.arguments:
            arg_scored += 1
            if _args_valid(case.expected_tool.arguments, last_args):
                arg_ok += 1
        status = "pass" if selected else "fail"
        message = (
            f"expected={case.expected_tool.name} actual={last_tool} "
            f"samples={hits}/{n}"
        )
        results.append(
            SampledCaseResult(
                case_id=case.id,
                status=status,
                message=message,
                expected_tool=case.expected_tool.name,
                actual_tool=last_tool,
                latency_ms=case_latency,
                samples_passed=hits,
                samples_total=n,
            )
        )

    total = max(1, len(suite.cases))
    metrics = EvalMetrics(
        selection_accuracy=passed_cases / total,
        argument_validity=(arg_ok / arg_scored) if arg_scored else 1.0,
        cases=len(suite.cases),
        samples=n,
        latency_ms_total=latency_total,
    )
    report = RunReport(
        suite_name=suite.name,
        case_results=results,
        mode="eval",
        accuracy=metrics.selection_accuracy,
        threshold=threshold,
    )
    log.info(
        "eval_complete",
        accuracy=metrics.selection_accuracy,
        threshold=threshold,
        cases=metrics.cases,
    )
    return report, metrics


def _args_valid(expected: dict[str, object], actual: dict[str, object]) -> bool:
    if not expected:
        return True
    return all(actual.get(k) == v for k, v in expected.items())
