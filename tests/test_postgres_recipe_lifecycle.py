"""Exercise the actual PostgreSQL recipe; only the external Docker CLI is fake."""
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / 'tests/recipes/check_postgres.py'
IMAGE = 'sha256:' + 'c' * 64
CONTAINER = 'a' * 64
VOLUME = 'd' * 64
PRIMARY = 'f' * 64

FAKE_DOCKER = r'''#!__PYTHON__
import json, os, signal, subprocess, sys, time
from pathlib import Path
STATE = Path(__STATE__)
LOG = Path(__LOG__)
HOME = Path(__HOME__)
def read(): return json.loads(STATE.read_text())
def save(s):
    tmp = STATE.with_suffix('.' + str(os.getpid()) + '.tmp')
    tmp.write_text(json.dumps(s)); os.replace(tmp, STATE)
def fail(message, code=1): print(message, file=sys.stderr); sys.exit(code)
args = sys.argv[1:]
endpoint = None
while args and args[0] in ('--host', '-H', '--context'):
    endpoint = args[1]; args = args[2:]
state = read()
with LOG.open('a') as stream:
    stream.write(json.dumps({'args': args, 'endpoint': endpoint,
        'receipt_before': any((HOME / '.local/state/cc-rpi/postgres-recipes').glob('*.json'))}) + '\n')
cid, volume, image = 'a'*64, 'd'*64, 'sha256:'+'c'*64
def option(name, default=None):
    return args[args.index(name)+1] if name in args else default
def selected(items, target):
    return [item for item in items if target in (item.get('Id'), item.get('Name'), item.get('Name','').lstrip('/'))]
def output(items):
    fmt = option('--format', '')
    if fmt and 'RepoDigests' in fmt: print(image + ' []')
    elif fmt in ('{{.Id}}', '{{.ID}}'): print('\n'.join(item.get('Id', item.get('ID','')) for item in items))
    elif fmt == '{{.Name}}': print('\n'.join(item['Name'] for item in items))
    elif fmt == '{{json .}}':
        for item in items: print(json.dumps(item))
    else: print(json.dumps(items))
if state.get('removal_countdown') is not None and args and args[0] == 'ps':
    state['removal_countdown'] -= 1
    if state['removal_countdown'] <= 0:
        state['removal_countdown'] = None
        removed = state['containers'].pop(cid, None)
        if removed:
            for mount in removed.get('Mounts', []): state['volumes'].pop(mount.get('Name'), None)
    save(state)
if args[:2] == ['context','show']: print('fixture-local')
elif args[:2] == ['context','inspect']:
    output([{'Name':'fixture-local','Endpoints':{'docker':{'Host':'unix:///tmp/recipe-fixture.sock'}}}])
elif args and args[0] == 'info':
    daemon = 'daemon-b' if state['mode']=='daemon_drift' and state.get('sql_seen') else 'daemon-a'
    if '{{json .}}' in args: print(json.dumps({'ID':daemon}))
    else: print(daemon)
elif args[:2] == ['image','inspect']:
    if state['mode']=='missing_image': fail('No such image')
    config = {} if state.get('no_declared_volumes') else {'Volumes':{'/var/lib/postgresql/data':{}}}
    output([{'Id':image,'RepoTags':['postgres:fixture'],'RepoDigests':[], 'Config':config}])
elif args and args[0] == 'run':
    if state['mode']=='image_disappeared':
        state['implicit_pull']=option('--pull')!='never';save(state);fail('No such image after inspection',125)
    name=option('--name'); labels={}
    for i,arg in enumerate(args):
        if arg=='--label':
            key,_,value=args[i+1].partition('=');labels[key]=value
    mounts=[] if state.get('no_declared_volumes') and state['mode']!='undeclared_mount' else [{'Type':'volume','Name':volume,'Destination':'/var/lib/postgresql/data','Driver':'local','RW':True}]
    resource={'Id':cid,'Name':'/'+name,'Created':'2026-11-05T10:00:00.000000000Z','Image':image,
      'Config':{'Labels':labels,'Image':image},'HostConfig':{'AutoRemove':True,'NetworkMode':'none','PortBindings':{}},
      'NetworkSettings':{'Ports':{},'Networks':{'none':{}}},'State':{'Running':True},'Mounts':mounts}
    if state['mode']=='empty_created': resource['Created']=''
    state['allocated']=resource
    if state['mode']!='delayed_create':
        state['containers'][cid]=resource
        if mounts: state['volumes'][volume]={'Name':volume,'CreatedAt':'2026-11-05T10:00:00Z','Driver':'local','Labels':{'com.docker.volume.anonymous':''}}
        if mounts and state['mode']=='empty_created_at': state['volumes'][volume]['CreatedAt']=''
    if option('--cidfile') and state['mode'] not in ('no_cid','delayed_create'):
        Path(option('--cidfile')).write_text(('b'*64 if state['mode']=='wrong_cid' else cid)+'\n')
    save(state)
    if state['mode']=='delayed_create':
        source="import json,os,time;from pathlib import Path;time.sleep(.4);p=Path("+repr(str(STATE))+");s=json.loads(p.read_text());s['containers']['a'*64]=s['allocated'];s['volumes']['d'*64]={'Name':'d'*64,'CreatedAt':'2026-11-05T10:00:00Z','Driver':'local','Labels':{'com.docker.volume.anonymous':''}};q=p.with_suffix('.daemon.tmp');q.write_text(json.dumps(s));os.replace(q,p)"
        child=subprocess.Popen([sys.executable,'-c',source],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        state['daemon_child']={'pid':child.pid,'birth':subprocess.check_output(['/bin/ps','-p',str(child.pid),'-o','lstart='],text=True).strip()};save(state)
        sys.exit(143)
    if state['mode'] in ('partial_create','no_cid','wrong_cid'): sys.exit(23)
    if state['mode']=='hold_create':
        state['active_cli']={'pid':os.getpid(),'birth':subprocess.check_output(['/bin/ps','-p',str(os.getpid()),'-o','lstart='],text=True).strip()};save(state)
        def ended(sig,_frame):
            s=read();s['cli_signal']=sig;save(s);sys.exit(128+sig)
        signal.signal(signal.SIGTERM,ended);signal.signal(signal.SIGINT,ended)
        while True: time.sleep(.05)
    print(cid)
elif args and args[0]=='exec':
    if 'pg_isready' in args: sys.exit(0)
    if '--version' in args: print('postgres (PostgreSQL) 17.6')
    elif 'psql' in args:
        state['sql']=sys.stdin.read();state['sql_seen']=True
        if state['mode']=='replace_lock':
            lock=next((HOME / '.local/state/cc-rpi/postgres-recipes').glob('*.lock'))
            lock.unlink();lock.touch(mode=0o600)
        if state['mode']=='absent': state['containers'].pop(cid,None);state['volumes'].pop(volume,None)
        if state['mode']=='replacement':
            original=state['containers'].pop(cid);original['Id']='b'*64;original['Config']['Labels']={'foreign':'replacement'};state['containers']['b'*64]=original
        if state['mode']=='extra_mount': state['containers'][cid]['Mounts'].append({'Type':'volume','Name':'unexpected','Destination':'/extra','Driver':'local'})
        if state['mode']=='foreign_consumer': state['containers']['e'*64]={'Id':'e'*64,'Name':'/foreign-stopped','Created':'old','State':{'Running':False},'Mounts':[{'Type':'volume','Name':volume}]}
        save(state)
        if state['mode'] in ('publication_failure','successful_publication_failure'):
            receipt=next((HOME / '.local/state/cc-rpi/postgres-recipes').glob('*.json'))
            receipt.rename(receipt.with_suffix('.saved'));receipt.mkdir(mode=0o700)
        if state['mode']=='hold_sql':
            state['active_cli']={'pid':os.getpid(),'birth':subprocess.check_output(['/bin/ps','-p',str(os.getpid()),'-o','lstart='],text=True).strip()};save(state)
            def ended(sig,_frame):
                s=read();s['cli_signal']=sig;save(s);sys.exit(128+sig)
            signal.signal(signal.SIGTERM,ended);signal.signal(signal.SIGINT,ended)
            while True: time.sleep(.05)
        if state['mode'] in ('sql_failure','dual_failure','publication_failure'): fail('fixture SQL assertion failed',17)
        print('PASS: recipe assertions')
elif args and (args[0]=='inspect' or args[:2]==['container','inspect']):
    if state['mode']=='inspect_failure' and state.get('sql_seen'): fail('daemon inspection unavailable',67)
    target=args[2] if args[0]=='container' else args[1]
    items=selected(state['containers'].values(),target)
    if not items: fail('Error: No such container: '+target)
    output(items)
elif args[:2]==['volume','inspect']:
    if state['mode']=='volume_inspect_failure' and state.get('sql_seen'): fail('volume inspection unavailable',67)
    items=selected(state['volumes'].values(),args[2])
    if not items: fail('Error: No such volume: '+args[2])
    output(items)
elif args and (args[0]=='ps' or args[:2]==['container','ls']):
    items=list(state['containers'].values())
    for i,arg in enumerate(args):
        if arg=='--filter':
            key,_,value=args[i+1].partition('=')
            if key=='id': items=[x for x in items if x['Id']==value]
            elif key=='name': items=[x for x in items if x['Name'].lstrip('/')==value.strip('^/$')]
            elif key=='volume': items=[x for x in items if any(m.get('Name')==value for m in x.get('Mounts',[]))]
            elif key=='label':
                label,_,expected=value.partition('=');items=[x for x in items if x.get('Config',{}).get('Labels',{}).get(label)==expected]
    print('\n'.join(x['Id'] if '--no-trunc' in args else x['Id'][:12] for x in items))
elif args[:2]==['volume','ls']: print('\n'.join(state['volumes']))
elif args and args[0]=='stop':
    if state['mode'] in ('cleanup_failure','dual_failure'): fail('fixture stop refused',19)
    if state['mode']=='hold_stop':
        state['active_cli']={'pid':os.getpid(),'birth':subprocess.check_output(['/bin/ps','-p',str(os.getpid()),'-o','lstart='],text=True).strip()};save(state)
        received=[]
        def completed(sig,_frame):
            s=read();s['cli_signal']=sig;save(s);received.append(sig)
        signal.signal(signal.SIGTERM,completed);signal.signal(signal.SIGINT,completed)
        while not received: time.sleep(.02)
        state=read()
    target=args[-1];items=selected(state['containers'].values(),target)
    if not items: fail('Error: No such container: '+target)
    if state['mode']=='slow_removal':
        state['removal_countdown']=2;save(state);print(target);sys.exit(0)
    if state['mode']=='stop_keeps':
        print(target);sys.exit(0)
    for item in items:
        state['containers'].pop(item['Id'])
        for mount in item.get('Mounts',[]):
            name=mount.get('Name');used=any(any(m.get('Name')==name for m in c.get('Mounts',[])) for c in state['containers'].values())
            if name and not used: state['volumes'].pop(name,None)
    save(state);print(target)
else: fail('Unsupported fake Docker operation: '+repr(args),97)
'''

TERMINAL_PUBLICATION_AUDIT = r'''"""Observe only this fixture's final receipt rename syscall."""
import errno
import json
import os
from pathlib import Path
import signal
import sys

root = Path(__RECEIPTS__)
state_path = Path(__STATE__)
marker = Path(__MARKER__)
mode = __MODE__

def terminal_boundary(event, args):
    if event != 'os.rename':
        return
    source, destination = Path(args[0]), Path(args[1])
    if destination.parent != root or destination.suffix != '.json':
        return
    value = json.loads(source.read_text())
    if value.get('cleanup', {}).get('status') != 'disposed' or marker.exists():
        return
    invocation = value.get('invocation')
    if mode == 'signal' and (not isinstance(invocation, dict) or invocation.get('exit_code') != 0):
        return
    state = json.loads(state_path.read_text())
    marker.write_text(json.dumps({'pid': os.getpid(), 'mode': mode,
        'container_absent': 'a'*64 not in state['containers'],
        'volume_absent': 'd'*64 not in state['volumes'], 'invocation_before': invocation}))
    if mode == 'failure':
        raise OSError(errno.EIO, 'fixture terminal receipt publication unavailable')
    os.kill(os.getpid(), signal.SIGTERM)

sys.addaudithook(terminal_boundary)
'''


class PostgresRecipeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix='cc-rpi-recipe-lifecycle-')).resolve()
        self.home = self.directory / 'home'
        self.home.mkdir()
        self.state_path = self.directory / 'docker.json'
        self.log_path = self.directory / 'docker.jsonl'
        self.log_path.touch()
        self.initial = {'mode': 'success', 'containers': {PRIMARY: {'Id': PRIMARY,
                        'Name': '/protected-primary', 'Mounts': [{'Type': 'volume', 'Name': 'protected-data'}]}},
                        'volumes': {'protected-data': {'Name': 'protected-data', 'CreatedAt': 'old'}}}
        self.write_state(self.initial)
        binary = self.directory / 'docker'
        binary.write_text(FAKE_DOCKER.replace('__PYTHON__', sys.executable)
                          .replace('__STATE__', repr(str(self.state_path)))
                          .replace('__LOG__', repr(str(self.log_path)))
                          .replace('__HOME__', repr(str(self.home))))
        binary.chmod(0o700)
        self.env = {'PATH': str(self.directory) + os.pathsep + os.environ['PATH'],
                    'HOME': str(self.home), 'LANG': 'C', 'LC_ALL': 'C', 'TZ': 'UTC'}
        self.children = []

    def tearDown(self):
        failures = []
        for child in self.children:
            try:
                if child.poll() is None:
                    child.kill()
            except ProcessLookupError:
                pass
            except OSError as error:
                failures.append(str(error))
        for active in (self.state().get('active_cli'), self.state().get('daemon_child')):
            if not active:
                continue
            try:
                birth = subprocess.run(['/bin/ps', '-p', str(active['pid']), '-o', 'lstart='],
                                       capture_output=True, text=True, env={**os.environ, 'LC_ALL': 'C', 'TZ': 'UTC'})
                if birth.returncode == 0 and birth.stdout.strip() == active['birth']:
                    os.kill(active['pid'], signal.SIGTERM)
                    self.wait_for(lambda: not self.alive(active['pid']))
                elif self.alive(active['pid']):
                    raise RuntimeError('Unknown fixture child ' + str(active['pid']))
            except (OSError, RuntimeError, AssertionError) as error:
                failures.append(str(error))
        for child in self.children:
            try:
                child.communicate(timeout=5)
            except (OSError, subprocess.TimeoutExpired) as error:
                failures.append(str(error))
        try:
            self.assertEqual(self.state()['containers'][PRIMARY], self.initial['containers'][PRIMARY])
            self.assertEqual(self.state()['volumes']['protected-data'], self.initial['volumes']['protected-data'])
        except (KeyError, AssertionError) as error:
            failures.append(str(error))
        if failures:
            self.fail('Fixture evidence retained at ' + str(self.directory) + ': ' + '; '.join(failures))
        shutil.rmtree(self.directory)

    @staticmethod
    def alive(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def state(self):
        return json.loads(self.state_path.read_text())

    def write_state(self, state):
        self.state_path.write_text(json.dumps(state))

    def configure(self, mode, **fields):
        state = self.state();state.update(mode=mode, **fields);self.write_state(state)

    def calls(self):
        return [json.loads(line) for line in self.log_path.read_text().splitlines()]

    def invoke(self, *args):
        return subprocess.run([sys.executable, str(RECIPE), *args], cwd=ROOT, env=self.env,
                              text=True, capture_output=True, timeout=15)

    def recipe(self):
        return self.invoke('--image', 'postgres:fixture')

    def receipt(self):
        files = list((self.home / '.local/state/cc-rpi/postgres-recipes').glob('*.json'))
        self.assertEqual(len(files), 1, 'one durable private task receipt is required')
        return files[0], json.loads(files[0].read_text())

    def result(self, process):
        for line in reversed(process.stdout.splitlines()):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and 'workload' in value and 'cleanup' in value:
                return value
        self.fail('Missing separate workload/cleanup result: ' + process.stdout + process.stderr)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate():
            if time.monotonic() >= deadline:
                self.fail('Fixture readiness/settlement deadline expired')
            time.sleep(0.02)

    def assert_no_mutations(self, calls):
        self.assertFalse([c for c in calls if c['args'][0] in ('run', 'stop', 'rm', 'pull')])

    def test_success_pins_image_and_exact_container_with_unchanged_sql_and_anonymous_cleanup(self):
        process = self.recipe()
        self.assertEqual(process.returncode, 0, process.stderr)
        calls = self.calls();launch = next(c for c in calls if c['args'][0] == 'run')
        self.assertTrue(launch['receipt_before'], 'intent must precede allocation')
        self.assertIn(IMAGE, launch['args']);self.assertNotIn('postgres:fixture', launch['args'])
        self.assertEqual(launch['args'][launch['args'].index('--pull') + 1], 'never')
        self.assertIn('--rm', launch['args']);self.assertIn('--cidfile', launch['args'])
        self.assertEqual(launch['args'][launch['args'].index('--network') + 1], 'none')
        self.assertNotIn('-p', launch['args']);self.assertNotIn('--publish', launch['args'])
        for call in calls:
            if call['args'][0] in ('exec', 'stop'):
                self.assertIn(CONTAINER, call['args'])
        blocks = re.findall(r'```sql\n(.*?)```', (ROOT / 'templates/skills/supabase/SKILL.md').read_text(), re.S)
        expected = (ROOT / 'tests/recipes/access-setup.sql').read_text() + '\n' + blocks[1] + '\n' + blocks[0] + '\n' + (ROOT / 'tests/recipes/access-assertions.sql').read_text()
        self.assertEqual(self.state()['sql'], expected)
        report = self.result(process)
        self.assertEqual(report['workload']['exit_code'], 0);self.assertEqual(report['cleanup']['status'], 'disposed')
        self.assertNotIn(CONTAINER, self.state()['containers']);self.assertNotIn(VOLUME, self.state()['volumes'])
        path, _ = self.receipt();self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_missing_optional_image_volumes_is_valid_and_has_no_mounts(self):
        self.configure('success', no_declared_volumes=True)
        process = self.recipe();self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(self.result(process)['cleanup']['status'], 'disposed')

    def test_undeclared_actual_mount_is_refused_before_sql_or_stop(self):
        self.configure('undeclared_mount', no_declared_volumes=True)
        process = self.recipe();self.assertNotEqual(process.returncode, 0)
        self.assertFalse(self.state().get('sql_seen'))
        self.assertNotEqual(self.result(process)['cleanup']['status'], 'disposed')
        self.assertFalse([c for c in self.calls() if c['args'][0] == 'stop'])

    def test_image_disappearance_never_attempts_implicit_pull(self):
        self.configure('image_disappeared');process = self.recipe()
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse(self.state().get('implicit_pull'), 'run must explicitly forbid missing-image pull')
        self.assertFalse([c for c in self.calls() if c['args'][0] == 'pull'])

    def test_sql_failure_preserves_exact_original_status(self):
        self.configure('sql_failure');process = self.recipe()
        self.assertEqual(process.returncode, 17)
        report = self.result(process);self.assertEqual(report['workload']['exit_code'], 17)
        self.assertEqual(report['cleanup']['status'], 'disposed')

    def test_dual_sql_and_cleanup_failure_preserves_both_outcomes(self):
        self.configure('dual_failure');process = self.recipe()
        self.assertEqual(process.returncode, 17)
        report = self.result(process);self.assertEqual(report['workload']['exit_code'], 17)
        self.assertNotEqual(report['cleanup']['status'], 'disposed');self.assertIn(CONTAINER, self.state()['containers'])
        self.assertIn('--finish', process.stdout + process.stderr)

    def test_partial_created_container_is_reconciled_from_cid_without_sql(self):
        self.configure('partial_create');process = self.recipe()
        self.assertEqual(process.returncode, 23)
        self.assertFalse(self.state().get('sql_seen'));self.assertNotIn(CONTAINER, self.state()['containers'])
        self.assertEqual(self.result(process)['cleanup']['status'], 'disposed')

    def test_ambiguous_create_without_cid_is_retained(self):
        self.configure('no_cid');process = self.recipe()
        self.assertEqual(process.returncode, 23)
        self.assertNotEqual(self.result(process)['cleanup']['status'], 'disposed')
        self.assertFalse([c for c in self.calls() if c['args'][0] == 'stop'])

    def test_wrong_cid_cannot_adopt_a_different_resource(self):
        self.configure('wrong_cid');process = self.recipe()
        self.assertNotEqual(process.returncode, 0)
        self.assertNotEqual(self.result(process)['cleanup']['status'], 'disposed')
        self.assertFalse(self.state().get('sql_seen'))
        self.assertFalse([c for c in self.calls() if c['args'][0] == 'stop'])

    def test_already_absent_container_and_volume_is_successful_cleanup(self):
        self.configure('absent');process = self.recipe()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(self.result(process)['cleanup']['status'], 'disposed')
        self.assertFalse([c for c in self.calls() if c['args'][0] == 'stop'])

    def test_changed_or_unknown_cleanup_proofs_block_stop(self):
        for mode in ('replacement', 'daemon_drift', 'inspect_failure', 'volume_inspect_failure', 'extra_mount', 'foreign_consumer'):
            with self.subTest(mode=mode):
                self.write_state(self.initial);self.log_path.write_text('');self.configure(mode)
                process = self.recipe()
                self.assertNotEqual(process.returncode, 0)
                self.assertNotEqual(self.result(process)['cleanup']['status'], 'disposed')
                self.assertFalse([c for c in self.calls() if c['args'][0] == 'stop'])

    def test_finish_only_tears_down_and_is_repeatable(self):
        self.configure('cleanup_failure');self.recipe();path, _ = self.receipt()
        self.configure('success');before = len(self.calls())
        result = self.invoke('--finish', str(path));self.assertEqual(result.returncode, 0, result.stderr)
        new = self.calls()[before:]
        self.assertFalse([c for c in new if c['args'][0] in ('run', 'exec')])
        self.assertEqual(self.result(result)['cleanup']['status'], 'disposed')
        again = self.invoke('--finish', str(path));self.assertEqual(again.returncode, 0, again.stderr)

    def test_finish_refuses_changed_schema_path_and_uncertain_owner(self):
        self.configure('cleanup_failure');self.recipe();path, original = self.receipt()
        birth = subprocess.check_output(['/bin/ps', '-p', str(os.getpid()), '-o', 'lstart='], text=True,
                                        env={**os.environ, 'LC_ALL': 'C', 'TZ': 'UTC'}).strip()
        cases = ({**original, 'version': 99},
                 {**original, 'owner': {**original['owner'], 'started_at': 'unknown'}},
                 {**original, 'owner': {'pid': os.getpid(), 'started_at': birth}})
        for receipt in cases:
            with self.subTest(receipt=receipt.get('owner')):
                path.write_text(json.dumps(receipt));before = len(self.calls())
                self.assertNotEqual(self.invoke('--finish', str(path)).returncode, 0)
                self.assert_no_mutations(self.calls()[before:])
        path.write_text(json.dumps(original));outside = self.directory / 'forged.json';outside.write_text(path.read_text())
        link = path.with_name('linked.json');link.symlink_to(path)
        for invalid in (outside, link):
            before = len(self.calls());self.assertNotEqual(self.invoke('--finish', str(invalid)).returncode, 0)
            self.assert_no_mutations(self.calls()[before:])

    def test_finish_cannot_cross_an_existing_exclusive_receipt_lock(self):
        self.configure('cleanup_failure');self.recipe();path, _ = self.receipt()
        self.configure('success')
        with path.with_suffix('.lock').open('a+') as guard:
            fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            before = len(self.calls())
            self.assertNotEqual(self.invoke('--finish', str(path)).returncode, 0)
            self.assert_no_mutations(self.calls()[before:])
            fcntl.flock(guard, fcntl.LOCK_UN)
        result = self.invoke('--finish', str(path))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_sigterm_settles_actual_sql_cli_before_cleanup(self):
        self.configure('hold_sql')
        child = subprocess.Popen([sys.executable, str(RECIPE), '--image', 'postgres:fixture'], cwd=ROOT, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.children.append(child);self.wait_for(lambda: bool(self.state().get('active_cli')))
        child.send_signal(signal.SIGTERM);child.wait(timeout=12)
        self.assertNotEqual(child.returncode, 0)
        self.assertEqual(self.state().get('cli_signal'), signal.SIGTERM)
        child.communicate(timeout=5)
        self.assertNotIn(CONTAINER, self.state()['containers']);self.assertNotIn(VOLUME, self.state()['volumes'])

    def test_dead_owner_does_not_authorize_finish_while_allocation_cli_survives(self):
        self.configure('hold_create')
        child = subprocess.Popen([sys.executable, str(RECIPE), '--image', 'postgres:fixture'], cwd=ROOT, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.children.append(child);self.wait_for(lambda: bool(self.state().get('active_cli')))
        child.kill();child.wait(timeout=5)
        path, _ = self.receipt();before = len(self.calls())
        self.assertTrue(self.alive(self.state()['active_cli']['pid']))
        self.assertNotEqual(self.invoke('--finish', str(path)).returncode, 0)
        self.assert_no_mutations(self.calls()[before:])

    def test_delayed_daemon_creation_after_cli_exit_never_looks_disposed(self):
        self.configure('delayed_create');process = self.recipe()
        self.assertNotEqual(process.returncode, 0)
        self.wait_for(lambda: CONTAINER in self.state()['containers'])
        self.assertNotEqual(self.result(process)['cleanup']['status'], 'disposed')
        path, _ = self.receipt();before = len(self.calls())
        self.assertNotEqual(self.invoke('--finish', str(path)).returncode, 0)
        self.assert_no_mutations(self.calls()[before:])

    def test_public_projection_includes_source_commit_and_disposal_evidence(self):
        process = self.recipe()
        self.assertEqual(process.returncode, 0, process.stderr)
        report = self.result(process)
        commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                                         text=True, env=self.env).strip()
        self.assertEqual(report.get('source_commit'), commit)
        self.assertEqual(report['repository'], 'cc-rpi')
        self.assertEqual(report['state'], 'finished')
        path, receipt = self.receipt()
        self.assertEqual(report['task_id'], receipt['task_id'])
        self.assertEqual(report['receipt_path'], str(path))
        self.assertEqual(report['created_at'], receipt['created_at'])
        self.assertEqual(report['updated_at'], receipt['updated_at'])
        self.assertEqual(report['resources']['container']['id'], CONTAINER)
        self.assertEqual(report['resources']['volumes'][0]['name'], VOLUME)
        self.assertEqual(report['workload']['exit_code'], 0)
        self.assertEqual(report['cleanup']['status'], 'disposed')
        self.assertIsNone(report['next_action'])

    def test_replaced_lock_inode_blocks_later_cleanup_mutation(self):
        self.configure('replace_lock')
        process = self.recipe()
        self.assertNotEqual(process.returncode, 0)
        self.assertIn(CONTAINER, self.state()['containers'])
        self.assertFalse([call for call in self.calls() if call['args'][0] == 'stop'])

    def test_sigterm_during_cleanup_is_preserved_even_when_stop_completes_zero(self):
        self.configure('hold_stop')
        child = subprocess.Popen([sys.executable, str(RECIPE), '--image', 'postgres:fixture'],
                                 cwd=ROOT, env=self.env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        self.children.append(child)
        self.wait_for(lambda: bool(self.state().get('active_cli')))
        child.send_signal(signal.SIGTERM)
        stdout, stderr = child.communicate(timeout=12)
        self.assertEqual(self.state().get('cli_signal'), signal.SIGTERM)
        self.assertNotIn(CONTAINER, self.state()['containers'])
        self.assertNotEqual(child.returncode, 0, stdout + stderr)
        report = self.result(subprocess.CompletedProcess(child.args, child.returncode, stdout, stderr))
        self.assertEqual(report['workload']['exit_code'], 0, 'A late signal must not rewrite completed SQL evidence')
        self.assertEqual(report['cleanup']['status'], 'disposed')

    def test_finish_sigterm_forwards_to_owned_stop_and_settles_before_return(self):
        self.configure('cleanup_failure')
        self.recipe()
        path, _ = self.receipt()
        self.configure('hold_stop')
        child = subprocess.Popen([sys.executable, str(RECIPE), '--finish', str(path)],
                                 cwd=ROOT, env=self.env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        self.children.append(child)
        self.wait_for(lambda: bool(self.state().get('active_cli')))
        child.send_signal(signal.SIGTERM)
        child.wait(timeout=12)
        self.assertEqual(self.state().get('cli_signal'), signal.SIGTERM)
        self.assertFalse(self.alive(self.state()['active_cli']['pid']))
        stdout, stderr = child.communicate(timeout=5)
        self.assertNotEqual(child.returncode, 0, stdout + stderr)
        self.assertNotIn(CONTAINER, self.state()['containers'])

    def test_incomplete_mount_receipt_cannot_dispose_absent_container_with_remaining_volume(self):
        self.configure('cleanup_failure')
        self.recipe()
        path, receipt = self.receipt()
        state = self.state()
        state['mode'] = 'success'
        state['containers'].pop(CONTAINER)
        self.write_state(state)
        receipt['volumes'] = []
        path.write_text(json.dumps(receipt))
        before = len(self.calls())
        process = self.invoke('--finish', str(path))
        self.assertNotEqual(process.returncode, 0)
        self.assertIn(VOLUME, self.state()['volumes'])
        self.assert_no_mutations(self.calls()[before:])

    def test_empty_creation_identity_blocks_sql_and_disposal(self):
        for mode in ('empty_created', 'empty_created_at'):
            with self.subTest(mode=mode):
                self.write_state(self.initial)
                self.log_path.write_text('')
                self.configure(mode)
                process = self.recipe()
                self.assertNotEqual(process.returncode, 0)
                self.assertFalse(self.state().get('sql_seen'))
                self.assertFalse([call for call in self.calls() if call['args'][0] == 'stop'])
                self.assertNotEqual(self.result(process)['cleanup']['status'], 'disposed')

    def publication_failure(self, mode):
        self.configure(mode)
        root = self.home / '.local/state/cc-rpi/postgres-recipes'
        try:
            return self.recipe()
        finally:
            # Restore only the fixture's exact receipt target after its process
            # has settled. No permission changes or detached fault injector.
            for saved in root.glob('*.saved'):
                target = saved.with_suffix('.json')
                if target.is_dir():
                    target.rmdir()
                saved.rename(target)

    def test_publication_failure_keeps_original_sql_status_and_separate_cleanup_failure(self):
        process = self.publication_failure('publication_failure')
        self.assertEqual(process.returncode, 17, process.stdout + process.stderr)
        report = self.result(process)
        self.assertEqual(report['workload']['exit_code'], 17)
        self.assertEqual(report['cleanup']['status'], 'retained')
        self.assertTrue(report['cleanup'].get('reason'))
        self.assertIn('--finish', report['next_action'])
        self.assertIn(CONTAINER, self.state()['containers'])

    def test_publication_failure_after_successful_sql_cannot_report_pass(self):
        process = self.publication_failure('successful_publication_failure')
        self.assertNotEqual(process.returncode, 0)
        report = self.result(process)
        self.assertEqual(report['workload']['exit_code'], 0)
        self.assertEqual(report['cleanup']['status'], 'retained')
        self.assertTrue(report['cleanup'].get('reason'))
        self.assertIn('--finish', report['next_action'])
        self.assertIn(CONTAINER, self.state()['containers'])

    def terminal_publication(self, mode):
        hooks = self.directory / 'terminal-hooks'
        hooks.mkdir()
        marker = self.directory / 'terminal-boundary.json'
        source = (TERMINAL_PUBLICATION_AUDIT
                  .replace('__RECEIPTS__', repr(str(self.home / '.local/state/cc-rpi/postgres-recipes')))
                  .replace('__STATE__', repr(str(self.state_path)))
                  .replace('__MARKER__', repr(str(marker)))
                  .replace('__MODE__', repr(mode)))
        (hooks / 'sitecustomize.py').write_text(source)
        self.env['PYTHONPATH'] = str(hooks)
        try:
            process = self.recipe()
        finally:
            self.env.pop('PYTHONPATH')
        observed = json.loads(marker.read_text())
        self.assertTrue(observed['container_absent'])
        self.assertTrue(observed['volume_absent'])
        self.assertNotIn(CONTAINER, self.state()['containers'])
        self.assertNotIn(VOLUME, self.state()['volumes'])
        return process, observed

    def test_terminal_publication_failure_preserves_verified_disposal(self):
        process, _ = self.terminal_publication('failure')
        self.assertNotEqual(process.returncode, 0)
        report = self.result(process)
        self.assertEqual(report['workload']['exit_code'], 0)
        self.assertEqual(report['cleanup']['status'], 'disposed')
        self.assertTrue(report['invocation']['evidence_error'])
        self.assertNotEqual(report['invocation']['exit_code'], 0)

    def test_terminal_publication_signal_keeps_sql_and_disposal_but_interrupts_invocation(self):
        process, observed = self.terminal_publication('signal')
        self.assertEqual(observed['invocation_before']['exit_code'], 0)
        self.assertEqual(process.returncode, 128 + signal.SIGTERM)
        report = self.result(process)
        self.assertEqual(report['workload']['exit_code'], 0)
        self.assertEqual(report['cleanup']['status'], 'disposed')
        self.assertEqual(report['invocation']['signal'], signal.SIGTERM)
        self.assertEqual(report['invocation']['exit_code'], 128 + signal.SIGTERM)

    # --- WB2-P-1 to WB2-P-6 -------------------------------------------------------------------------------------
    def test_only_the_container_carries_the_task_labels_and_the_receipt_names_the_anonymous_volumes(self):
        self.assertEqual(self.recipe().returncode, 0)
        launch = next(c for c in self.calls() if c['args'][0] == 'run')
        labels = [launch['args'][i + 1] for i, arg in enumerate(launch['args']) if arg == '--label']
        self.assertEqual(len(labels), 3, 'nonce, repository and workdir labels go on the container')
        self.assertTrue(all(label.startswith('com.cc-rpi.postgres-recipe.') for label in labels))
        # `docker run` offers no label for an anonymous volume, so the volume names live in the receipt.
        self.assertNotIn('volume', [a for a in launch['args'] if a in ('--volume', '-v', '--mount')])
        _, receipt = self.receipt()
        self.assertEqual([item['name'] for item in receipt['volumes']], [VOLUME])

    def test_the_review_steps_do_not_look_for_volume_labels_that_anonymous_volumes_never_get(self):
        text = (ROOT / 'docs/development/resource-lifecycle.md').read_text()
        flat = ' '.join(text.split())
        self.assertTrue('volume ls --filter "label=' not in text, 'a label filter cannot find anonymous volumes')
        self.assertTrue('every resource carries' not in flat, 'only the container carries the labels')
        for needle in ('Only the container carries these labels', 'anonymous volumes inherit no label', 'volume inspect VOLUME_NAME'):
            self.assertTrue(needle in flat, 'missing: ' + needle)

    def test_the_owner_liveness_check_prints_nothing_for_a_missing_process_on_macos_too(self):
        text = (ROOT / 'docs/development/resource-lifecycle.md').read_text()
        for needle in ('ps -p OWNER_PID -o pid=', 'ps -p CHILD_PID -o pid='):
            self.assertTrue(needle in text, 'missing: ' + needle)
        self.assertTrue(re.search(r'ps -p (OWNER|CHILD)_PID\s+#', text) is None, 'a bare ps -p prints a header on macOS')
        # The same check as the doc gives, run on a pid that cannot exist: no output, nonzero status, on this OS.
        gone = subprocess.run(['ps', '-p', '999999', '-o', 'pid='], capture_output=True, text=True)
        self.assertEqual((gone.stdout.strip(), gone.returncode), ('', 1))

    def test_an_orphan_receipt_points_at_the_owner_review_instead_of_a_finish_that_cannot_succeed(self):
        self.configure('no_cid');process = self.recipe()
        report = self.result(process)
        self.assertNotEqual(report['cleanup']['status'], 'disposed')
        self.assertTrue(report['next_action'].startswith('--finish cannot clear this receipt'), report['next_action'])
        self.assertIn('docs/development/resource-lifecycle.md', report['next_action'])
        self.assertIn('Owner review of a retained orphan', report['next_action'])
        self.assertIn(report['receipt_path'], report['next_action'])
        path, _ = self.receipt()
        again = self.invoke('--finish', str(path))
        self.assertNotEqual(again.returncode, 0, 'the finish this used to advertise really cannot succeed')

    def test_a_retained_but_reconciled_receipt_still_advertises_the_finish_command(self):
        self.configure('dual_failure');report = self.result(self.recipe())
        path, _ = self.receipt()
        self.assertIn('--finish', report['next_action'])
        self.assertIn(str(path), report['next_action'])
        self.assertFalse(report['next_action'].startswith('--finish cannot'))

    def test_finish_on_a_failed_sql_receipt_does_not_rewrite_the_recorded_invocation(self):
        self.configure('dual_failure');first = self.recipe()
        self.assertEqual(first.returncode, 17)
        path, before = self.receipt()
        self.assertEqual(before['invocation']['exit_code'], 17)
        self.configure('success')
        result = self.invoke('--finish', str(path))
        self.assertEqual(result.returncode, 0, 'finish reports its own disposal result: ' + result.stderr)
        _, after = self.receipt()
        self.assertEqual(after['invocation'], before['invocation'], 'the original invocation is history')
        self.assertEqual(after['workload'], before['workload'])
        self.assertEqual(after['finish']['cleanup'], 'disposed')
        self.assertEqual(after['finish']['exit_code'], 0)
        report = self.result(result)
        self.assertEqual(report['invocation']['exit_code'], 17)
        self.assertEqual(report['finish']['cleanup'], 'disposed')
        self.assertEqual(report['workload']['exit_code'], 17)
        self.assertIn('NOTE: --finish only disposes resources', result.stderr)
        self.assertIn('failed (exit 17)', result.stderr)

    def test_a_refusal_is_blocked_why_fix_with_a_runnable_fix(self):
        missing = self.home / '.local/state/cc-rpi/postgres-recipes' / ('0' * 32 + '.json')
        result = self.invoke('--finish', str(missing))
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith('BLOCKED: Recipe refused: '), result.stderr)
        self.assertRegex(result.stderr, r'\n\nWHY: .+\n\nFIX:\n  .+')
        self.assertIn('receipt_path or next_action', result.stderr)
        foreign = self.directory / 'foreign.json'
        foreign.write_text('{}')
        result = self.invoke('--finish', str(foreign))
        self.assertIn('FIX:\n  pass the path printed as receipt_path or next_action', result.stderr)

    def test_a_locked_receipt_refusal_says_to_wait(self):
        self.configure('cleanup_failure');self.recipe();path, _ = self.receipt()
        with path.with_suffix('.lock').open('a+') as guard:
            fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.invoke('--finish', str(path))
            fcntl.flock(guard, fcntl.LOCK_UN)
        self.assertEqual(result.returncode, 1)
        self.assertIn('BLOCKED: Recipe refused: Receipt is locked by another owner', result.stderr)
        self.assertIn('FIX:\n  wait for that run to end', result.stderr)

    def test_receipts_follow_home_and_an_unset_home_is_refused_before_any_docker_call(self):
        for label, env in (('unset', {k: v for k, v in self.env.items() if k != 'HOME'}), ('relative', {**self.env, 'HOME': 'relative/home'}),
                           ('empty', {**self.env, 'HOME': ''}), ('missing', {**self.env, 'HOME': str(self.directory / 'no-such-home')})):
            with self.subTest(home=label):
                result = subprocess.run([sys.executable, str(RECIPE), '--image', 'postgres:fixture'], cwd=ROOT, env=env, text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertTrue(result.stderr.startswith('BLOCKED: Recipe refused: HOME is not set to an existing absolute directory'), result.stderr)
                self.assertIn('FIX:\n  export HOME=', result.stderr)
                self.assertEqual(self.calls(), [], 'no Docker call was made')
        # With HOME set, the receipts are exactly where the doc says, not in the passwd-database home.
        self.assertEqual(self.recipe().returncode, 0)
        self.assertEqual(len(list((self.home / '.local/state/cc-rpi/postgres-recipes').glob('*.json'))), 1)

    def test_a_container_the_daemon_removes_a_moment_after_stop_is_still_proven_gone(self):
        # --rm removal is asynchronous: the first inventory after `docker stop` can still list the container.
        self.configure('slow_removal');process = self.recipe()
        self.assertEqual(process.returncode, 0, process.stderr)
        report = self.result(process)
        self.assertEqual(report['cleanup']['status'], 'disposed')
        self.assertNotIn(CONTAINER, self.state()['containers'])
        inventories = [c for c in self.calls() if c['args'][:2] == ['ps', '-a'] and '--filter' not in c['args']]
        self.assertGreaterEqual(len(inventories), 3, 'the proof was retried until the container was seen gone')

    def test_a_container_that_never_disappears_is_retained_after_a_bounded_wait(self):
        self.configure('stop_keeps');self.env['RPI_RECIPE_DISPOSAL_SECONDS'] = '1'
        started = time.monotonic();process = self.recipe()
        self.assertNotEqual(process.returncode, 0)
        self.assertLess(time.monotonic() - started, 12)
        report = self.result(process)
        self.assertEqual(report['cleanup']['status'], 'retained')
        self.assertIn('remains after 1 seconds', report['cleanup']['reason'])
        self.assertIn(CONTAINER, self.state()['containers'])
        self.assertIn('--finish', report['next_action'])
        del self.env['RPI_RECIPE_DISPOSAL_SECONDS']
        self.configure('success')
        path, _ = self.receipt()
        self.assertEqual(self.invoke('--finish', str(path)).returncode, 0, 'the retained receipt is still finishable')

    def test_an_invalid_disposal_wait_is_retained_with_the_variable_named(self):
        self.env['RPI_RECIPE_DISPOSAL_SECONDS'] = 'soon'
        process = self.recipe()
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('RPI_RECIPE_DISPOSAL_SECONDS must be a whole number', self.result(process)['cleanup']['reason'])


if __name__ == '__main__':
    unittest.main()
