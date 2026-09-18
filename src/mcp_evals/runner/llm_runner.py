"""Behavioral eval runner: mock matcher and OpenAI-compatible tool calling."""

from __future__ import annotations

import json
import re
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
    """Deterministic CI selector: token overlap for tool name + inferred args.

    Argument inference is heuristic (schema property names + request text). Good
    enough to score ``expected_tool.arguments`` in mock CI without an LLM.
    """

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
        return best.name, _infer_arguments(request, best)


_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "at",
        "for",
        "from",
        "with",
        "by",
        "about",
        "find",
        "get",
        "fetch",
        "search",
        "return",
        "please",
        "me",
        "my",
        "using",
        "into",
        "that",
        "this",
        "those",
        "these",
        "document",
        "documents",
        "tool",
        "call",
    }
)


def _infer_arguments(request: str, tool: ToolDefinition) -> dict[str, object]:
    """Fill tool args from the request using parameter schema hints."""
    params = tool.parameters if isinstance(tool.parameters, dict) else {}
    props = params.get("properties")
    if not isinstance(props, dict) or not props:
        return {}
    required = params.get("required")
    keys: list[str]
    if isinstance(required, list) and required:
        keys = [str(k) for k in required if str(k) in props]
    else:
        keys = [str(k) for k in props]
    args: dict[str, object] = {}
    for key in keys:
        schema = props.get(key)
        typ = "string"
        if isinstance(schema, dict) and isinstance(schema.get("type"), str):
            typ = schema["type"]
        value = _extract_arg_value(request, key, typ, tool)
        if value is not None:
            args[key] = value
    return args


def _extract_arg_value(
    request: str, key: str, typ: str, tool: ToolDefinition
) -> object | None:
    key_l = key.lower()
    # Quoted string wins for string-like fields
    quoted = _first_quoted(request)
    if typ in {"string", "number", "integer"} and quoted is not None and (
        "query" in key_l or key_l == "q" or "name" in key_l or "city" in key_l or "text" in key_l
    ):
        return quoted if typ == "string" else _coerce_number(quoted, typ)

    if "id" in key_l:
        ident = _extract_id_token(request)
        if ident is not None:
            return ident

    if typ in {"integer", "number"}:
        num = _first_number(request)
        if num is not None:
            return int(num) if typ == "integer" and num == int(num) else num

    if typ == "string" or typ not in {"integer", "number", "boolean", "array", "object"}:
        # "about X" / "for X" / "in X"
        for marker in (" about ", " for ", " in ", " named ", " called "):
            idx = request.lower().find(marker)
            if idx >= 0:
                tail = request[idx + len(marker) :].strip().strip(".,?!")
                if tail:
                    return tail
        return _residual_phrase(request, tool)
    return None


def _first_quoted(text: str) -> str | None:
    for quote in ('"', "'"):
        if quote in text:
            parts = text.split(quote)
            if len(parts) >= 3 and parts[1].strip():
                return parts[1].strip()
    return None


def _extract_id_token(text: str) -> str | None:
    match = re.search(r"\b([A-Za-z]+[-_]\d+)\b", text)
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{3,})\b", text)
    if match:
        return match.group(1)
    return None


def _first_number(text: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    raw = match.group(0)
    return float(raw) if "." in raw else float(int(raw))


def _coerce_number(raw: str, typ: str) -> object | None:
    try:
        if typ == "integer":
            return int(float(raw))
        return float(raw)
    except ValueError:
        return None


def _residual_phrase(request: str, tool: ToolDefinition) -> str | None:
    name_tokens = {w.lower() for w in tool.name.replace("_", " ").split() if w}
    kept: list[str] = []
    for token in request.replace("_", " ").split():
        clean = token.strip(".,?!:;\"'").lower()
        if not clean or clean in _STOPWORDS or clean in name_tokens:
            continue
        kept.append(token.strip(".,?!:;\"'"))
    return " ".join(kept) if kept else None


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
    """Run each case `samples` times; pass if majority selects the expected tool
    (and arguments match when ``expected_tool.arguments`` is set)."""
    threshold = pass_threshold if pass_threshold is not None else suite.pass_threshold
    results: list[CaseResult] = []
    passed_cases = 0
    arg_ok = 0
    arg_scored = 0
    latency_total = 0
    n = max(1, samples)

    for case in suite.cases:
        hits = 0
        arg_hits = 0
        last_tool = ""
        last_args: dict[str, object] = {}
        case_latency = 0
        expect_args = case.expected_tool.arguments
        for _ in range(n):
            start = time.monotonic()
            actual, args = selector.select(case.request, catalog.tools)
            case_latency += int((time.monotonic() - start) * 1000)
            last_tool, last_args = actual, args
            tool_ok = actual == case.expected_tool.name
            if tool_ok:
                hits += 1
            if expect_args:
                if tool_ok and _args_valid(expect_args, args):
                    arg_hits += 1
            elif tool_ok:
                arg_hits += 1
        latency_total += case_latency
        selected = hits * 2 >= n
        args_ok = True
        if expect_args:
            arg_scored += 1
            # Majority of samples must match expected args (not just the last draw).
            args_ok = arg_hits * 2 >= n
            if args_ok:
                arg_ok += 1
        elif last_args:
            arg_scored += 1
            arg_ok += 1
        case_passed = selected and args_ok
        if case_passed:
            passed_cases += 1
        status = "pass" if case_passed else "fail"
        arg_note = ""
        if expect_args:
            arg_note = (
                " args=ok"
                if args_ok
                else f" args={last_args!r}"
            )
        message = (
            f"expected={case.expected_tool.name} actual={last_tool} "
            f"samples={hits}/{n}{arg_note}"
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
