#!/usr/bin/env python3
"""Validate LENS module source assets beyond the generic BMAD module checks."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

REQUIRED_SKILLS = [
    'bmad-lens-setup','bmad-lens-help','bmad-lens-intake','bmad-lens-slice-new','bmad-lens-slice-frame','bmad-lens-slice-scope','bmad-lens-detect-adjacency','bmad-lens-detect-repetition','bmad-lens-suggest-promotion','bmad-lens-discover','bmad-lens-capture','bmad-lens-synthesize','bmad-lens-context-check','bmad-lens-research-plan','bmad-lens-map-system','bmad-lens-map-outcomes','bmad-lens-map-loops','bmad-lens-map-journeys','bmad-lens-slice-journey','bmad-lens-map-capabilities','bmad-lens-analyze-impact','bmad-lens-promote-landscape','bmad-lens-map-rebuild','bmad-lens-prepare-bmad','bmad-lens-sync-bmad','bmad-lens-guard-story','bmad-lens-validate-slice','bmad-lens-validate-journey','bmad-lens-validate-outcome','bmad-lens-salmon','bmad-lens-doctor','bmad-lens-auspex'
]
REQUIRED_ENTITIES = ['system','system_thesis','discovery_epoch','session','source','extraction','slice','artifact','adjacency','relationship','role','stakeholder','outcome','operating_loop','journey','journey_step','capability','domain','service','workstream','program','decision','assumption','unknown','risk','evidence','impact_map','promotion_gate','story','implementation_evidence','salmon_signal','auspex_status','bmad_packet','validation_result']
REQUIRED_TEMPLATES = ['slice.yaml','discovery-epoch.yaml','relationship.yaml','promotion-gate.yaml','impact-map.yaml','bmad-packet.yaml','bmad-packet.md','context-sufficiency.md','story-guard.yaml','salmon-signal.yaml','validation-result.yaml','doctor-report.md','auspex-status.yaml','journey.yaml','journey.md','journey-map.mmd','project-context.md']
REQUIRED_FIXTURES = {
    'fixtures/top-down/evidence-visible-to-teacher': ['slice.yaml', 'journey.yaml', 'impact-map.yaml'],
    'fixtures/bottom-up/download-model-images': ['slice.yaml', 'adjacency.yaml', 'promotion-gate.yaml'],
}
REQUIRED_TESTS = [
    'scripts/tests/test_lens_artifact_ops.py',
    'scripts/tests/test_validate_lens_assets.py',
]
REQUIRED_METADATA = ['id', 'kind', 'name', 'status', 'confidence', 'created_at', 'updated_at', 'source_refs', 'relationships', 'open_questions']
SEMANTIC_ROOTS = ['templates', 'fixtures']
REQUIRED_EVAL_IDS = {
    'top_down_routes_to_discovery',
    'bottom_up_remains_slice',
    'relationship_contract_validation',
    'repeated_pressure_promotion_candidate',
    'focused_bmad_packet',
    'guard_story_traceability',
    'salmon_upstream_impact',
    'doctor_invalid_topology',
    'auspex_read_only_status',
}


def fail(findings, category, message):
    findings.append({'category': category, 'message': message})


def yaml_docs(path: Path):
    if path.suffix not in {'.yaml', '.yml'}:
        return []
    return [doc for doc in yaml.safe_load_all(path.read_text(encoding='utf-8')) if doc]


def iter_dicts(data):
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from iter_dicts(value)
    elif isinstance(data, list):
        for value in data:
            yield from iter_dicts(value)


def manifest_skills(root: Path) -> list[str]:
    marketplace = root / '.claude-plugin' / 'marketplace.json'
    if not marketplace.is_file():
        return REQUIRED_SKILLS
    data = json.loads(marketplace.read_text(encoding='utf-8'))
    skills = []
    for plugin in data.get('plugins', []):
        if plugin.get('name') == 'lens':
            for path in plugin.get('skills', []):
                skills.append(Path(path).name)
    return skills or REQUIRED_SKILLS


def iter_asset_items(assets: Path):
    for semantic_root in SEMANTIC_ROOTS:
        root = assets / semantic_root
        if not root.exists():
            continue
        for path in sorted(root.rglob('*.yaml')):
            for doc in yaml_docs(path):
                for item in iter_dicts(doc):
                    yield path, item


def load_relationship_contract(assets: Path, findings) -> dict[str, set[str]]:
    path = assets / 'schemas' / 'relationship-types.yaml'
    if not path.is_file():
        fail(findings, 'relationship-contract', 'missing schemas/relationship-types.yaml')
        return {'types': set(), 'lifecycle': set(), 'gates': set()}
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    contract = {
        'types': set(data.get('relationship_types') or []),
        'lifecycle': set(data.get('relationship_lifecycle') or []),
        'gates': set(data.get('relationship_gates') or []),
    }
    for key, values in contract.items():
        if not values:
            fail(findings, 'relationship-contract', f'relationship-types.yaml missing {key}')
    return contract


def validate_relationship_contract(assets: Path, statuses: set[str], findings) -> None:
    contract = load_relationship_contract(assets, findings)
    relationship_types = contract['types']
    relationship_lifecycle = contract['lifecycle']
    relationship_gates = contract['gates']

    for state in sorted(relationship_lifecycle):
        if state not in statuses:
            fail(findings, 'relationship-contract', f'relationship lifecycle state {state} is not allowed by lens-entity.schema.json status enum')

    for path, item in iter_asset_items(assets):
        if 'id' not in item:
            continue
        kind = item.get('kind')
        status = item.get('status')
        if status == 'promoted' and kind != 'relationship':
            fail(findings, 'relationship-contract', f'{path} entity {item.get("id")} uses relationship-only status promoted')
        if kind != 'relationship':
            continue
        rel_type = item.get('type')
        if rel_type not in relationship_types:
            fail(findings, 'relationship-contract', f'{path} relationship {item.get("id")} uses unknown type {rel_type}')
        if status not in relationship_lifecycle:
            fail(findings, 'relationship-contract', f'{path} relationship {item.get("id")} uses non-lifecycle status {status}')
        gates = item.get('gates')
        if not isinstance(gates, dict):
            fail(findings, 'relationship-contract', f'{path} relationship {item.get("id")} missing gates map')
            continue
        missing_gates = relationship_gates - set(gates)
        unknown_gates = set(gates) - relationship_gates
        if missing_gates:
            fail(findings, 'relationship-contract', f'{path} relationship {item.get("id")} missing gates {sorted(missing_gates)}')
        if unknown_gates:
            fail(findings, 'relationship-contract', f'{path} relationship {item.get("id")} uses unknown gates {sorted(unknown_gates)}')


def validate_slice_contract(assets: Path, findings) -> None:
    for stale_name in ['acceptance-evidence.yaml', 'risks.yaml']:
        for path in sorted((assets / 'templates').rglob(stale_name)) + sorted((assets / 'fixtures').rglob(stale_name)):
            fail(findings, 'slice-contract', f'{path} violates canonical inline slice contract; keep acceptance_evidence and risks in slice.yaml')

    for path, item in iter_asset_items(assets):
        if item.get('kind') != 'slice':
            continue
        scope = item.get('scope')
        if not isinstance(scope, dict):
            fail(findings, 'slice-contract', f'{path} slice {item.get("id")} missing scope map')
        else:
            for key in ['includes', 'excludes']:
                if not isinstance(scope.get(key), list):
                    fail(findings, 'slice-contract', f'{path} slice {item.get("id")} scope.{key} must be a list')
        for key in ['acceptance_evidence', 'risks']:
            if not isinstance(item.get(key), list):
                fail(findings, 'slice-contract', f'{path} slice {item.get("id")} must define inline {key} list')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--module-root', default='.')
    args = parser.parse_args()
    root = Path(args.module_root)
    findings = []
    skills = root / 'skills'
    setup = skills / 'bmad-lens-setup'
    assets = setup / 'assets' / 'lens'
    required_skills = manifest_skills(root)

    for skill in required_skills:
        if not (skills / skill / 'SKILL.md').is_file():
            fail(findings, 'skills', f'missing skill {skill}')

    help_csv = setup / 'assets' / 'module-help.csv'
    if help_csv.is_file():
        rows = list(csv.DictReader(help_csv.open(encoding='utf-8')))
        csv_skills = {r.get('skill','') for r in rows}
        for skill in required_skills:
            if skill not in csv_skills:
                fail(findings, 'module-help', f'missing help entry for {skill}')
        codes = {}
        for r in rows:
            code = r.get('menu-code','')
            if code in codes:
                fail(findings, 'module-help', f'duplicate menu code {code}')
            codes[code] = r.get('skill','')
    else:
        fail(findings, 'module-help', 'missing setup assets/module-help.csv')

    module_yaml = setup / 'assets' / 'module.yaml'
    if not module_yaml.is_file():
        fail(findings, 'module', 'missing setup assets/module.yaml')
    else:
        module_text = module_yaml.read_text(encoding='utf-8')
        if 'code: lens' not in module_text:
            fail(findings, 'module', 'module.yaml must use code: lens')
        if '_bmad-output/lens/validation"' not in module_text:
            fail(findings, 'module', 'module.yaml must use _bmad-output/lens/validation as primary validation path')

    marketplace = root / '.claude-plugin' / 'marketplace.json'
    if marketplace.is_file():
        data = json.loads(marketplace.read_text(encoding='utf-8'))
        text = json.dumps(data)
        for skill in required_skills:
            if f'./skills/{skill}' not in text:
                fail(findings, 'marketplace', f'marketplace missing {skill}')
    else:
        fail(findings, 'marketplace', 'missing .claude-plugin/marketplace.json')

    schema_path = assets / 'schemas' / 'lens-entity.schema.json'
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding='utf-8'))
        entities = set(schema.get('properties', {}).get('kind', {}).get('enum', []))
        statuses = set(schema.get('properties', {}).get('status', {}).get('enum', []))
        for entity in REQUIRED_ENTITIES:
            if entity not in entities:
                fail(findings, 'schema', f'missing entity {entity}')
    else:
        fail(findings, 'schema', 'missing lens-entity.schema.json')
        entities = set()
        statuses = set()

    for template in REQUIRED_TEMPLATES:
        if not (assets / 'templates' / template).is_file():
            fail(findings, 'templates', f'missing template {template}')

    for semantic_root in SEMANTIC_ROOTS:
        for path in sorted((assets / semantic_root).rglob('*.yaml')):
            for doc in yaml_docs(path):
                for item in iter_dicts(doc):
                    if 'id' not in item:
                        continue
                    kind = item.get('kind')
                    status = item.get('status')
                    if kind and kind not in entities:
                        fail(findings, 'semantic', f'{path} uses kind {kind} not allowed by schema')
                    if status and status not in statuses:
                        fail(findings, 'semantic', f'{path} uses status {status} not allowed by schema')
                    if kind in {'relationship', 'promotion_gate', 'impact_map', 'validation_result', 'salmon_signal', 'bmad_packet', 'slice', 'journey', 'discovery_epoch', 'story'}:
                        for key in REQUIRED_METADATA:
                            if key not in item:
                                fail(findings, 'semantic', f'{path} entity {item.get("id")} missing metadata key {key}')

    validate_relationship_contract(assets, statuses, findings)
    validate_slice_contract(assets, findings)

    directory_map = assets / 'schemas' / 'directory-map.yaml'
    if directory_map.is_file():
        text = directory_map.read_text(encoding='utf-8')
        if '_bmad-output/lens/validation' not in text:
            fail(findings, 'schemas', 'directory-map missing primary validation path')
        if '_bmad-output/lens/archive/validation-results' not in text:
            fail(findings, 'schemas', 'directory-map missing validation archive path')
    else:
        fail(findings, 'schemas', 'missing directory-map.yaml')

    for fixture_root, files in REQUIRED_FIXTURES.items():
        for file_name in files:
            if not (assets / fixture_root / file_name).is_file():
                fail(findings, 'fixtures', f'missing {fixture_root}/{file_name}')

    top_down = assets / 'fixtures' / 'top-down' / 'evidence-visible-to-teacher'
    for file_name in ['discovery-epoch.yaml', 'bmad-packet.yaml', 'bmad-packet.md', 'story-guard.yaml', 'validation-result.yaml', 'salmon-signal.yaml']:
        if not (top_down / file_name).is_file():
            fail(findings, 'fixtures', f'missing top-down evidence-visible-to-teacher/{file_name}')

    packet_yaml = assets / 'templates' / 'bmad-packet.yaml'
    packet_md = assets / 'templates' / 'bmad-packet.md'
    if packet_yaml.is_file() and packet_md.is_file():
        packet_text = packet_yaml.read_text(encoding='utf-8') + '\n' + packet_md.read_text(encoding='utf-8')
        for phrase in ['active_slice', 'included_scope', 'explicit_exclusions', 'required_capabilities', 'required_decisions', 'risks', 'acceptance_evidence', 'recommended_bmad_next_step']:
            if phrase not in packet_text and phrase.replace('_', ' ').title() not in packet_text:
                fail(findings, 'templates', f'BMAD packet templates missing {phrase}')

    for test_path in REQUIRED_TESTS:
        if not (assets / test_path).is_file():
            fail(findings, 'tests', f'missing {test_path}')

    for setup_test in [
        root / 'skills' / 'bmad-lens-setup' / 'scripts' / 'tests' / 'test_merge_config.py',
        root / 'skills' / 'bmad-lens-setup' / 'scripts' / 'tests' / 'test_merge_help_csv.py',
        root / 'skills' / 'bmad-lens-setup' / 'scripts' / 'tests' / 'test_cleanup_legacy.py',
    ]:
        if not setup_test.is_file():
            fail(findings, 'tests', f'missing {setup_test.relative_to(root)}')

    evals = assets / 'evals' / 'lens-evals.yaml'
    if evals.is_file():
        text = evals.read_text(encoding='utf-8')
        eval_data = yaml.safe_load(text) or {}
        asset_eval_ids = {str(item.get('id', '')).removeprefix('lens.eval.') for item in eval_data.get('evals', [])}
        if text.count('id: lens.eval.') < 8:
            fail(findings, 'evals', 'expected at least 8 eval cases')
        for eval_id in sorted(REQUIRED_EVAL_IDS - asset_eval_ids):
            fail(findings, 'evals', f'lens-evals.yaml missing required eval {eval_id}')
    else:
        fail(findings, 'evals', 'missing lens-evals.yaml')

    runner_evals = root / 'evals' / 'lens' / 'evals.json'
    runner_triggers = root / 'evals' / 'lens' / 'triggers.json'
    if runner_evals.is_file():
        data = json.loads(runner_evals.read_text(encoding='utf-8'))
        runner_eval_ids = {item.get('id') for item in data.get('evals', [])}
        if len(data.get('evals', [])) < 8:
            fail(findings, 'evals', 'evals/lens/evals.json must contain at least 8 evals')
        for eval_id in sorted(REQUIRED_EVAL_IDS - runner_eval_ids):
            fail(findings, 'evals', f'evals/lens/evals.json missing required eval {eval_id}')
    else:
        fail(findings, 'evals', 'missing evals/lens/evals.json')
    if runner_triggers.is_file():
        triggers = json.loads(runner_triggers.read_text(encoding='utf-8'))
        if not any(item.get('should_trigger') is False for item in triggers):
            fail(findings, 'evals', 'triggers.json should include at least one negative trigger')
    else:
        fail(findings, 'evals', 'missing evals/lens/triggers.json')

    project_context = root / '_bmad-output' / 'project-context.md'
    if not project_context.is_file():
        fail(findings, 'project-context', 'missing _bmad-output/project-context.md')
    else:
        pc = project_context.read_text(encoding='utf-8')
        for phrase in ['Traceability Rule', 'Scope Rule', 'Architecture Rule', 'Change Rule']:
            if phrase not in pc:
                fail(findings, 'project-context', f'missing {phrase}')

    forbidden_dirs = [p for p in root.rglob('*') if p.is_dir() and 'NorthStarET' in p.name]
    if forbidden_dirs:
        fail(findings, 'northstar', f'forbidden NorthStarET directory found: {forbidden_dirs[0]}')

    result = {'status': 'pass' if not findings else 'fail', 'findings': findings}
    print(json.dumps(result, indent=2))
    return 0 if not findings else 1


if __name__ == '__main__':
    sys.exit(main())
