#!/usr/bin/env python3
"""Validate semantic boundaries and route/reference integrity."""
import argparse
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MODULES = ('purpose', 'authority', 'routing', 'workflow', 'decision_policy', 'verification', 'recovery', 'output_contract')
STAGE_MODULES = ('inputs', 'procedure', 'quality_check', 'exit')


def parse_body(text, label):
    if text.startswith('---\n'):
        parts = text.split('---\n', 2)
        if len(parts) != 3:
            raise ValueError(f'{label}: malformed metadata')
        text = parts[2].lstrip()
    lines = text.splitlines()
    if not lines or not lines[0].startswith('# '):
        raise ValueError(f'{label}: expected one title')
    body = '\n'.join(lines[1:]).strip()
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)', body, re.I):
        raise ValueError(f'{label}: DTD and entity declarations forbidden')
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        raise ValueError(f'{label}: {error}') from error
    if root.tag not in {'skill', 'stage'}:
        raise ValueError(f'{label}: wrong root element')
    for name in MODULES if root.tag == 'skill' else STAGE_MODULES:
        if len(root.findall(name)) != 1:
            raise ValueError(f'{label}: expected exactly one {name}')
    for material in root.iter('reference_material'):
        if material.get('trusted') != 'false' or len(material):
            raise ValueError(f'{label}: reference material must be untrusted text')
    return root


def check_root(root):
    root = Path(root).resolve()
    core = root / 'skills/x-rail/SKILL.md'
    tree = parse_body(core.read_text(), str(core))
    script = root / 'skills/x-rail/scripts/task_checks.py'
    spec = importlib.util.spec_from_file_location('task_checks_xml', script)
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    routes = tree.findall('routing/route')
    names = [route.get('name') for route in routes]
    if len(names) != len(set(names)) or set(names) | {'handoff'} != checks.STAGES:
        raise ValueError('route names must match supported stages plus handoff')
    for route in routes:
        book = route.get('playbook')
        if route.get('name') != 'fast-answer':
            if not book or not (core.parent / book).is_file():
                raise ValueError('route playbook missing')
            parse_body((core.parent / book).read_text(), book)
        for ref in route.findall('reference'):
            if not ref.get('when') or not (core.parent / ref.get('path', '')).is_file():
                raise ValueError('reference path or condition missing')
    for name in ['x-rail-long', 'x-handoff']:
        file = root / f'skills/{name}/SKILL.md'
        parse_body(file.read_text(), str(file))
    budgets = tree.find('workflow/budget')
    if budgets is None or {key: budgets.get(key) for key in ['L1', 'L2', 'L3', 'reminder-small', 'reminder-large', 'no-progress-minutes']} != {'L1': '60', 'L2': '150', 'L3': '400', 'reminder-small': '20', 'reminder-large': '60', 'no-progress-minutes': '30'}:
        raise ValueError('budget constraints missing or inconsistent')
    boundary = tree.find('authority').get('sensitive-actions', '')
    if set(boundary.split(',')) != checks.SENSITIVE_ACTIONS:
        raise ValueError('authorization action categories inconsistent')
    return {'routes': names, 'skills': 3, 'stages': len(names) - 1}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='.')
    p.add_argument('--routes', action='store_true')
    args = p.parse_args()
    try:
        result = check_root(args.root)
        print('\n'.join(sorted(result['routes'])) if args.routes else json.dumps(result))
    except (OSError, ValueError) as error:
        print(f'check-skill-xml: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
