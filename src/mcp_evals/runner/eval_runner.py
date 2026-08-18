"""Eval runner — validates specs and reports readiness (LLM calls in next phase)."""

from dataclasses import dataclass, field

import structlog

from mcp_evals.models.spec import EvalSuite

log = structlog.get_logger()


@dataclass
class CaseResult:
    case_id: str
    status: str  # pending | pass | fail | skipped
    message: str = ""


@dataclass
class RunReport:
    suite_name: str
    case_results: list[CaseResult] = field(default_factory=list)
    mode: str = "dry-run"
    accuracy: float | None = None
    threshold: float | None = None

    @property
    def passed(self) -> bool:
        if self.accuracy is not None and self.threshold is not None:
            return self.accuracy >= self.threshold
        return all(r.status in {"pass", "skipped"} for r in self.case_results)


def validate_suite_structure(suite: EvalSuite) -> RunReport:
    """Validate eval suite structure without calling an LLM (MVP foundation)."""
    log.info("validating_suite", name=suite.name, cases=len(suite.cases))
    results: list[CaseResult] = []

    seen_ids: set[str] = set()
    for case in suite.cases:
        if case.id in seen_ids:
            results.append(
                CaseResult(case.id, "fail", f"Duplicate case id: {case.id}")
            )
            continue
        seen_ids.add(case.id)

        if not case.request.strip():
            results.append(CaseResult(case.id, "fail", "Empty request text."))
            continue
        if not case.expected_tool.name.strip():
            results.append(CaseResult(case.id, "fail", "Expected tool name is empty."))
            continue

        results.append(
            CaseResult(case.id, "skipped", "LLM evaluation not configured (dry-run).")
        )

    return RunReport(suite_name=suite.name, case_results=results, mode="dry-run")
