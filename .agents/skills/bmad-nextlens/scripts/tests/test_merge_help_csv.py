from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "bmad-nextlens-setup" / "scripts" / "merge-help-csv.py"
SPEC = importlib.util.spec_from_file_location("nextlens_merge_help_csv", SCRIPT_PATH)
MERGE_HELP = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MERGE_HELP
SPEC.loader.exec_module(MERGE_HELP)
HEADER = ",".join(MERGE_HELP.HEADER)


def test_merge_filters_current_bmad_rows_and_legacy_module_code_rows(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.csv"
    target = tmp_path / "module-help.csv"
    legacy_dir = tmp_path / "_bmad"
    (legacy_dir / "nxl").mkdir(parents=True)
    (legacy_dir / "nxl" / "module-help.csv").write_text("legacy\n", encoding="utf-8")
    source.write_text(
        HEADER
        + "\nNextLens Top-Down Bridge,bmad-nextlens,Setup NextLens,SN,Register,setup,,anytime,,,false,{project-root}/_bmad,config\n",
        encoding="utf-8",
    )
    target.write_text(
        HEADER
        + "\nNextLens Top-Down Bridge,bmad-nextlens,Old Setup,OS,Old,setup,,anytime,,,false,old,old\n"
        + "\nnxl,bmad-nextlens,old,old,old\n"
        + "\nOther Module,other-skill,Other,OT,Other,run,,anytime,,,false,other,other\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "merge-help-csv.py",
            "--target",
            str(target),
            "--source",
            str(source),
            "--legacy-dir",
            str(legacy_dir),
            "--module-code",
            "nxl",
        ],
    )

    assert MERGE_HELP.main() == 0
    text = target.read_text(encoding="utf-8")

    assert "Old Setup" not in text
    assert "nxl,bmad-nextlens,old,old,old" not in text
    assert "Other Module,other-skill" in text
    assert "NextLens Top-Down Bridge,bmad-nextlens,Setup NextLens" in text
    assert not (legacy_dir / "nxl" / "module-help.csv").exists()
