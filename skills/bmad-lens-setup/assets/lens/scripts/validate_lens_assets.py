#!/usr/bin/env python3
"""Validate LENS module source assets beyond the generic BMAD module checks."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REQUIRED_SKILLS = [
    'bmad-lens-setup','bmad-lens-help','bmad-lens-intake','bmad-lens-slice-new','bmad-lens-slice-frame','bmad-lens-slice-scope','bmad-lens-detect-adjacency','bmad-lens-detect-repetition','bmad-lens-suggest-promotion','bmad-lens-discover','bmad-lens-capture','bmad-lens-synthesize','bmad-lens-context-check','bmad-lens-research-plan','bmad-lens-map-system','bmad-lens-map-outcomes','bmad-lens-map-loops','bmad-lens-map-journeys','bmad-lens-slice-journey','bmad-lens-map-capabilities','bmad-lens-analyze-impact','bmad-lens-promote-landscape','bmad-lens-map-rebuild','bmad-lens-prepare-bmad','bmad-lens-sync-bmad','bmad-lens-guard-story','bmad-lens-validate-slice','bmad-lens-validate-journey','bmad-lens-validate-outcome','bmad-lens-salmon','bmad-lens-doctor','bmad-lens-auspex'
]
REQUIRED_ENTITIES = ['system','system_thesis','discovery_epoch','session','source','extraction','slice','artifact','adjacency','relationship','role','stakeholder','outcome','operating_loop','journey','journey_step','capability','domain','service','workstream','program','decision','assumption','unknown','risk','evidence','salmon_signal','auspex_status','bmad_packet','validation_result']
REQUIRED_TEMPLATES = ['slice.yaml','discovery-epoch.yaml','relationship.yaml','promotion-gate.yaml','impact-map.yaml','bmad-packet.md','context-sufficiency.md','story-guard.yaml','salmon-signal.yaml','validation-result.yaml','doctor-report.md','auspex-status.yaml','journey.yaml','journey.md','journey-map.mmd']
REQUIRED_FIXTURES = {
    'fixtures/top-down/evidence-visible-to-teacher': ['slice.yaml', 'journey.yaml', 'impact-map.yaml'],
    'fixtures/bottom-up/download-model-images': ['slice.yaml', 'adjacency.yaml', 'promotion-gate.yaml'],
}
REQUIRED_TESTS = [
    'scripts/tests/test_lens_artifact_ops.py',
    'scripts/tests/test_validate_lens_assets.py',
]


def fail(findings, category, message):
    findings.append({'category': category, 'message': message})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--module-root', default='.')
    args = parser.parse_args()
    root = Path(args.module_root)
    findings = []
    skills = root / 'skills'
    setup = skills / 'bmad-lens-setup'
    assets = setup / 'assets' / 'lens'

    for skill in REQUIRED_SKILLS:
        if not (skills / skill / 'SKILL.md').is_file():
            fail(findings, 'skills', f'missing skill {skill}')

    help_csv = setup / 'assets' / 'module-help.csv'
    if help_csv.is_file():
        rows = list(csv.DictReader(help_csv.open(encoding='utf-8')))
        csv_skills = {r.get('skill','') for r in rows}
        for skill in REQUIRED_SKILLS:
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
        for skill in REQUIRED_SKILLS:
            if f'./skills/{skill}' not in text:
                fail(findings, 'marketplace', f'marketplace missing {skill}')
    else:
        fail(findings, 'marketplace', 'missing .claude-plugin/marketplace.json')

    schema_path = assets / 'schemas' / 'lens-entity.schema.json'
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding='utf-8'))
        entities = set(schema.get('properties', {}).get('kind', {}).get('enum', []))
        for entity in REQUIRED_ENTITIES:
            if entity not in entities:
                fail(findings, 'schema', f'missing entity {entity}')
    else:
        fail(findings, 'schema', 'missing lens-entity.schema.json')

    for template in REQUIRED_TEMPLATES:
        if not (assets / 'templates' / template).is_file():
            fail(findings, 'templates', f'missing template {template}')

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

    for test_path in REQUIRED_TESTS:
        if not (assets / test_path).is_file():
            fail(findings, 'tests', f'missing {test_path}')

    evals = assets / 'evals' / 'lens-evals.yaml'
    if evals.is_file():
        text = evals.read_text(encoding='utf-8')
        if text.count('id: lens.eval.') < 8:
            fail(findings, 'evals', 'expected at least 8 eval cases')
    else:
        fail(findings, 'evals', 'missing lens-evals.yaml')

    runner_evals = root / 'evals' / 'lens' / 'evals.json'
    runner_triggers = root / 'evals' / 'lens' / 'triggers.json'
    if runner_evals.is_file():
        data = json.loads(runner_evals.read_text(encoding='utf-8'))
        if len(data.get('evals', [])) < 8:
            fail(findings, 'evals', 'evals/lens/evals.json must contain at least 8 evals')
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
