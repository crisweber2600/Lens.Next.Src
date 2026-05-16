from __future__ import annotations

import csv
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = MODULE_ROOT.parent
MODULE_HELP_PATH = SKILLS_ROOT / "bmad-nextlens-setup" / "assets" / "module-help.csv"
EXPECTED_HEADER = [
    "module",
    "skill",
    "display-name",
    "menu-code",
    "description",
    "action",
    "args",
    "phase",
    "after",
    "before",
    "required",
    "output-location",
    "outputs",
]


def test_module_help_csv_has_required_header_and_actions() -> None:
    rows = _rows()

    assert list(rows[0].keys()) == EXPECTED_HEADER
    assert [row["action"] for row in rows] == ["configure", "new", "doctor", "validate", "salmon"]
    assert [row["skill"] for row in rows] == [
        "bmad-nextlens-setup",
        "bmad-nextlens-new",
        "bmad-nextlens-doctor",
        "bmad-nextlens-validate",
        "bmad-nextlens-salmon",
    ]
    assert {row["menu-code"] for row in rows} == {"SN", "NF", "ND", "NV", "NS"}


def test_module_help_csv_registers_expected_action_metadata() -> None:
    rows = {row["action"]: row for row in _rows()}

    assert rows["configure"] == {
        "module": "NextLens Top-Down Bridge",
        "skill": "bmad-nextlens-setup",
        "display-name": "Setup NextLens",
        "menu-code": "SN",
        "description": "Register or refresh the NextLens BMad module in this project.",
        "action": "configure",
        "args": "{-H: headless mode}|{setup|configure}",
        "phase": "anytime",
        "after": "",
        "before": "bmad-nextlens-new:new",
        "required": "true",
        "output-location": "{project-root}/_bmad",
        "outputs": "config.yaml and module-help.csv",
    }
    assert rows["new"]["display-name"] == "Create Feature Packet"
    assert rows["new"]["args"] == "{context_source: discovery context path}|{docs_path: optional docs root}"
    assert rows["new"]["after"] == "bmad-nextlens-setup:configure"
    assert rows["new"]["before"] == "bmad-nextlens-doctor:doctor"
    assert rows["doctor"]["output-location"] == "nextlens_docs_path"
    assert rows["doctor"]["after"] == "bmad-nextlens-new:new"
    assert rows["doctor"]["before"] == "bmad-nextlens-validate:validate"
    assert rows["validate"]["display-name"] == "Run Post-BMAD Validation"
    assert rows["validate"]["description"] == "Run governed post-BMAD validation on implementation evidence; not Doctor."
    assert rows["validate"]["args"] == "{packet_source: packet path}|{implementation_evidence_source: implementation evidence path}|{bmad_artifacts_source: optional BMAD artifact bundle path}|{docs_path: optional docs root}"
    assert rows["validate"]["after"] == "bmad-nextlens-doctor:doctor"
    assert rows["validate"]["before"] == "bmad-nextlens-salmon:salmon"
    assert rows["validate"]["outputs"] == "post-BMAD validation report"
    assert rows["salmon"]["output-location"] == "nextlens_landscape_store"
    assert rows["salmon"]["after"] == "bmad-nextlens-validate:validate"


def test_module_help_references_only_existing_capabilities() -> None:
    rows = _rows()
    refs = {f"{row['skill']}:{row['action']}" for row in rows}

    for row in rows:
        for field_name in ("after", "before"):
            value = row[field_name]
            if value:
                assert value in refs


def _rows() -> list[dict[str, str]]:
    with MODULE_HELP_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
