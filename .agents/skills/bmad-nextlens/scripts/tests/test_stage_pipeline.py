from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "stage_pipeline.py"
SPEC = importlib.util.spec_from_file_location("bmad_nextlens_stage_pipeline", SCRIPT_PATH)
STAGE_PIPELINE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = STAGE_PIPELINE
SPEC.loader.exec_module(STAGE_PIPELINE)


def _pass(detail: str, **state_patch: object):
    return STAGE_PIPELINE.StageResult(status="pass", detail=detail, state_patch=dict(state_patch))


def test_new_pipeline_executes_stages_in_order_and_logs_transitions(tmp_path: Path) -> None:
    pipeline = STAGE_PIPELINE.NextLensStagePipeline(tmp_path)
    handlers = {
        stage: (lambda stage_name: lambda context: _pass(f"{stage_name} complete", last_stage=stage_name))(stage)
        for stage in STAGE_PIPELINE.NEW_STAGE_SEQUENCE
    }

    result = pipeline.run("new", handlers, context={"context_source": "path/to/context.yaml"})
    combined_output = "\n".join(result.output_lines)
    normalized_output = combined_output.replace("\n  ", " ")

    assert result.status == "complete"
    assert list(result.completed_stages) == list(STAGE_PIPELINE.NEW_STAGE_SEQUENCE)
    assert result.output_lines[0] == "[stage:intake]"
    assert "status=pass;" in result.output_lines[1]
    assert any("progress=Stage 1 of 10 complete" in line for line in result.output_lines)
    assert any(line == "[stage:route]" for line in result.output_lines)
    assert "[stage:route] status=pass;" in normalized_output
    assert "next_action=Pipeline complete." in normalized_output
    assert any("progress=Stage 10 of 10 complete" in line for line in result.output_lines)
    assert all("\u001b[" not in line for line in result.output_lines)
    assert [entry["stage"] for entry in result.evidence_bundle["stage_transitions"]] == list(
        STAGE_PIPELINE.NEW_STAGE_SEQUENCE
    )
    assert all(entry["status"] == "pass" for entry in result.evidence_bundle["stage_transitions"])
    assert result.resume_state["context"]["last_stage"] == "route"
    assert result.state_path is None


def test_blocking_stage_stops_pipeline_and_saves_resume_state(tmp_path: Path) -> None:
    pipeline = STAGE_PIPELINE.NextLensStagePipeline(tmp_path)
    calls: list[str] = []

    def make_handler(stage_name: str):
        def _handler(context: dict[str, object]) -> STAGE_PIPELINE.StageResult:
            calls.append(stage_name)
            if stage_name == "rank":
                return STAGE_PIPELINE.StageResult(
                    status="fail",
                    detail="ranking blocked by insufficient evidence",
                    next_action="return to discovery and enrich journey context",
                )
            return _pass(f"{stage_name} complete")

        return _handler

    handlers = {stage: make_handler(stage) for stage in STAGE_PIPELINE.NEW_STAGE_SEQUENCE}

    result = pipeline.run("new", handlers, context={"context_source": "path/to/context.yaml"})

    assert result.status == "blocked"
    assert list(result.completed_stages) == ["intake", "extract", "sufficiency"]
    assert calls == ["intake", "extract", "sufficiency", "rank"]
    assert result.current_stage == "rank"
    assert result.next_action == "return to discovery and enrich journey context"
    assert result.state_path == tmp_path / ".nextlens" / "pipeline-state.yaml"
    assert result.state_path.exists()
    assert any("status=fail;" in line for line in result.output_lines)
    assert any("rollback_action=No further stages were run; resume from saved state." in line for line in result.output_lines)
    assert any("diagnostic_stage=rank" in line for line in result.output_lines)
    assert any("progress=Stage 4 of 10 blocked" in line for line in result.output_lines)
    saved_text = result.state_path.read_text(encoding="utf-8")
    assert 'current_stage: "rank"' in saved_text
    assert 'next_action: "return to discovery and enrich journey context"' in saved_text


def test_resume_state_skips_completed_stages_after_interruption(tmp_path: Path) -> None:
    pipeline = STAGE_PIPELINE.NextLensStagePipeline(tmp_path)
    first_run_calls: list[str] = []

    def first_handler(stage_name: str):
        def _handler(context: dict[str, object]) -> STAGE_PIPELINE.StageResult:
            first_run_calls.append(stage_name)
            if stage_name == "confirm":
                raise STAGE_PIPELINE.PipelineInterrupted(
                    "operator paused before confirmation",
                    next_action="resume once confirmation input is available",
                )
            return _pass(f"{stage_name} complete")

        return _handler

    interrupted = pipeline.run(
        "new",
        {stage: first_handler(stage) for stage in STAGE_PIPELINE.NEW_STAGE_SEQUENCE},
        context={"context_source": "path/to/context.yaml"},
    )

    assert interrupted.status == "blocked"
    assert list(interrupted.completed_stages) == ["intake", "extract", "sufficiency", "rank"]

    resumed_calls: list[str] = []

    def resume_handler(stage_name: str):
        def _handler(context: dict[str, object]) -> STAGE_PIPELINE.StageResult:
            resumed_calls.append(stage_name)
            return _pass(f"{stage_name} complete")

        return _handler

    resumed = pipeline.run(
        "new",
        {stage: resume_handler(stage) for stage in STAGE_PIPELINE.NEW_STAGE_SEQUENCE},
        resume_state=interrupted.resume_state,
    )

    assert resumed.status == "complete"
    assert resumed_calls[0] == "confirm"
    assert "intake" not in resumed_calls
    assert "extract" not in resumed_calls
    assert "sufficiency" not in resumed_calls
    assert "rank" not in resumed_calls
    assert list(resumed.completed_stages) == list(STAGE_PIPELINE.NEW_STAGE_SEQUENCE)


def test_warning_and_wrapping_preserve_readable_status_output(tmp_path: Path) -> None:
    pipeline = STAGE_PIPELINE.NextLensStagePipeline(tmp_path, line_width=80)

    def make_handler(stage_name: str):
        def _handler(context: dict[str, object]) -> STAGE_PIPELINE.StageResult:
            if stage_name == "validate":
                return STAGE_PIPELINE.StageResult(
                    status="warning",
                    detail="doctor reported advisory findings that require operator review before final emit",
                    remediation_hints=(
                        "Review advisory findings and confirm the packet should proceed.",
                    ),
                )
            return _pass(f"{stage_name} complete")

        return _handler

    result = pipeline.run(
        "new",
        {stage: make_handler(stage) for stage in STAGE_PIPELINE.NEW_STAGE_SEQUENCE},
        context={"context_source": "path/to/context.yaml"},
    )

    warning_lines = [line for line in result.output_lines if "status=warning;" in line or "remediation_hint=" in line]
    assert warning_lines
    assert any("remediation_hint=Review advisory findings and confirm the packet should proceed." in line for line in warning_lines)
    assert all(len(line) <= 80 for line in warning_lines)
