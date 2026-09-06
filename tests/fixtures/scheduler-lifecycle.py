#!/usr/bin/env python3
"""Required offline scheduler mutation acceptance; never run against an owner HOME.

See docs/release-verification.md for the disposable Docker invocation. This is
separate from ordinary unittest discovery and never builds or pulls an image.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import sys
import time


WORK = Path('/work')
INSTALLER = Path('/input/install-agents.sh')


def validate_container():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-container', action='store_true', required=True)
    parser.parse_args()
    if (not Path('/.dockerenv').is_file() or os.geteuid() != 0
            or os.environ.get('HOME') != '/root' or pwd.getpwuid(0).pw_dir != '/root'):
        raise RuntimeError('requires a fresh disposable Docker container with its unchanged default root HOME')
    mounts = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()]
    if any(parts[4] == '/root' or parts[4].startswith('/root/') for parts in mounts):
        raise RuntimeError('HOME must belong to the disposable container, never a mounted owner directory')
    if Path('/root/Library').exists() or not WORK.is_dir() or WORK.is_symlink() or any(WORK.iterdir()):
        raise RuntimeError('requires empty /work and no existing /root/Library')
    if not INSTALLER.is_file() or INSTALLER.is_symlink():
        raise RuntimeError('mount the selected installer as a regular read-only input')


def main():
    validate_container()
    evidence = WORK / 'evidence'
    evidence.mkdir()
    project = WORK / "parent path ' & literal" / 'project'
    scripts = project / 'scripts/agents'
    scripts.mkdir(parents=True)
    installer = scripts / 'install-agents.sh'
    shutil.copyfile(INSTALLER, installer)
    (scripts / 'fixture-agent.sh').write_text(
        '#!/bin/bash\n# SCHEDULE: daily 03:00\nprintf "literal agent executed\\n" > /work/evidence/agent-executed\n')
    binary = WORK / 'bin'
    binary.mkdir()
    state = evidence / 'native-state.json'
    state.write_text('{}')
    control = evidence / 'control.json'
    control.write_text('{}')
    seam = '''
import json, pathlib, plistlib, sys, time
root = pathlib.Path('/work/evidence')
state = root / 'native-state.json'
control = json.loads((root / 'control.json').read_text())
loaded = json.loads(state.read_text())
args = sys.argv[1:]
with (root / 'calls.jsonl').open('a') as handle:
    handle.write(json.dumps(args) + '\\n')
if args[0] == 'list':
    if control.get('query_failure'):
        print('fixture scheduler unavailable', file=sys.stderr)
        raise SystemExit(77)
    print('PID\\tStatus\\tLabel')
    for label in loaded:
        print('-\\t0\\t' + label)
elif args[0] == 'bootstrap':
    if control.get('bootstrap_failure'):
        print('fixture bootstrap rejected', file=sys.stderr)
        raise SystemExit(78)
    value = plistlib.loads(pathlib.Path(args[2]).read_bytes())
    loaded[value['Label']] = value
    state.write_text(json.dumps(loaded))
    if control.get('pause_bootstrap'):
        (root / 'bootstrap-paused').touch()
        while True:
            time.sleep(1)
elif args[0] == 'bootout':
    if control.get('bootout_failure'):
        print('fixture bootout rejected', file=sys.stderr)
        raise SystemExit(79)
    loaded.pop(args[1].split('/')[-1], None)
    state.write_text(json.dumps(loaded))
else:
    raise SystemExit(90)
'''
    fake = binary / 'launchctl'
    fake.write_text('#!' + sys.executable + '\n' + seam)
    fake.chmod(0o755)
    environment = {**os.environ, 'PATH': str(binary) + ':' + os.environ['PATH']}
    plists = Path('/root/Library/LaunchAgents')
    plists.mkdir(parents=True)
    owner = plists / 'com.owner.keep.plist'
    owner.write_bytes(b'OWNER KEEP\n')
    rows = []

    def capture(name, code, stdout, stderr):
        row = {'name': name, 'exit': code, 'stdout': stdout, 'stderr': stderr,
               'loaded': json.loads(state.read_text()),
               'plists': {path.name: path.read_text() for path in plists.glob('*.plist')}}
        rows.append(row)
        (evidence / 'results.json').write_text(json.dumps({
            'installer_sha256': hashlib.sha256(INSTALLER.read_bytes()).hexdigest(),
            'fixture_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'default_home': os.environ['HOME'], 'rows': rows}, indent=2))
        return row

    def run(name, *arguments, expected=0, loaded=None):
        result = subprocess.run(['bash', str(installer), *arguments], env=environment,
                                text=True, capture_output=True, timeout=30)
        row = capture(name, result.returncode, result.stdout, result.stderr)
        assert row['exit'] == expected, row
        if loaded is not None:
            assert len(row['loaded']) == loaded, row
        return row

    first = run('install', loaded=1)
    job = next(iter(first['loaded'].values()))
    assert job['ProgramArguments'][:2] == ['/bin/bash', '-c'], job
    executed = subprocess.run(job['ProgramArguments'], env=environment,
                              text=True, capture_output=True, timeout=10)
    (evidence / 'agent-execution.json').write_text(json.dumps({
        'arguments': job['ProgramArguments'], 'exit': executed.returncode,
        'stdout': executed.stdout, 'stderr': executed.stderr}, indent=2))
    assert executed.returncode == 0, executed.stderr
    assert (evidence / 'agent-executed').read_text() == 'literal agent executed\n'
    assert run('repeat-install', loaded=1)['plists'] == first['plists']
    assert 'LOADED (last exit: 0)' in run('loaded-status', '--status', loaded=1)['stdout']
    control.write_text(json.dumps({'query_failure': True}))
    assert 'UNKNOWN' in run('unknown-status', '--status', expected=77, loaded=1)['stderr']
    control.write_text(json.dumps({'bootout_failure': True}))
    failed = run('failed-remove', '--unload', expected=79, loaded=1)
    assert 'fixture bootout rejected' in failed['stderr']
    assert failed['plists'] == first['plists']
    assert run('failed-reload', expected=79, loaded=1)['plists'] == first['plists']
    control.write_text('{}')
    run('state-after-failed-remove', '--status', loaded=1)
    run('recover-install', loaded=1)
    run('remove', '--unload', loaded=0)
    run('repeat-remove', '--unload', loaded=0)
    assert 'NOT LOADED' in run('absent-status', '--status', loaded=0)['stdout']
    control.write_text(json.dumps({'bootstrap_failure': True}))
    run('failed-install', expected=78, loaded=0)
    control.write_text('{}')
    run('recover-failed-install', loaded=1)
    run('remove-before-interruption', '--unload', loaded=0)
    control.write_text(json.dumps({'pause_bootstrap': True}))
    process = subprocess.Popen(['bash', str(installer)], env=environment, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        deadline = time.monotonic() + 30
        while not (evidence / 'bootstrap-paused').exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        assert (evidence / 'bootstrap-paused').exists(), 'interruption seam was not reached'
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=10)
    interrupted = capture('interrupted-install', process.returncode, stdout, stderr)
    assert interrupted['exit'] == -signal.SIGTERM and len(interrupted['loaded']) == 1
    control.write_text('{}')
    run('status-after-interruption', '--status', loaded=1)
    run('recover-interrupted-install', loaded=1)
    run('final-remove', '--unload', loaded=0)
    assert 'NOT LOADED' in run('final-absent-status', '--status', loaded=0)['stdout']
    assert owner.read_bytes() == b'OWNER KEEP\n'
    assert sorted(path.name for path in plists.glob('*.plist')) == ['com.owner.keep.plist']
    (evidence / 'cleanup.json').write_text(json.dumps({
        'owner_sentinel_preserved': True, 'fake_registry_empty': True,
        'managed_plists_absent': True, 'fixture_process_reaped': process.returncode is not None,
        'scope': 'default container HOME only; --init reaps children; --rm destroys container'}, indent=2))
    print(f'PASS: {len(rows)} scheduler lifecycle actions; evidence: {evidence}')


if __name__ == '__main__':
    main()
