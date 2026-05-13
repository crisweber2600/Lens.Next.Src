from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[6]
VALIDATOR = REPO_ROOT / "skills/bmad-lens-setup/assets/lens/scripts/validate_lens_assets.py"

spec = importlib.util.spec_from_file_location("validate_lens_assets", VALIDATOR)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def test_validate_lens_assets_passes_for_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--module-root", str(REPO_ROOT)],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {"status": "pass", "findings": []}


def write_relationship_contract(assets: Path) -> None:
    schema_dir = assets / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "relationship-types.yaml").write_text(
        yaml.safe_dump(
            {
                "relationship_types": ["serves"],
                "relationship_lifecycle": ["raw", "promoted"],
                "relationship_gates": ["discovery", "validation"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_relationship_contract_validation_flags_bad_relationships(tmp_path: Path) -> None:
    assets = tmp_path
    write_relationship_contract(assets)
    template_dir = assets / "templates"
    template_dir.mkdir()
    (template_dir / "bad-relationship.yaml").write_text(
        """
items:
  - id: rel.bad_type
    kind: relationship
    name: Bad Type
    status: raw
    confidence: low
    created_at: "2026-05-13"
    updated_at: "2026-05-13"
    source_refs: [source.fixture]
    relationships: []
    open_questions: []
    from: slice.one
    type: invented_type
    to: slice.two
    gates:
      discovery:
        status: pass
  - id: slice.bad_promoted
    kind: slice
    name: Bad Promoted Slice
    status: promoted
    confidence: low
    created_at: "2026-05-13"
    updated_at: "2026-05-13"
    source_refs: [source.fixture]
    relationships: []
    open_questions: []
""",
        encoding="utf-8",
    )

    findings: list[dict[str, str]] = []
    validator.validate_relationship_contract(assets, {"raw", "promoted"}, findings)
    messages = "\n".join(finding["message"] for finding in findings)
    assert "unknown type invented_type" in messages
    assert "missing gates ['validation']" in messages
    assert "relationship-only status promoted" in messages


def test_relationship_contract_requires_schema_to_allow_lifecycle(tmp_path: Path) -> None:
    assets = tmp_path
    write_relationship_contract(assets)

    findings: list[dict[str, str]] = []
    validator.validate_relationship_contract(assets, {"raw"}, findings)
    assert any("lifecycle state promoted" in finding["message"] for finding in findings)


def test_slice_contract_validation_requires_inline_acceptance_and_risks(tmp_path: Path) -> None:
    assets = tmp_path
    template_dir = assets / "templates"
    template_dir.mkdir(parents=True)
    (template_dir / "slice.yaml").write_text(
        """
slice:
  id: slice.incomplete
  kind: slice
  name: Incomplete Slice
  status: raw
  confidence: low
  created_at: "2026-05-13"
  updated_at: "2026-05-13"
  source_refs: [source.fixture]
  relationships: []
  open_questions: []
  scope:
    includes: []
    excludes: []
""",
        encoding="utf-8",
    )
    (template_dir / "acceptance-evidence.yaml").write_text("acceptance_evidence: []\n", encoding="utf-8")

    findings: list[dict[str, str]] = []
    validator.validate_slice_contract(assets, findings)
    messages = "\n".join(finding["message"] for finding in findings)
    assert "inline slice contract" in messages
    assert "must define inline acceptance_evidence list" in messages
    assert "must define inline risks list" in messages
