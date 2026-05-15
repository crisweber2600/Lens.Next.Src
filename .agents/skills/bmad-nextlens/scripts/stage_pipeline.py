"""Deterministic stage orchestration for the NextLens command spine."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from textwrap import wrap as textwrap_wrap
from typing import Any, Callable, Mapping


NEW_STAGE_SEQUENCE = (
    "intake",
    "sufficiency",
    "rank",
    "confirm",
    "write",
    "rebuild",
    "validate",
    "emit",
    "route",
)

VALID_STAGE_STATUSES = {"pass", "warning", "fail"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def _yaml_lines(value: Any, indent: int = 0) -> list[str]:
    pad = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.extend(_yaml_lines(item, indent + 2))
            else:
                lines.append(f"{pad}{key}: {_yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.extend(_yaml_lines(item, indent + 2))
            else:
                lines.append(f"{pad}- {_yaml_scalar(item)}")
        return lines
    return [f"{pad}{_yaml_scalar(value)}"]


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(_yaml_lines(dict(payload))) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class StageResult:
    status: str
    detail: str = ""
    next_action: str | None = None
    state_patch: dict[str, Any] = field(default_factory=dict)
    remediation_hints: tuple[str, ...] = ()
    diagnostic_context: dict[str, Any] = field(default_factory=dict)
    rollback_action: str | None = None

    def normalized_status(self) -> str:
        status = self.status.strip().lower()
        if status not in VALID_STAGE_STATUSES:
            raise ValueError(f"invalid stage status '{self.status}'")
        return status


@dataclass(frozen=True)
class PipelineExecution:
    mode: str
    status: str
    output_lines: tuple[str, ...]
    evidence_bundle: dict[str, Any]
    completed_stages: tuple[str, ...]
    current_stage: str | None
    next_action: str | None
    resume_state: dict[str, Any]
    state_path: Path | None


class PipelineInterrupted(RuntimeError):
    def __init__(self, detail: str, *, next_action: str | None = None):
        super().__init__(detail)
        self.next_action = next_action


StageHandler = Callable[[dict[str, Any]], StageResult]


class NextLensStagePipeline:
    def __init__(self, docs_path: str | Path, *, line_width: int = 80):
        self.docs_path = Path(docs_path)
        self.state_path = self.docs_path / ".nextlens" / "pipeline-state.yaml"
        self.line_width = line_width

    def run(
        self,
        mode: str,
        handlers: Mapping[str, StageHandler],
        *,
        context: Mapping[str, Any] | None = None,
        resume_state: Mapping[str, Any] | None = None,
    ) -> PipelineExecution:
        normalized_mode = (mode or "").strip().lower()
        if normalized_mode != "new":
            raise ValueError(f"unsupported pipeline mode '{mode}'")

        state = self._initial_state(normalized_mode, context or {}, resume_state)
        output_lines = list(state.get("output_lines", []))
        evidence_bundle = copy.deepcopy(state.get("evidence_bundle", {"stage_transitions": []}))
        completed_stages = list(state.get("completed_stages", []))
        current_stage = None

        for stage_index, stage_name in enumerate(NEW_STAGE_SEQUENCE, start=1):
            if stage_name in completed_stages:
                continue
            if stage_name not in handlers:
                raise ValueError(f"missing stage handler for '{stage_name}'")

            current_stage = stage_name
            output_lines.append(f"[stage:{stage_name}]")
            try:
                result = handlers[stage_name](copy.deepcopy(state["context"]))
            except PipelineInterrupted as exc:
                result = StageResult(
                    status="fail",
                    detail=str(exc),
                    next_action=exc.next_action or f"Resume pipeline from stage '{stage_name}'.",
                    diagnostic_context={"stage": stage_name, "reason": "interrupted"},
                    rollback_action="No further stages were run; resume from saved state.",
                )
            except Exception as exc:
                result = StageResult(
                    status="fail",
                    detail=f"{type(exc).__name__}: {exc}",
                    next_action=f"Resume pipeline from stage '{stage_name}' after fixing the blocking error.",
                    diagnostic_context={"stage": stage_name, "exception": type(exc).__name__},
                    rollback_action="No further stages were run; resume from saved state.",
                )

            status = result.normalized_status()
            detail = result.detail or stage_name
            timestamp = _utcnow_iso()
            next_stage = self._next_stage_name(stage_name)
            next_action = result.next_action or self._default_next_action(status, next_stage)
            diagnostic_context = dict(result.diagnostic_context)
            if status == "fail":
                diagnostic_context.setdefault("stage", stage_name)
            rollback_action = result.rollback_action
            if status == "fail" and not rollback_action:
                rollback_action = "No further stages were run; resume from saved state."
            output_lines.extend(
                self._format_status_lines(
                    stage_name=stage_name,
                    stage_index=stage_index,
                    status=status,
                    detail=detail,
                    next_action=next_action,
                    remediation_hints=result.remediation_hints,
                    diagnostic_context=diagnostic_context,
                    rollback_action=rollback_action,
                )
            )

            if status == "fail":
                persisted_state = self._build_resume_state(
                    state=state,
                    completed_stages=completed_stages,
                    current_stage=stage_name,
                    evidence_bundle=evidence_bundle,
                    output_lines=output_lines,
                    next_action=next_action,
                    last_error=detail,
                )
                _write_yaml(self.state_path, persisted_state)
                return PipelineExecution(
                    mode=normalized_mode,
                    status="blocked",
                    output_lines=tuple(output_lines),
                    evidence_bundle=evidence_bundle,
                    completed_stages=tuple(completed_stages),
                    current_stage=stage_name,
                    next_action=next_action,
                    resume_state=persisted_state,
                    state_path=self.state_path,
                )

            if result.state_patch:
                state["context"].update(copy.deepcopy(result.state_patch))

            completed_stages.append(stage_name)
            evidence_bundle["stage_transitions"].append(
                {
                    "stage": stage_name,
                    "status": status,
                    "timestamp": timestamp,
                }
            )

        final_state = self._build_resume_state(
            state=state,
            completed_stages=completed_stages,
            current_stage=None,
            evidence_bundle=evidence_bundle,
            output_lines=output_lines,
            next_action=None,
            last_error=None,
        )
        return PipelineExecution(
            mode=normalized_mode,
            status="complete",
            output_lines=tuple(output_lines),
            evidence_bundle=evidence_bundle,
            completed_stages=tuple(completed_stages),
            current_stage=None,
            next_action=None,
            resume_state=final_state,
            state_path=None,
        )

    def _default_next_action(self, status: str, next_stage: str | None) -> str:
        if status == "fail":
            return "Resume from saved state after resolving the blocking issue."
        if next_stage is None:
            return "Pipeline complete."
        return f"continue to {next_stage}"

    def _format_status_lines(
        self,
        *,
        stage_name: str,
        stage_index: int,
        status: str,
        detail: str,
        next_action: str,
        remediation_hints: tuple[str, ...],
        diagnostic_context: Mapping[str, Any],
        rollback_action: str | None,
    ) -> list[str]:
        progress_state = "complete" if status != "fail" else "blocked"
        base_line = f"[stage:{stage_name}] status={status}; message={detail}; next_action={next_action}"
        lines = self._wrap_line(base_line)
        lines.extend(self._wrap_line(f"progress=Stage {stage_index} of {len(NEW_STAGE_SEQUENCE)} {progress_state}"))
        for hint in remediation_hints:
            lines.extend(self._wrap_line(f"remediation_hint={hint}", indent="  "))
        if rollback_action:
            lines.extend(self._wrap_line(f"rollback_action={rollback_action}", indent="  "))
        for key, value in diagnostic_context.items():
            lines.extend(self._wrap_line(f"diagnostic_{key}={value}", indent="  "))
        return lines

    def _next_stage_name(self, stage_name: str) -> str | None:
        try:
            stage_index = NEW_STAGE_SEQUENCE.index(stage_name)
        except ValueError:
            return None
        next_index = stage_index + 1
        if next_index >= len(NEW_STAGE_SEQUENCE):
            return None
        return NEW_STAGE_SEQUENCE[next_index]

    def _wrap_line(self, line: str, indent: str = "  ") -> list[str]:
        return textwrap_wrap(
            line,
            width=self.line_width,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [line]

    def _initial_state(
        self,
        mode: str,
        context: Mapping[str, Any],
        resume_state: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if resume_state:
            state = copy.deepcopy(dict(resume_state))
            state.setdefault("context", {}).update(copy.deepcopy(dict(context)))
            state.setdefault("mode", mode)
            return state
        return {
            "mode": mode,
            "context": copy.deepcopy(dict(context)),
            "completed_stages": [],
            "output_lines": [],
            "evidence_bundle": {"stage_transitions": []},
        }

    def _build_resume_state(
        self,
        *,
        state: Mapping[str, Any],
        completed_stages: list[str],
        current_stage: str | None,
        evidence_bundle: Mapping[str, Any],
        output_lines: list[str],
        next_action: str | None,
        last_error: str | None,
    ) -> dict[str, Any]:
        return {
            "mode": state["mode"],
            "completed_stages": list(completed_stages),
            "current_stage": current_stage,
            "next_action": next_action,
            "last_error": last_error,
            "last_checkpoint": _utcnow_iso(),
            "context": copy.deepcopy(dict(state["context"])),
            "evidence_bundle": copy.deepcopy(dict(evidence_bundle)),
            "output_lines": list(output_lines),
            "state_path": str(self.state_path),
        }