"""Serial closeout regressions; all approval keys and records are synthetic."""
import copy
import json
from unittest.mock import patch

import pytest

from test_stage_s00e_phase_d_repair import fixture, write, TASK, RUN
from s00e_evidence import validate_tests, EvidenceError
import stage_handoff as handoff
import s00e_approval as approval
import subprocess
from types import SimpleNamespace
from test_stage_s00e_phase_d_repair import refresh


def test_duplicate_main_call_is_not_a_subtest(tmp_path):
    fx = fixture(tmp_path)
    proof = fx['run_base'] / 'private/PYTEST_EXECUTION_NODES.json'
    value = json.loads(proof.read_text())
    value['reports'].append(copy.deepcopy(value['reports'][1]))
    write(proof, value)
    record = fx['tests']
    record['execution_proof_sha256'] = handoff.sha256(proof)
    record['subtests_passed'] = 1
    with pytest.raises(EvidenceError):
        validate_tests(record, tmp_path, TASK, RUN)


def test_typed_subtest_positive_control(tmp_path):
    fx = fixture(tmp_path)
    proof = fx['run_base'] / 'private/PYTEST_EXECUTION_NODES.json'
    value = json.loads(proof.read_text())
    sub = copy.deepcopy(value['reports'][1])
    sub['subtest'] = True
    value['reports'].insert(1, sub)
    write(proof, value)
    fx['tests']['execution_proof_sha256'] = handoff.sha256(proof)
    fx['tests']['subtests_passed'] = 1
    validate_tests(fx['tests'], tmp_path, TASK, RUN)


@pytest.mark.parametrize('defect', ['boolean_exit', 'missing_marker', 'string_marker', 'source_during_tests'])
def test_strict_pytest_proof_types_and_execution_snapshot(tmp_path, defect):
    fx = fixture(tmp_path)
    proof = fx['run_base'] / 'private/PYTEST_EXECUTION_NODES.json'
    value = json.loads(proof.read_text())
    if defect == 'boolean_exit':
        value['exit_code'] = False
    elif defect == 'missing_marker':
        value['reports'][1].pop('subtest')
    elif defect == 'string_marker':
        value['reports'][1]['subtest'] = 'false'
    else:
        fx['tests']['tested_files_before_sha256'] = {'changed': '0' * 64}
    write(proof, value)
    fx['tests']['execution_proof_sha256'] = handoff.sha256(proof)
    with pytest.raises(EvidenceError):
        validate_tests(fx['tests'], tmp_path, TASK, RUN)


def test_real_detached_signature_requires_external_owner_key_and_exact_bytes(tmp_path):
    # Synthetic ephemeral keys never enroll with GitHub and never approve a real run.
    key = tmp_path / 'fixture_key'
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True, capture_output=True)
    public = (tmp_path / 'fixture_key.pub').read_text().split()
    trusted = ' '.join(public[:2])
    message = tmp_path / 'payload'
    message.write_bytes(b'synthetic review digest\n')
    subprocess.run(['ssh-keygen', '-Y', 'sign', '-f', str(key), '-n', approval.NAMESPACE, str(message)],
                   check=True, capture_output=True)
    signature = tmp_path / 'payload.sig'
    with patch.object(approval, 'owner_signing_keys', return_value=[trusted]):
        approval.verify_owner_signature(message.read_bytes(), signature)
        with pytest.raises(approval.ApprovalError):
            approval.verify_owner_signature(b'changed review digest\n', signature)
    with patch.object(approval, 'owner_signing_keys', side_effect=approval.ApprovalError('unavailable')):
        with pytest.raises(approval.ApprovalError):
            approval.verify_owner_signature(message.read_bytes(), signature)


def test_editable_approval_fields_are_not_a_signature(tmp_path):
    fx = fixture(tmp_path)
    write(fx['run_base'] / 'private/OWNER_APPROVAL.json', {'approved': True, 'reviewer_model': 'GPT-6 Astra'})
    with patch.object(approval, 'native_sessions_root', return_value=tmp_path / 'absent-host'), \
         pytest.raises(approval.ApprovalError, match='unavailable'):
        approval.verify(tmp_path, tmp_path / fx['review_relative'], TASK, RUN)


def test_full_synthetic_publisher_reaches_final_index_with_bound_acceptance(tmp_path):
    fx = fixture(tmp_path)
    receipt_path = 'reports/engineering/s00e_prepublication_preflight.json'
    fx['manifest']['public_files'].append(receipt_path)
    manifest_path = fx['run_base'] / 'public/HANDOFF_INPUTS.json'
    write(manifest_path, fx['manifest'])
    write(tmp_path / receipt_path, {'stage': 'S00E', 'run_id': RUN,
          'name': 'PREPUBLICATION_SAFETY_PREFLIGHT', 'status': 'PASS', 'read_only': True,
          'e01_e20_passed': True, 'review_e19_checked': True,
          'tracked_tree_and_index_checked': True, 'git_write_performed': False,
          'release_created': False, 'manifest_sha256': handoff.sha256(manifest_path)})
    gate_path = fx['run_base'] / 'GATE.json'
    gate = json.loads(gate_path.read_text())
    gate.update(status='PASS', passed=True, summary={'PASS': 21, 'FAIL': 0, 'SKIPPED': 0, 'BLOCKED': 0})
    gate['items'][-1].update(status='PASS', evidence=[receipt_path])
    write(gate_path, gate)
    refresh(fx)
    commits = ['1' * 40, '2' * 40, '3' * 40]
    release = {'tag': 'synthetic-release', 'url': 'https://example.invalid/review',
               'asset_name': 'synthetic.zip', 'asset_size_bytes': 10,
               'target': commits[0], 'local_sha256': 'a' * 64, 'downloaded_sha256': 'a' * 64}
    with patch.object(handoff, 'ROOT', tmp_path), patch.object(handoff, 'verify_workspace', return_value='0' * 40), \
         patch.object(handoff, 'verify_independent_review_approval', return_value=None), \
         patch.object(handoff, 'command', return_value=SimpleNamespace(returncode=1, stderr='not found')), \
         patch.object(handoff, 'worktree_changed_paths', return_value=set()), \
         patch.object(handoff, 'exact_stage', side_effect=commits) as staged, \
         patch.object(handoff, 'push_and_verify') as pushed, \
         patch.object(handoff, 'build_review_asset'), \
         patch.object(handoff, 'release_and_verify', return_value=release), \
         patch.object(handoff, 'load_release', return_value={'targetCommitish': commits[0],
                      'assets': [{'name': 'synthetic.zip', 'size': 10}]}):
        # Explicitly pass root: default arguments otherwise refer to the real repo.
        real_validate = handoff.validate_run
        with patch.object(handoff, 'validate_run', side_effect=lambda m: real_validate(m, tmp_path)):
            result = handoff.publish(manifest_path)
        assert result['index_commit'] == commits[2]
        assert staged.call_count == pushed.call_count == 3
        handoff.validate_acceptance(tmp_path / 'reports/stages/S00E/acceptance.json',
                                    'S00E', task_id=TASK, run_id=RUN, root=tmp_path)


def test_commit_and_release_preserve_tested_crlf_bytes(tmp_path):
    from test_stage_s00e_phase_d_repair import git
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.name', 'Synthetic Fixture')
    git(tmp_path, 'config', 'user.email', 'fixture@example.invalid')
    git(tmp_path, 'config', 'core.autocrlf', 'true')
    names = ['docs/safe.md', f'reports/runs/{RUN}/RUN.json', 'reports/stages/S00E/acceptance.json']
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'# Synthetic safe text\r\n' if name.endswith('.md') else b'{}\r\n')
    with patch.object(handoff, 'ROOT', tmp_path), patch.object(
            handoff, 'scan_tracked_public_tree', side_effect=lambda: {'findings': {}}), patch.object(
            handoff, 'public_path', side_effect=lambda n, r, s: tmp_path / n):
        handoff.exact_stage(names, 'synthetic publication bytes')
        asset = tmp_path / 'fixture.zip'
        handoff.build_review_asset(asset, names)
        (tmp_path / names[0]).write_bytes(b'changed\n')
        with pytest.raises(handoff.HandoffError, match='differs'):
            handoff.build_review_asset(tmp_path / 'stale.zip', names)


def test_owner_trust_host_is_pinned_under_hostile_environment(monkeypatch):
    monkeypatch.setenv('GH_HOST', 'attacker.invalid')
    with patch.object(approval.subprocess, 'run', return_value=SimpleNamespace(
            returncode=0, stdout=b'[{"key":"ssh-ed25519 YWJj"}]')) as call:
        assert approval.owner_signing_keys() == ['ssh-ed25519 YWJj']
    argv = call.call_args.args[0]
    assert argv == ['gh', 'api', '--hostname', 'github.com',
                    'users/BiLiangXin/ssh_signing_keys', '--paginate']


def native_fixture(question):
    def event(payload):
        return {'type': 'response_item', 'timestamp': '2026-09-25T00:00:00Z', 'payload': payload}
    return [event({'type': 'function_call', 'name': 'request_user_input_async',
                   'call_id': 'synthetic-call', 'arguments': json.dumps({'questions': [{'title': question}]})}),
            event({'type': 'function_call_output', 'call_id': 'synthetic-call', 'output': '{"accepted":true}'}),
            event({'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text':
                   '<send_user_message_question_reply>\n' + json.dumps([{
                       'questionItemId': json.dumps(['request_user_input_async', 'synthetic-call', 0]),
                       'question': question, 'answer': '批准'}], ensure_ascii=False) +
                   '\n</send_user_message_question_reply>'}]})]


def test_native_user_approval_exact_link_positive():
    question = approval.approval_question(TASK, RUN, 'a' * 64, 'b' * 64)
    result = approval.validate_host_events(native_fixture(question), question)
    assert result['source'] == 'CODEX_NATIVE_USER_EVENT'
    assert result['call_id'] == 'synthetic-call'
    assert len(result['event_sha256']) == 64


@pytest.mark.parametrize('defect', ['assistant', 'tool', 'missing_ack', 'declined', 'wrong_call',
    'wrong_digest', 'duplicate_reply', 'duplicate_request', 'wrong_order', 'malformed', 'timestamp', 'output_text'])
def test_native_approval_rejects_forged_stale_ambiguous_events(defect):
    question = approval.approval_question(TASK, RUN, 'a' * 64, 'b' * 64)
    events = native_fixture(question)
    if defect in ('assistant', 'tool'):
        events[2]['payload']['role'] = defect
    elif defect == 'missing_ack':
        events.pop(1)
    elif defect == 'declined':
        events[2]['payload']['content'][0]['text'] = events[2]['payload']['content'][0]['text'].replace('"answer": "批准"', '"answer": "拒绝"')
    elif defect == 'wrong_call':
        events[2]['payload']['content'][0]['text'] = events[2]['payload']['content'][0]['text'].replace('synthetic-call', 'unlinked-call')
    elif defect == 'wrong_digest':
        question += 'changed'
    elif defect == 'duplicate_reply':
        events.append(copy.deepcopy(events[2]))
    elif defect == 'duplicate_request':
        events.append(copy.deepcopy(events[0]))
    elif defect == 'wrong_order':
        events.reverse()
    elif defect == 'malformed':
        events[2]['payload']['content'][0]['text'] = '<send_user_message_question_reply>[null]</send_user_message_question_reply>'
    elif defect == 'timestamp':
        events[2].pop('timestamp')
    elif defect == 'output_text':
        events[2]['payload']['content'][0]['type'] = 'output_text'
    with pytest.raises(approval.ApprovalError):
        approval.validate_host_events(events, question)


def test_native_journal_identity_and_direct_reread(tmp_path, monkeypatch):
    payload = json.dumps({'task_id': TASK, 'run_id': RUN, 'review_sha256': 'a'*64,
                          'manifest_sha256': 'b'*64}).encode()
    question = approval.approval_question(TASK, RUN, 'a'*64, 'b'*64)
    journal = tmp_path / ('rollout-' + approval.HOST_THREAD_ID + '.jsonl')
    meta = {'type': 'session_meta', 'payload': {'id': approval.HOST_THREAD_ID, 'originator': 'Codex Desktop'}}
    def save(rows):
        journal.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows), encoding='utf-8')
    save([meta] + native_fixture(question))
    # This injected test root is synthetic; production has no root/path/receipt argument.
    with patch.object(approval, 'native_sessions_root', return_value=tmp_path):
        assert approval.verify_native_host(payload)['source'] == 'CODEX_NATIVE_USER_EVENT'
        meta['payload']['id'] = 'different-thread'
        save([meta] + native_fixture(question))
        with pytest.raises(approval.ApprovalError, match='identity'):
            approval.verify_native_host(payload)
        journal.write_text('{invalid', encoding='utf-8')
        with pytest.raises(approval.ApprovalError):
            approval.verify_native_host(payload)


def test_native_profile_root_ignores_environment_redirect(monkeypatch, tmp_path):
    baseline = approval.native_sessions_root()
    for key in ('USERPROFILE', 'CODEX_HOME', 'CODEX_THREAD_ID'):
        monkeypatch.setenv(key, str(tmp_path))
    assert approval.native_sessions_root() == baseline


@pytest.mark.parametrize('position', ['root', 'ancestor', 'intermediate'])
def test_native_junction_redirect_is_rejected(tmp_path, position):
    outside = tmp_path / 'outside'
    outside.mkdir()
    link = tmp_path / 'redirect'
    command = "New-Item -ItemType Junction -Path '" + str(link).replace("'", "''") + "' -Target '" + str(outside).replace("'", "''") + "' | Out-Null"
    subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', command], check=True, capture_output=True)
    assert not link.is_symlink()
    assert link.lstat().st_file_attributes & approval.stat.FILE_ATTRIBUTE_REPARSE_POINT
    if position == 'root':
        root, journal_dir = link, outside
    elif position == 'ancestor':
        (outside / 'sessions').mkdir()
        root, journal_dir = link / 'sessions', outside / 'sessions'
    else:
        root, journal_dir = tmp_path, outside
    payload = json.dumps({'task_id': TASK, 'run_id': RUN, 'review_sha256': 'a'*64, 'manifest_sha256': 'b'*64}).encode()
    question = approval.approval_question(TASK, RUN, 'a'*64, 'b'*64)
    journal = journal_dir / ('rollout-' + approval.HOST_THREAD_ID + '.jsonl')
    rows = [{'type': 'session_meta', 'payload': {'id': approval.HOST_THREAD_ID, 'originator': 'Codex Desktop'}}] + native_fixture(question)
    journal.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows), encoding='utf-8')
    if position == 'intermediate':
        # Explicitly check the discovered intermediate path even on walkers that skip junctions.
        with pytest.raises(approval.ApprovalError, match='Redirected'):
            approval.reject_redirected_path(link / journal.name)
    else:
        with patch.object(approval, 'native_sessions_root', return_value=root), \
             pytest.raises(approval.ApprovalError, match='Redirected'):
            approval.verify_native_host(payload)


def test_native_file_reparse_flag_rejected(tmp_path):
    path = tmp_path / 'journal.jsonl'
    path.write_text('{}')
    from pathlib import Path
    original = Path.lstat
    def attributes(p):
        if p == path:
            return SimpleNamespace(st_mode=approval.stat.S_IFREG, st_file_attributes=approval.stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return original(p)
    with patch.object(Path, 'lstat', attributes), pytest.raises(approval.ApprovalError, match='Redirected'):
        approval.reject_redirected_path(path)
