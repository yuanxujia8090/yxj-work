#!/usr/bin/env python3
"""Shared, fail-closed checks for x-rail task artifacts."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

UTC = timezone.utc
ISO_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$")
SENSITIVE_ACTIONS = {"irreversible", "cost", "external-publish", "scope-change"}
STATUSES = {"in_progress", "done", "blocked", "stopped", "cancelled"}
STAGES = {"fast-answer", "investigate", "research", "design", "plan", "exec", "bugfix", "review", "ops", "mixed", "handoff"}


def fail(message: str) -> None:
    raise ValueError(message)


def parse_evidence_time(value: str) -> datetime:
    if not isinstance(value, str) or not ISO_TIME.fullmatch(value):
        raise ValueError(f"invalid timestamp: {value!r}; expected YYYY-MM-DDTHH:MM:SSZ or offset")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"invalid timestamp: {value!r}") from error
    if not value.endswith('Z') and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError(f'invalid timestamp offset: {value!r}')
    offset = parsed.utcoffset()
    if offset is None or abs(offset.total_seconds()) >= 24 * 3600:
        raise ValueError(f"invalid timestamp offset: {value!r}")
    return parsed.astimezone(UTC)


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _unique_fields(lines: Iterable[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        if not line or line.startswith("#") or line.startswith("##"):
            continue
        match = re.fullmatch(r"([a-z_]+): (.*)", line)
        if not match:
            continue
        key, value = match.groups()
        if key in result:
            fail(f"duplicate {label} field: {key}")
        result[key] = value
    return result


def _section(lines: list[str], title: str) -> list[str]:
    marker = f"## {title}"
    try:
        start = lines.index(marker) + 1
    except ValueError:
        return []
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def _acceptances(lines: list[str]) -> dict[str, dict[str, str]]:
    section = _section(lines, "Acceptance")
    output: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in section:
        if line.startswith("### "):
            current = line[4:]
            if not re.fullmatch(r"A[1-9]\d*", current):
                fail(f"invalid acceptance heading: {line}")
            if current in output:
                fail(f"duplicate acceptance id: {current}")
            output[current] = {}
        elif current and line:
            match = re.fullmatch(r"([a-z_]+): (.*)", line)
            if match:
                key, value = match.groups()
                if key in output[current]:
                    fail(f"duplicate {current} field: {key}")
                output[current][key] = value
    return output


def _gate(lines: list[str]) -> dict[str, str]:
    return _unique_fields(_section(lines, "Decision Gates"), "gate")


def check_contract(task_dir: Path, mode: str = "ready", strict: bool = True) -> dict:
    task_dir = Path(task_dir).resolve()
    path = task_dir / "contract.md"
    if not path.is_file() or path.is_symlink():
        fail("contract.md not found or is a symlink")
    lines = _lines(path)
    if not strict:
        import subprocess
        result = subprocess.run(['bash', str(Path(__file__).with_name('check-contract-legacy.sh')), str(task_dir), '--draft' if mode == 'draft' else '--ready'], capture_output=True, text=True)
        if result.returncode:
            fail(result.stderr.strip())
        return {"legacy": True, "fields": {}}
    for line in lines:
        if re.match(r'^- [a-z_]+:', line):
            fail('fields must use key: value at column 1; remove list markers')
    headings = [line for line in lines if line.startswith('## ')]
    if len(headings) != len(set(headings)):
        fail('duplicate contract section')
    top = lines[:next((i for i, line in enumerate(lines) if line.startswith('## ')), len(lines))]
    fields = _unique_fields(top, "contract")
    if '## Acceptance' not in lines:
        fail("strict mode requires Acceptance")
    required = ["task_id", "level", "task_type", "objective", "scope", "forbidden", "risk", "risk_reason", "review_policy", "contract_revision", "done_when"]
    for key in required:
        if not fields.get(key):
            fail(f"missing field: {key}")
    if fields['task_id'] != task_dir.name:
        fail('contract task_id differs from task directory')
    if fields["level"] not in {"L1", "L2", "L3", "long"}:
        fail(f"invalid level: {fields['level']}")
    if fields["task_type"] not in {"investigate", "research", "design", "plan", "exec", "bugfix", "review", "ops", "mixed"}:
        fail(f"invalid task_type: {fields['task_type']}")
    if fields["risk"] not in {"low", "medium", "high"}:
        fail(f"invalid risk: {fields['risk']}")
    if fields["review_policy"] not in {"auto", "user-confirm", "full-review"}:
        fail(f"invalid review_policy: {fields['review_policy']}")
    if not re.fullmatch(r"[1-9]\d*", fields["contract_revision"]):
        fail(f"invalid contract_revision: {fields['contract_revision']}")
    for title in ["Unknowns", "Decision Gates", "Contract Changes"]:
        if not _section(lines, title):
            fail(f"missing section: {title}")
    acceptances = _acceptances(lines)
    if not acceptances:
        fail("Acceptance has no conditions")
    for aid, values in acceptances.items():
        for key in ["outcome", "verification", "verification_type", "layer", "required"]:
            if not values.get(key):
                fail(f"{aid} missing field: {key}")
        if values["verification_type"] not in {"automatic", "manual", "consumer", "external"}:
            fail(f"{aid} invalid verification_type: {values['verification_type']}")
        if values["layer"] not in {"syntax/config", "static", "runtime/local", "external", "consumer"}:
            fail(f"{aid} invalid layer: {values['layer']}")
        if values["required"] == "no" and not values.get("skip_reason"):
            fail(f"{aid} optional condition needs skip_reason")
        if values["required"] not in {"yes", "no"}:
            fail(f"{aid} invalid required: {values['required']}")
    gates = _gate(lines)
    for key in ["confirmation", "confirmation_status", "review", "action_categories"]:
        if not gates.get(key):
            fail(f"Decision Gates missing field: {key}")
    if gates["confirmation"] not in {"required", "exempted"}:
        fail(f"invalid confirmation: {gates['confirmation']}")
    if gates["confirmation_status"] not in {"pending", "confirmed", "exempted"}:
        fail(f"invalid confirmation_status: {gates['confirmation_status']}")
    if gates["review"] not in {"auto", "user-confirm", "full-review"}:
        fail(f"invalid review: {gates['review']}")
    if fields["review_policy"] != gates["review"]:
        fail("review conflicts with review_policy")
    actions = set(filter(None, gates.get("action_categories", "none").split(",")))
    if actions - SENSITIVE_ACTIONS - {"none"} or ('none' in actions and len(actions) > 1):
        fail("invalid action_categories")
    if actions & SENSITIVE_ACTIONS:
        if gates["confirmation"] != "required":
            fail("sensitive action requires confirmation: required")
        if gates["confirmation_status"] != "confirmed" and mode != "draft":
            fail("confirmation is pending; only --draft is allowed")
    if fields["risk"] == "medium" and fields["review_policy"] == "auto":
        fail("medium risk cannot use auto review_policy")
    if fields["risk"] == "high" and fields["review_policy"] != "full-review":
        fail("high risk requires full-review policy")
    if gates["confirmation"] == "exempted":
        if gates["confirmation_status"] != "exempted" or not gates.get("confirmation_reason"):
            fail("exempted confirmation needs reason and exempted status")
    elif gates["confirmation_status"] == "confirmed":
        for key in ["confirmation_by", "confirmation_at", "confirmation_source"]:
            if not gates.get(key) or gates[key] == "none":
                fail(f"confirmed gate needs {key}")
    elif mode != "draft":
        fail("confirmation is pending; only --draft is allowed")
    dependencies = []
    dependency_names, dependency_tasks = set(), set()
    for line in _section(lines, 'Dependencies'):
        if not line.strip():
            continue
        if not line.startswith('dependency: '):
            fail('invalid dependency record')
        name, *segments = line[len('dependency: '):].split('|')
        item = _parse_pipe('|'.join(segments), '')
        child = item.get('task_id', '')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', child) or child == task_dir.name:
            fail('dependency task path invalid or self-reference')
        if name in dependency_names or child in dependency_tasks:
            fail('duplicate dependency')
        dependency_names.add(name); dependency_tasks.add(child)
        if item.get('required') not in {'yes', 'no'} or item.get('acceptance') not in acceptances:
            fail('dependency required or acceptance invalid')
        if item['required'] == 'no' and not item.get('skip_reason'):
            fail('optional dependency needs skip_reason')
        item['key'] = name
        dependencies.append(item)
    if not any(item['required'] == 'yes' for item in acceptances.values()):
        fail('Acceptance needs at least one required condition')
    if gates.get('confirmation_status') == 'confirmed':
        parse_evidence_time(gates['confirmation_at'])
    revision = int(fields["contract_revision"])
    audit = task_dir / "audit"
    if mode in {"seal", "locked"}:
        for number in range(1, revision + 1):
            snapshot = audit / f"contract-r{number}.md"
            if number < revision or mode == "locked":
                if not snapshot.is_file():
                    fail(f"missing contract snapshot r{number}")
            if number > 1:
                change = audit / f"contract-change-r{number}.md"
                if not change.is_file():
                    fail(f"missing change record r{number}")
                changes = _unique_fields(_lines(change), 'change')
                for key in ['old_revision', 'new_revision', 'old_value', 'new_value', 'reason', 'approved_by', 'approval_source', 'affected_evidence']:
                    if not changes.get(key):
                        fail(f'change r{number} missing {key}')
                if changes['old_revision'] != str(number - 1) or changes['new_revision'] != str(number):
                    fail('change revision mismatch')
                if f'audit/contract-change-r{number}.md' not in '\n'.join(_section(lines, 'Contract Changes')):
                    fail(f'Contract Changes missing record r{number}')
                previous = _lines(audit / f'contract-r{number-1}.md')
                previous_acceptance = _acceptances(previous)
                current_lines = lines if number == revision else _lines(audit / f'contract-r{number}.md')
                current_acceptance = _acceptances(current_lines)
                old_required = {key for key, item in previous_acceptance.items() if item.get('required') == 'yes'}
                weakened = any(key not in current_acceptance or current_acceptance[key].get('required') != 'yes' or current_acceptance[key] != previous_acceptance[key] for key in old_required)
                if weakened and (changes['approved_by'] == 'none' or changes['approval_source'] == 'none'):
                    fail('changed required acceptance needs approval')
        snapshot = audit / f"contract-r{revision}.md"
        if snapshot.exists() and snapshot.read_bytes() != path.read_bytes():
            fail("contract changed without a new revision")
        if mode == "seal" and not snapshot.exists():
            audit.mkdir(exist_ok=True)
            with snapshot.open('xb') as output:
                output.write(path.read_bytes())
    return {"legacy": False, "fields": fields, "acceptances": acceptances, "gates": gates, "dependencies": dependencies}


def _parse_state(path: Path) -> tuple[dict[str, str], list[str], list[str]]:
    lines = _lines(path)
    fields: dict[str, str] = {}
    required: list[str] = []
    evidence: list[str] = []
    for line in lines:
        if line.startswith("required_verification:"):
            required.append(line)
        elif line.startswith("evidence:"):
            evidence.append(line)
        elif re.match(r"^[a-z_]+: ", line):
            key, value = line.split(": ", 1)
            if key in fields:
                fail(f"duplicate state field: {key}")
            fields[key] = value
    return fields, required, evidence


def _safe_task_path(task_dir: Path, relative: str) -> Path:
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        fail(f"evidence path escapes task directory: {relative}")
    resolved = (task_dir / candidate).resolve()
    try:
        resolved.relative_to(task_dir)
    except ValueError:
        fail(f"evidence path escapes task directory: {relative}")
    if resolved.is_symlink() or (task_dir / candidate).is_symlink():
        fail(f"evidence path must not be a symlink: {relative}")
    return resolved


def _parse_pipe(line: str, prefix: str) -> dict[str, str]:
    if not line.startswith(prefix):
        return {}
    values: dict[str, str] = {}
    for item in line[len(prefix):].split("|"):
        if not item:
            continue
        if "=" not in item:
            fail(f"malformed record: {line}")
        key, value = item.split("=", 1)
        if key in values:
            fail(f"duplicate record field: {key}")
        values[key] = value
    return values


def _check_inputs(task_dir: Path, reference: str, contract_revision: str) -> None:
    path = _safe_task_path(task_dir, reference)
    if not path.is_file() or not path.read_bytes().strip():
        fail(f"input summary missing or empty: {reference}")
    try:
        data = json.loads(path.read_text(), object_pairs_hook=unique_json_object)
    except json.JSONDecodeError as error:
        fail(f"invalid input summary: {reference}")
    if not isinstance(data, dict):
        fail('input summary must be an object')
    if data.get("version") != 1 or str(data.get("contract_revision")) != contract_revision or not data.get("workspace_root"):
        fail(f"input summary contract mismatch: {reference}")
    files = data.get("files")
    if not isinstance(files, list) or not files:
        fail(f"input summary files must be non-empty: {reference}")
    if not Path(data['workspace_root']).is_absolute():
        fail('input workspace_root must be absolute')
    root = Path(data["workspace_root"]).resolve()
    seen = set()
    for item in files:
        if not isinstance(item, dict):
            fail('invalid input entry')
        relative = item.get("path")
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            fail(f"input path escapes workspace: {relative}")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            fail(f'input path escapes workspace: {relative}')
        if path in seen:
            fail('duplicate input path')
        seen.add(path)
        if path == task_dir / 'state.md' or path == task_dir / 'contract.md' or path.is_relative_to(task_dir / 'evidence') or path.is_relative_to(task_dir / 'audit'):
            fail('input summary cannot include task state or evidence')
        if item.get("state") == "present":
            if not path.is_file():
                fail(f"input file missing: {relative}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != item.get("sha256"):
                fail(f"input changed: {relative}")
        elif item.get("state") == "absent":
            if path.exists() or path.is_symlink():
                fail(f"input changed: {relative}")
        else:
            fail(f"invalid input state: {relative}")


def read_runs(task_dir: Path, dependencies: list[dict] | None = None) -> list[dict]:
    path = Path(task_dir) / 'audit/runs.json'
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(), object_pairs_hook=unique_json_object)
    except json.JSONDecodeError as error:
        fail(f'invalid runs.json: {error}')
    if not isinstance(data, dict):
        fail('runs.json must be an object')
    if data.get('version') != 1 or not isinstance(data.get('runs'), list):
        fail('invalid runs.json schema')
    result = []
    for run in data['runs']:
        if not isinstance(run, dict) or not run.get('key') or not run.get('provider') or not run.get('run_id') or not run.get('task_id'):
            fail('run reference missing identity')
        if not Path(run.get('workspace', '')).is_absolute():
            fail('run workspace must be absolute')
        if run.get('observed_status') not in {'unknown', 'queued', 'pending', 'running', 'waiting', 'needs_attention', 'completed', 'done', 'failed', 'blocked', 'stopped', 'cancelled', 'interrupted', 'timed_out'}:
            fail('invalid run observed status')
        if dependencies is not None and not any(item['key'] == run['key'] and item['task_id'] == run['task_id'] for item in dependencies):
            fail('run reference does not match a declared dependency')
        parse_evidence_time(run.get('observed_at', ''))
        if run.get('output_reference') and (Path(run['output_reference']).is_absolute() or '..' in Path(run['output_reference']).parts):
            fail('run output reference escapes task')
        result.append(run)
    if len({run['key'] for run in result}) != len(result):
        fail('duplicate run reference')
    return result


def check_state(task_dir: Path, state_path: Path | None = None, strict: bool = True, ancestors: tuple = ()) -> dict:
    task_dir = Path(task_dir).resolve()
    state_path = Path(state_path or task_dir / "state.md")
    if strict and state_path.is_symlink():
        fail('state must not be a symlink')
    state_path = state_path.resolve()
    if strict and not state_path.is_relative_to(task_dir):
        fail('state path escapes task directory')
    if not state_path.is_file():
        fail("state.md not found")
    if task_dir in ancestors:
        fail('dependency cycle')
    fields, required_lines, evidence_lines = _parse_state(state_path)
    if not strict:
        return check_legacy_state(task_dir, fields, required_lines, evidence_lines)
    for key in ["task_id", "status", "stage", "calls_since_progress", "budget", "last_progress_at"]:
        if not fields.get(key):
            fail(f"missing {key}")
    if fields["status"] not in STATUSES:
        fail(f"invalid status: {fields['status']}")
    if fields["stage"] not in STAGES:
        fail(f"invalid stage: {fields['stage']}")
    if not fields["calls_since_progress"].isdigit():
        fail("invalid calls_since_progress")
    threshold = 60 if fields.get("level") in {"L3", "long"} else 20
    calls = int(fields["calls_since_progress"])
    if calls >= threshold and fields["status"] not in {"blocked", "stopped", "cancelled"}:
        fail(f"calls_since_progress reached {threshold} while status is not paused")
    match = re.fullmatch(r"(\d+)/(\d+)", fields["budget"])
    if not match or int(match.group(2)) <= 0:
        fail("invalid budget; expected used/limit")
    used, limit = map(int, match.groups())
    if used > limit and fields["status"] not in {"blocked", "stopped", "cancelled"}:
        fail("budget exceeded; state must be paused")
    if used == limit and fields["status"] == "in_progress":
        fail("budget exhausted; state must be paused")
    if fields.get('level') not in {'L1', 'L2', 'L3', 'long'}:
        fail('invalid level')
    if fields["status"] in {"blocked", "stopped", "cancelled"}:
        if fields.get('blocked_by', 'none') == 'none':
            fail('paused state needs reason in blocked_by')
        for key in ["blocked_by", "unblock_condition", "next_action"]:
            if not fields.get(key):
                fail(f"blocked state missing {key}")
    for key in ['started_at', 'deadline_at', 'updated_at', 'last_progress_at']:
        if fields.get(key):
            parse_evidence_time(fields[key])
    if fields.get('updated_at') and fields.get('last_progress_at'):
        elapsed = (parse_evidence_time(fields['updated_at']) - parse_evidence_time(fields['last_progress_at'])).total_seconds()
        if elapsed < 0:
            fail('progress timestamp follows updated_at')
        if fields.get('level') in {'L3', 'long'} and elapsed >= 1800 and fields['status'] == 'in_progress':
            fail('no progress for 30 minutes; state must be paused')
    if fields.get('deadline_at'):
        deadline = parse_evidence_time(fields['deadline_at'])
        observed = parse_evidence_time(fields.get('updated_at', fields.get('last_progress_at', '')))
        if fields.get('started_at') and parse_evidence_time(fields['started_at']) > deadline:
            fail('deadline precedes start')
        if observed > deadline and fields['status'] == 'in_progress':
            fail('deadline exceeded; state must be paused')
        if observed > deadline and fields['status'] == 'done':
            fail('done state exceeded deadline')
    contract = task_dir / "contract.md"
    if not contract.is_file():
        fail('strict state requires contract.md')
    if contract.is_file():
        contract_data = check_contract(task_dir, mode='locked')
        read_runs(task_dir, dependencies=contract_data['dependencies'])
        if fields['task_id'] != contract_data['fields']['task_id']:
            fail('state task_id differs from contract')
        if fields['level'] != contract_data['fields']['level']:
            fail('state level differs from contract')
        revision = contract_data["fields"]["contract_revision"]
        if fields.get("evidence_schema") != "2":
            fail("strict state requires evidence_schema: 2")
        if fields.get("contract_revision") != revision:
            fail("contract_revision mismatch or missing in state")
        fingerprint = hashlib.sha256(contract.read_bytes()).hexdigest()
        if fields.get("contract_fingerprint") != fingerprint:
            fail("contract_fingerprint mismatch or missing in state")
        required_ids = [aid for aid, item in contract_data["acceptances"].items() if item["required"] == "yes"]
        seen_acceptances: set[str] = set()
        for line in required_lines:
            raw = line[len("required_verification: "):]
            parts = raw.split()
            aid = parts[0] if parts else ""
            if aid in seen_acceptances:
                fail(f"duplicate required verification: {aid}")
            seen_acceptances.add(aid)
            if aid not in contract_data["acceptances"]:
                fail(f"unknown acceptance reference: {aid}")
            record = _parse_pipe('|'.join(parts[1:]), '')
            status = record.get('status', '')
            evidence_ref = record.get('evidence', '')
            if status not in {"passed", "failed", "not_run", "blocked"}:
                fail(f"invalid verification status: {aid}")
            if fields["status"] == "done" and status != "passed":
                fail(f"required acceptance not passed: {aid}")
            if status == "passed":
                if not evidence_ref:
                    fail(f"required verification missing evidence: {aid}")
                ev_path = _safe_task_path(task_dir, evidence_ref)
                if not ev_path.is_file() or not ev_path.read_bytes().strip():
                    fail(f"evidence file missing or empty: {evidence_ref}")
                evidence_id = Path(evidence_ref).stem
                matches = [line for line in evidence_lines if line.startswith(f"evidence:{evidence_id}|")]
                if len(matches) != 1:
                    fail(f"evidence record missing or duplicate: {evidence_id}")
                ev = _parse_pipe(matches[0], f"evidence:{evidence_id}|")
                for key in ["acceptance", "command", "run_at", "result", "last_edit_at", "inputs", "contract_revision"]:
                    if not ev.get(key):
                        fail(f"evidence {evidence_id} missing {key}")
                if ev["acceptance"] != aid or ev["contract_revision"] != revision or ev["result"] != "passed":
                    fail(f"evidence {evidence_id} does not match {aid}")
                run_at = parse_evidence_time(ev["run_at"])
                last_edit = parse_evidence_time(ev["last_edit_at"])
                if run_at < last_edit:
                    fail(f"evidence is stale: {evidence_id}")
                _check_inputs(task_dir, ev["inputs"], revision)
        evidence_ids = [line.split('|', 1)[0] for line in evidence_lines]
        if len(evidence_ids) != len(set(evidence_ids)):
            fail('duplicate evidence id')
        if fields["status"] == "done":
            if not set(required_ids).issubset(seen_acceptances):
                fail("done state does not list every required acceptance")
            if contract_data["fields"]["review_policy"] != "auto":
                review_lines = [line for line in _lines(state_path) if line.startswith("review_evidence:")]
                if not review_lines:
                    fail("review evidence required for " + contract_data["fields"]["review_policy"])
                if len(review_lines) != 1:
                    fail('duplicate review evidence')
                if '|' not in review_lines[0]:
                    fail('malformed review evidence')
                review = _parse_pipe(review_lines[0].split('|', 1)[1], '')
                if review.get("policy") != contract_data["fields"]["review_policy"] or review.get("status") != "passed":
                    fail("review evidence is not passed")
                for key in ['path', 'inputs', 'contract_revision', 'run_at', 'last_edit_at']:
                    if not review.get(key):
                        fail(f'review evidence missing {key}')
                report = _safe_task_path(task_dir, review['path'])
                if not report.is_file() or not report.read_bytes().strip():
                    fail('review evidence file missing or empty')
                if review['contract_revision'] != revision:
                    fail('review evidence contract revision mismatch')
                if parse_evidence_time(review['run_at']) < parse_evidence_time(review['last_edit_at']):
                    fail('review evidence stale')
                _check_inputs(task_dir, review['inputs'], revision)
            for item in contract_data['dependencies']:
                if item['required'] == 'no':
                    continue
                child = (task_dir.parent / item['task_id']).resolve()
                if not child.is_relative_to(task_dir.parent) or not child.is_dir():
                    fail('dependency missing or path escapes tasks')
                try:
                    result = check_state(child, ancestors=ancestors + (task_dir,))
                    if result['status'] != 'done':
                        fail('dependency is not done')
                except (OSError, ValueError) as error:
                    fail(f'dependency {item["key"]}: {error}')
    return fields


def check_legacy_state(task_dir, fields, required_lines, evidence_lines):
    import subprocess
    script = Path(__file__).resolve().with_name('check-state-legacy.sh')
    result = subprocess.run(['bash', str(script), str(task_dir)], capture_output=True, text=True)
    if result.returncode:
        fail(result.stderr.strip())
    return fields
