#!/usr/bin/env python3
"""Run the grants/RLS recipe in an owned disposable local PostgreSQL container.

Requires Docker and an already available image. Never pulls images, exposes
network ports, or invokes remote database commands. --finish retries only the
guarded disposal of a recorded task; it never creates a database or runs SQL.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import signal
import stat
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
ID = re.compile(r'[a-f0-9]{64}\Z')
NONCE = re.compile(r'[a-f0-9]{32}\Z')
LABEL = 'com.cc-rpi.postgres-recipe.'
SETTLEMENT_SECONDS = 30
DISPOSAL_SECONDS = 20
DOC = 'docs/development/resource-lifecycle.md'


class Refusal(RuntimeError):
    """Ownership or absence could not be proved."""


class WorkloadFailure(RuntimeError):
    def __init__(self, code, phase):
        super().__init__(phase + ' failed')
        self.code = 128 - code if code < 0 else code
        self.phase = phase


def require(condition, reason):
    if not condition:
        raise Refusal(reason)


def disposal_seconds():
    """How long to wait for the daemon's asynchronous --rm removal; RPI_RECIPE_DISPOSAL_SECONDS overrides the default."""
    value = os.environ.get('RPI_RECIPE_DISPOSAL_SECONDS')
    if value is None:
        return DISPOSAL_SECONDS
    require(value.isdigit() and int(value) <= 600, 'RPI_RECIPE_DISPOSAL_SECONDS must be a whole number of seconds from 0 to 600, not %r' % value)
    return int(value)


def now():
    return datetime.now(timezone.utc).isoformat()


def environment():
    return {key: value for key, value in os.environ.items()
            if key in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TZ', 'SYSTEMROOT')}


def birth(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except OSError:
        return 'unknown'
    try:
        result = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart='],
                                env={**environment(), 'LC_ALL': 'C', 'TZ': 'UTC'},
                                capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return 'unknown'
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else 'unknown'


def group_alive(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def private_root():
    home = os.environ.get('HOME', '')
    require(home and os.path.isabs(home) and os.path.isdir(home),
            'HOME is not set to an existing absolute directory; receipts live under $HOME/.local/state/cc-rpi/postgres-recipes')
    root = Path(home).resolve()
    for component in ('.local', 'state', 'cc-rpi', 'postgres-recipes'):
        root = root / component
        root.mkdir(exist_ok=True, mode=0o700)
        value = root.lstat()
        require(stat.S_ISDIR(value.st_mode) and value.st_uid == os.getuid()
                and not value.st_mode & 0o022, 'Unsafe private receipt directory ancestry')
    value = root.lstat()
    require(stat.S_ISDIR(value.st_mode) and value.st_uid == os.getuid()
            and not value.st_mode & 0o077, 'Unsafe private receipt directory')
    return root


def private_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        value = os.fstat(stream.fileno())
        require(stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid()
                and not value.st_mode & 0o077 and value.st_nlink == 1,
                'Unsafe receipt file')
        return json.load(stream)


@contextmanager
def receipt_lock(path):
    lock_path = path.with_suffix('.lock')
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    def verify():
        opened, named = os.fstat(fd), lock_path.lstat()
        require(stat.S_ISREG(named.st_mode) and named.st_uid == os.getuid()
                and not named.st_mode & 0o077 and named.st_nlink == 1
                and (opened.st_dev, opened.st_ino) == (named.st_dev, named.st_ino),
                'Receipt lock identity changed; preserve resources')
    try:
        value = os.fstat(fd)
        require(stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid()
                and not value.st_mode & 0o077 and value.st_nlink == 1, 'Unsafe receipt lock')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Refusal('Receipt is locked by another owner') from error
        verify()
        yield verify
    finally:
        os.close(fd)


def write_receipt(path, receipt, verify):
    verify()
    receipt['updated_at'] = now()
    temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        verify()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_command(args):
    try:
        result = subprocess.run(args, env=environment(), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Refusal('Local inspection did not complete; absence is unproven') from error
    require(result.returncode == 0, 'Local inspection failed; absence is unproven')
    return result.stdout.strip()


def local_endpoint():
    host, context = os.environ.get('DOCKER_HOST'), os.environ.get('DOCKER_CONTEXT')
    require(not (host and context), 'Ambiguous Docker host and context')
    if not host:
        context = context or read_command(['docker', 'context', 'show'])
        result = json.loads(read_command(['docker', 'context', 'inspect', context]))
        require(isinstance(result, list) and len(result) == 1, 'Unknown Docker context')
        host = result[0]['Endpoints']['docker']['Host']
    require(isinstance(host, str) and host.startswith('unix:///') and '\n' not in host,
            'Only an explicit local Unix Docker endpoint is allowed')
    return host


def docker_read(endpoint, *args):
    return read_command(['docker', '--host', endpoint, *args])


def inspect_one(endpoint, *args):
    result = json.loads(docker_read(endpoint, *args))
    require(isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict),
            'Ambiguous Docker inspection')
    return result[0]


def source_commit():
    return read_command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'])


def validate_receipt(path, root):
    require(path.parent == root and path.suffix == '.json' and NONCE.fullmatch(path.stem),
            'Receipt must be an exact task file in the private receipt directory')
    value = private_file(path)
    require(isinstance(value, dict) and value.get('version') == 1
            and value.get('kind') == 'cc-rpi-postgres-recipe'
            and value.get('repository') == 'cc-rpi', 'Unsupported receipt schema')
    require(value.get('task_id') == path.stem and value.get('nonce') == path.stem
            and value.get('name') == 'cc-rpi-recipe-' + path.stem[:12]
            and value.get('lifecycle') == 'disposable'
            and value.get('source', {}).get('root') == str(ROOT.resolve()), 'Receipt source mismatch')
    daemon = value.get('docker', {})
    require(isinstance(daemon.get('endpoint'), str) and daemon['endpoint'].startswith('unix:///')
            and isinstance(daemon.get('id'), str) and daemon['id'], 'Unknown recorded daemon')
    require(re.fullmatch(r'sha256:[a-f0-9]{64}', value.get('image_id', '')),
            'Unknown immutable image identity')
    declared = value.get('declared_volumes')
    require(isinstance(declared, list) and all(isinstance(item, str) and item.startswith('/')
            for item in declared) and len(set(declared)) == len(declared), 'Unknown mount declaration')
    container = value.get('container')
    require(container is None or (isinstance(container, dict) and ID.fullmatch(container.get('id', ''))
            and container.get('name') == '/' + value['name']
            and isinstance(container.get('created'), str) and container['created'].strip()),
            'Unknown recorded container identity')
    volumes = value.get('volumes')
    require(isinstance(volumes, list), 'Unknown recorded mounts')
    for volume in volumes:
        require(isinstance(volume, dict) and ID.fullmatch(volume.get('name', ''))
                and isinstance(volume.get('created'), str) and volume['created'].strip()
                and volume.get('driver') == 'local'
                and isinstance(volume.get('destination'), str), 'Unknown recorded volume identity')
    require(value.get('allocation') in ('pending', 'reconciled') and 'command' in value
            and isinstance(value.get('owner'), dict) and isinstance(value.get('workload'), dict),
            'Incomplete receipt schema')
    if value['allocation'] == 'reconciled':
        require(container is not None and len(volumes) == len(declared)
                and {item['destination'] for item in volumes} == set(declared)
                and len({item['name'] for item in volumes}) == len(volumes),
                'Reconciled mount evidence is incomplete or duplicated')
    return value


class Task:
    def __init__(self, path, receipt, verify):
        self.path, self.receipt = path, receipt
        self.verify = verify
        self.publication_error = None
        self.process = None
        self.interrupted = None
        self.signal_count = 0
        self.cancel_deadline = None

    def save(self):
        try:
            write_receipt(self.path, self.receipt, self.verify)
        except (OSError, Refusal) as error:
            self.publication_error = 'Receipt publication failed: ' + str(error)
            raise

    @contextmanager
    def signals(self):
        handlers = {number: signal.signal(number, self.signal)
                    for number in (signal.SIGINT, signal.SIGTERM)}
        try:
            yield
        finally:
            for number, handler in handlers.items():
                signal.signal(number, handler)

    def signal(self, number, _frame):
        self.signal_count += 1
        self.interrupted = self.interrupted or number
        if self.process is not None:
            self.cancel_deadline = time.monotonic() + SETTLEMENT_SECONDS
            try:
                os.killpg(self.process.pid, number)
            except ProcessLookupError:
                pass

    def checkpoint(self):
        if self.interrupted:
            raise WorkloadFailure(128 + self.interrupted, 'interrupted')

    def command(self, args, purpose, input_text=None, visible=True):
        signals_before = self.signal_count
        if purpose != 'cleanup':
            self.checkpoint()
        self.verify()
        require(self.publication_error is None, 'Earlier receipt publication failed; preserve resources')
        require(self.receipt['command'] is None, 'Unsettled prior command')
        entry = {'id': uuid.uuid4().hex, 'purpose': purpose, 'state': 'launching', 'child': None}
        self.receipt['command'] = entry
        self.save()
        try:
            self.verify()
            process = subprocess.Popen(['docker', '--host', self.receipt['docker']['endpoint'], *args],
                                       env=environment(), text=True, start_new_session=True,
                                       stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as error:
            self.receipt['command'] = None
            self.save()
            raise WorkloadFailure(127, purpose) from error
        self.process = process
        if self.interrupted and (purpose != 'cleanup' or self.signal_count != signals_before):
            self.signal(self.interrupted, None)
        entry.update(state='running', child={'pid': process.pid, 'pgid': process.pid,
                                          'started_at': birth(process.pid)})
        try:
            self.save()
        except BaseException:
            process.terminate()
            self.process = None
            raise
        supplied, settled = False, False
        stdout, stderr = '', ''
        deadline = None
        while True:
            try:
                stdout, stderr = process.communicate(input=None if supplied else input_text, timeout=0.1)
                supplied = True
                if not group_alive(process.pid):
                    settled = True
                    break
                deadline = deadline or time.monotonic() + SETTLEMENT_SECONDS
                time.sleep(0.05)
            except subprocess.TimeoutExpired:
                supplied = True
                if process.poll() is not None:
                    deadline = deadline or time.monotonic() + SETTLEMENT_SECONDS
            if (self.cancel_deadline is not None and time.monotonic() >= self.cancel_deadline
                    or deadline is not None and time.monotonic() >= deadline):
                break
        self.process = None
        outcome = {'status': process.returncode, 'signal': -process.returncode
                   if process.returncode is not None and process.returncode < 0 else None,
                   'settled': settled, 'purpose': purpose}
        if settled and entry['child']['started_at'] not in (None, 'unknown'):
            self.receipt['command'] = None
        else:
            entry['state'] = 'unsettled'
        self.receipt['last_command'] = outcome
        try:
            self.save()
        except (OSError, Refusal):
            if visible:
                print(stdout, end='')
                print(stderr, end='', file=sys.stderr)
            raise
        fd = os.open(self.path.with_suffix('.log'), os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as log:
            log.write(stdout + stderr)
        if visible:
            print(stdout, end='')
            print(stderr, end='', file=sys.stderr)
        require(settled and self.receipt['command'] is None, 'Command settlement or identity is unknown')
        return process.returncode

    def same_daemon(self):
        require(docker_read(self.receipt['docker']['endpoint'], 'info', '--format', '{{.ID}}')
                == self.receipt['docker']['id'], 'Docker daemon identity changed')

    def container_proof(self, cid):
        endpoint = self.receipt['docker']['endpoint']
        item = inspect_one(endpoint, 'container', 'inspect', cid)
        expected = {LABEL + 'nonce': self.receipt['nonce'], LABEL + 'repository': 'cc-rpi',
                    LABEL + 'workdir': self.receipt['source']['root']}
        require(item.get('Id') == cid and item.get('Name') == '/' + self.receipt['name']
                and item.get('Image') == self.receipt['image_id'], 'Container identity changed')
        labels = item.get('Config', {}).get('Labels') or {}
        require(all(labels.get(key) == value for key, value in expected.items()), 'Container ownership changed')
        host = item.get('HostConfig', {})
        require(host.get('AutoRemove') is True and host.get('NetworkMode') == 'none'
                and not host.get('PortBindings') and not item.get('NetworkSettings', {}).get('Ports'),
                'Container isolation changed')
        mounts = item.get('Mounts')
        require(isinstance(item.get('Created'), str) and item['Created'].strip()
                and isinstance(mounts, list), 'Incomplete container inspection')
        require(len(mounts) == len(self.receipt['declared_volumes'])
                and {mount.get('Destination') for mount in mounts} == set(self.receipt['declared_volumes']),
                'Unexpected or incomplete container mounts')
        volumes = []
        for mount in mounts:
            require(mount.get('Type') == 'volume' and ID.fullmatch(mount.get('Name', '')),
                    'Mount is not a task anonymous volume')
            volume = inspect_one(endpoint, 'volume', 'inspect', mount['Name'])
            require(volume.get('Name') == mount['Name'] and volume.get('Driver') == 'local'
                    and isinstance(volume.get('CreatedAt'), str) and volume['CreatedAt'].strip()
                    and 'com.docker.volume.anonymous' in (volume.get('Labels') or {}),
                    'Anonymous volume identity is unknown')
            volumes.append({'name': volume['Name'], 'created': volume['CreatedAt'],
                            'driver': volume['Driver'], 'destination': mount['Destination']})
        return {'id': cid, 'name': item['Name'], 'created': item['Created']}, sorted(volumes, key=lambda v: v['name'])

    def reconcile(self):
        require(self.receipt['command'] is None, 'Allocation command is unsettled')
        cidfile = self.path.with_suffix('.cid')
        require(cidfile.is_file() and not cidfile.is_symlink(), 'Allocation CID is missing or unsafe')
        cid = cidfile.read_text().strip()
        require(ID.fullmatch(cid), 'Allocation CID is incomplete')
        self.same_daemon()
        container, volumes = self.container_proof(cid)
        self.receipt.update(container=container, volumes=volumes, allocation='reconciled')
        self.save()

    def owner_admission(self, current_owner):
        owner = self.receipt['owner']
        require(isinstance(owner.get('pid'), int) and owner['pid'] > 1
                and isinstance(owner.get('started_at'), str)
                and owner['started_at'] not in ('', 'unknown'), 'Recorded owner identity is unknown')
        observed = birth(owner['pid'])
        require(observed != 'unknown', 'Recorded owner liveness is unknown')
        own = current_owner and owner['pid'] == os.getpid() and observed == owner['started_at']
        require(own or observed is None or observed != owner['started_at'], 'Recorded task owner is still live')
        require(self.receipt['command'] is None, 'Unsettled or orphan command intent requires preservation')
        require(self.receipt['allocation'] == 'reconciled', 'Allocation identity remains unresolved')

    def await_absence(self, endpoint, cid):
        """Prove, from fresh inventories, that the container and its anonymous volumes are gone.

        `docker stop` returns when the container has exited; the daemon then removes it (--rm) and its anonymous volumes
        asynchronously. A single inventory straight after the stop can still list the container, so the proof is retried
        for a bounded time. Every attempt re-checks the daemon identity; an inventory that fails is uncertainty, not
        absence, and the last inventory decides: nothing is called gone without having been seen gone."""
        limit = disposal_seconds()
        deadline = time.monotonic() + limit
        while True:
            self.same_daemon()
            ids = docker_read(endpoint, 'ps', '-a', '-q', '--no-trunc').splitlines()
            require(all(ID.fullmatch(value) for value in ids), 'Incomplete post-stop inventory')
            volumes = docker_read(endpoint, 'volume', 'ls', '-q').splitlines()
            if cid not in ids and all(item['name'] not in volumes for item in self.receipt['volumes']):
                return
            if time.monotonic() >= deadline:
                raise Refusal('Recorded container or anonymous volume remains after %d seconds' % limit)
            time.sleep(0.25)

    def cleanup(self, current_owner=False):
        try:
            self.verify()
            require(self.publication_error is None, 'Earlier receipt publication failed; preserve resources')
            self.owner_admission(current_owner)
            self.same_daemon()
            endpoint = self.receipt['docker']['endpoint']
            container = self.receipt['container']
            require(container is not None, 'No complete allocation identity')
            cid = container['id']
            ids = docker_read(endpoint, 'ps', '-a', '-q', '--no-trunc').splitlines()
            require(all(ID.fullmatch(value) for value in ids), 'Incomplete container inventory')
            names = docker_read(endpoint, 'ps', '-a', '-q', '--no-trunc', '--filter',
                                'name=^/' + self.receipt['name'] + '$').splitlines()
            require(all(value == cid for value in names), 'Same-name container replacement is protected')
            if cid in ids:
                current, volumes = self.container_proof(cid)
                require(current == container and volumes == self.receipt['volumes'], 'Recorded resources changed')
                for volume in volumes:
                    consumers = docker_read(endpoint, 'ps', '-a', '-q', '--no-trunc', '--filter',
                                            'volume=' + volume['name']).splitlines()
                    require(all(value == cid for value in consumers), 'Anonymous volume has another consumer')
                self.same_daemon()
                self.cancel_deadline = None
                status = self.command(['stop', cid], 'cleanup', visible=False)
                require(status == 0, 'Owned container stop failed')
            self.await_absence(endpoint, cid)
            self.receipt.update(cleanup={'status': 'disposed'}, state='finished')
        except (Refusal, WorkloadFailure, OSError, ValueError, KeyError, TypeError) as error:
            self.receipt.update(cleanup={'status': 'retained', 'reason': str(error)}, state='retained')
        try:
            self.save()
        except (OSError, Refusal):
            if self.receipt['cleanup']['status'] != 'disposed':
                self.receipt.update(cleanup={'status': 'retained', 'reason': self.publication_error}, state='retained')

    def finish_can_succeed(self):
        """--finish only disposes a reconciled allocation with no unsettled command; nothing else clears an orphan."""
        return self.receipt.get('command') is None and self.receipt.get('allocation') == 'reconciled'

    def next_action(self):
        if self.receipt['cleanup']['status'] == 'disposed' and not self.publication_error:
            return None
        if self.finish_can_succeed():
            return shlex.join([sys.executable, str(Path(__file__).resolve()), '--finish', str(self.path)])
        # An unsettled command or an unreconciled allocation can never pass --finish's guards: repeating it only
        # refuses again. The owner reviews the retained receipt and the daemon's resources by hand.
        return ('--finish cannot clear this receipt (an unsettled command or unresolved allocation is recorded); '
                'review it as the owner: ' + DOC + ', section "Owner review of a retained orphan", receipt ' + str(self.path))

    def report(self):
        value = self.receipt
        print(json.dumps({'task_id': value['task_id'], 'repository': 'cc-rpi', 'state': value['state'],
                          'source_commit': value['source']['commit'],
                          'invocation': value.get('invocation'),
                          'workload': value['workload'], 'cleanup': value['cleanup'],
                          'receipt_path': str(self.path), 'created_at': value['created_at'],
                          'updated_at': value['updated_at'], 'resources': {
                              'container': value['container'], 'volumes': value['volumes'],
                              'image_id': value['image_id']},
                          'finish': value.get('finish'),
                          'next_action': self.next_action()}))

    def finish(self):
        """Retry disposal for a recorded task. The original invocation and workload results are history: they are
        never rewritten here, and the outcome of this retry is recorded separately under `finish`."""
        try:
            self.save()
        except (OSError, Refusal):
            pass  # save latched the error; cleanup must now preserve resources.
        self.cleanup(current_owner=False)
        disposed = self.receipt['cleanup']['status'] == 'disposed'
        code = 0 if disposed and not self.publication_error else 1
        self.receipt['finish'] = {'at': now(), 'exit_code': code, 'cleanup': self.receipt['cleanup']['status']}
        if self.interrupted:
            code = code or 128 + self.interrupted
            self.receipt['finish'].update(exit_code=code, signal=self.interrupted)
        if self.publication_error is None:
            try:
                self.save()
            except (OSError, Refusal):
                code = code or 1
                self.receipt['finish'].update(exit_code=code, evidence_error=self.publication_error)
        self.report()
        original = self.receipt.get('workload', {})
        if original.get('status') in ('failed', 'interrupted'):
            print('NOTE: --finish only disposes resources. The original workload result is unchanged: %s (exit %s). '
                  'Its exit status is not this command\'s.' % (original.get('status'), original.get('exit_code')), file=sys.stderr)
        return code

    def finalize(self, code, current_owner=False):
        try:
            self.save()
        except (OSError, Refusal):
            pass  # save latched the error; cleanup must now preserve resources.
        self.cleanup(current_owner=current_owner)
        if not code and self.interrupted:
            code = 128 + self.interrupted
        if not code and (self.publication_error or self.receipt['cleanup']['status'] != 'disposed'):
            code = 1
        invocation = {'exit_code': code, 'signal': self.interrupted,
                      'evidence_error': self.publication_error}
        self.receipt['invocation'] = invocation
        if self.publication_error is None:
            try:
                self.save()
            except (OSError, Refusal):
                code = code or 1
                invocation.update(exit_code=code, evidence_error=self.publication_error)
                if self.receipt['cleanup']['status'] != 'disposed':
                    self.receipt.update(cleanup={'status': 'retained', 'reason': self.publication_error}, state='retained')
        # A signal can arrive inside the final publication syscall. The first
        # observed signal is immutable, so at most one corrective write is needed.
        if self.interrupted != invocation['signal']:
            code = code or (128 + self.interrupted)
            invocation.update(exit_code=code, signal=self.interrupted)
            if self.publication_error is None:
                try:
                    self.save()
                except (OSError, Refusal):
                    invocation['evidence_error'] = self.publication_error
                    if self.receipt['cleanup']['status'] != 'disposed':
                        self.receipt.update(cleanup={'status': 'retained', 'reason': self.publication_error}, state='retained')
        self.report()
        return code


def recipe_sql():
    content = (ROOT / 'templates/skills/supabase/SKILL.md').read_text()
    blocks = re.findall(r'```sql\n(.*?)```', content, re.S)
    if len(blocks) != 2:
        raise RuntimeError('Expected both table and default-privilege recipes')
    sql = (ROOT / 'tests/recipes/access-setup.sql').read_text()
    sql += '\n' + blocks[1] + '\n' + blocks[0] + '\n'
    sql += (ROOT / 'tests/recipes/access-assertions.sql').read_text()
    return sql


def execute(image_reference, root):
    sql = recipe_sql()
    endpoint = local_endpoint()
    daemon = docker_read(endpoint, 'info', '--format', '{{.ID}}')
    require(daemon, 'Unknown Docker daemon identity')
    image = inspect_one(endpoint, 'image', 'inspect', image_reference)
    require(re.fullmatch(r'sha256:[a-f0-9]{64}', image.get('Id', '')), 'Unknown immutable image identity')
    declared = image.get('Config', {}).get('Volumes', {})
    require(isinstance(declared, dict) and all(isinstance(item, str) and item.startswith('/') for item in declared),
            'Unknown image mount declarations')
    print(image['Id'], json.dumps(image.get('RepoDigests')))
    nonce = uuid.uuid4().hex
    owner_birth = birth(os.getpid())
    require(owner_birth not in (None, 'unknown'), 'Current owner identity is unknown')
    path = root / (nonce + '.json')
    receipt = {'version': 1, 'kind': 'cc-rpi-postgres-recipe', 'repository': 'cc-rpi',
               'task_id': nonce, 'nonce': nonce, 'lifecycle': 'disposable', 'state': 'running',
               'created_at': now(), 'owner': {'pid': os.getpid(), 'started_at': owner_birth},
               'source': {'root': str(ROOT.resolve()), 'commit': source_commit()},
               'docker': {'endpoint': endpoint, 'id': daemon}, 'image_id': image['Id'],
               'declared_volumes': sorted(declared), 'name': 'cc-rpi-recipe-' + nonce[:12],
               'container': None, 'volumes': [], 'allocation': 'pending', 'command': None,
               'workload': {'status': 'pending', 'exit_code': None}, 'cleanup': {'status': 'pending'}}
    with receipt_lock(path) as verify:
        task = Task(path, receipt, verify)
        task.save()
        handlers = {number: signal.signal(number, task.signal) for number in (signal.SIGINT, signal.SIGTERM)}
        code = 1
        try:
            task.same_daemon()
            labels = [part for key, value in {'nonce': nonce, 'repository': 'cc-rpi', 'workdir': str(ROOT.resolve())}.items()
                      for part in ('--label', LABEL + key + '=' + value)]
            status = task.command(['run', '--detach', '--rm', '--pull', 'never', '--network', 'none',
                                   '--name', receipt['name'], '--cidfile', str(path.with_suffix('.cid')), *labels,
                                   '--user', 'postgres', '--entrypoint', 'sh', image['Id'], '-c',
                                   'initdb -D /tmp/rpi-pg --auth=trust >/tmp/rpi-init.log && '
                                   'exec postgres -D /tmp/rpi-pg -k /tmp -c listen_addresses='], 'allocation')
            try:
                task.reconcile()
            except (Refusal, OSError, ValueError, KeyError, TypeError):
                if status:
                    raise WorkloadFailure(status, 'allocation')
                raise
            task.checkpoint()
            if status:
                raise WorkloadFailure(status, 'allocation')
            cid = receipt['container']['id']
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                ready = task.command(['exec', cid, 'pg_isready', '-h', '/tmp'], 'readiness', visible=False)
                task.checkpoint()
                if ready == 0:
                    break
                time.sleep(0.2)
            else:
                raise Refusal('Owned postgres fixture did not become ready')
            status = task.command(['exec', cid, 'postgres', '--version'], 'version')
            if status:
                raise WorkloadFailure(status, 'version')
            status = task.command(['exec', '-i', cid, 'psql', '-h', '/tmp', '-U', 'postgres',
                                   '-d', 'postgres', '-v', 'ON_ERROR_STOP=1'], 'sql', input_text=sql)
            task.checkpoint()
            if status:
                raise WorkloadFailure(status, 'sql')
            code = 0
            receipt['workload'] = {'status': 'passed', 'exit_code': 0}
        except WorkloadFailure as error:
            code = error.code
            receipt['workload'] = {'status': 'interrupted' if task.interrupted else 'failed',
                                   'exit_code': code, 'phase': error.phase}
        except (Refusal, OSError, ValueError, KeyError, TypeError) as error:
            observed = receipt.get('last_command', {})
            if observed.get('purpose') == 'sql' and observed.get('settled') and isinstance(observed.get('status'), int):
                sql_code = observed['status'] if observed['status'] >= 0 else 128 - observed['status']
                code = sql_code or (128 + task.interrupted if task.interrupted else 1)
                receipt['workload'] = {'status': 'failed' if sql_code else 'passed',
                                       'exit_code': sql_code, 'phase': 'sql'}
            else:
                code = 128 + task.interrupted if task.interrupted else 1
                receipt['workload'] = {'status': 'failed', 'exit_code': code, 'reason': str(error)}
        finally:
            try:
                code = task.finalize(code, current_owner=True)
            finally:
                for number, handler in handlers.items():
                    signal.signal(number, handler)
        return code


# (text found in the refusal, why it matters, runnable fix) -- the first match wins.
EXPLANATIONS = (
    ('HOME is not set', 'Receipts and their locks are private to the owner and live under $HOME, so without it there is no place to prove ownership.',
     'export HOME=/absolute/path/of/the/owner/home    # then run the same command again'),
    ('Receipt is locked by another owner', 'Another --image or --finish run holds this receipt; a second writer could race its cleanup.',
     'wait for that run to end, then run the same command again'),
    ('Receipt must be an exact task file', 'Only a receipt this recipe wrote in the private receipt directory can authorize disposal.',
     'pass the path printed as receipt_path or next_action (an absolute path under $HOME/.local/state/cc-rpi/postgres-recipes/)'),
    ('Unsupported receipt schema', 'The file is not a receipt of this recipe, so its resource names cannot be trusted.',
     'run --finish from the checkout that wrote the receipt, with the unedited receipt; never edit a receipt'),
    ('Receipt source mismatch', 'The receipt names a different checkout, so it is not this checkout\'s task.',
     'run --finish from the checkout recorded in the receipt\'s source.root'),
    ('Recorded task owner is still live', 'The run that owns this task is still running; stopping its container would break it.',
     'wait for that run to finish (or stop it with SIGTERM), then run --finish again'),
    ('Unsettled or orphan command intent', 'A command was launched and never recorded as settled, so the daemon may hold a resource this task cannot see.',
     'review it as the owner: ' + DOC + ', section "Owner review of a retained orphan"; --finish cannot clear it'),
    ('Local inspection', 'The recipe could not read the local Docker daemon, and absence is never assumed.',
     'start the local Docker daemon, check "docker context show" names a local Unix socket, then run the same command again'),
    ('Only an explicit local Unix Docker endpoint', 'The recipe never talks to a remote or non-Unix Docker endpoint.',
     'unset DOCKER_HOST or point it (or DOCKER_CONTEXT) at a local unix:/// socket, then run again'),
    ('No such file or directory', 'The receipt named on the command line is not there, so there is nothing to dispose of.',
     'pass the exact absolute path printed as receipt_path or next_action'),
    ('Unsafe', 'Receipts prove ownership only when they are private to this user.',
     'make $HOME/.local/state/cc-rpi/postgres-recipes and its parents owned by you and not writable by group or others (chmod go-w), keep receipt files at mode 600, then run again'),
)


def explain(reason):
    """Print a refusal in the repository's BLOCKED / WHY / FIX form; a refusal never changes a resource."""
    why, fix = ('The recipe could not prove ownership or absence, so it changed nothing.',
                'read ' + DOC + ' ("Completion and recovery"), correct the condition named above, then run the same command again')
    for text, reason_why, reason_fix in EXPLANATIONS:
        if text in reason:
            why, fix = reason_why, reason_fix
            break
    print('BLOCKED: Recipe refused: %s\n\nWHY: %s\n\nFIX:\n  %s' % (reason, why, fix), file=sys.stderr)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--image', help='Already present local postgres image')
    action.add_argument('--finish', help='Exact private task receipt whose disposal should be retried')
    args = parser.parse_args()
    try:
        root = private_root()
        if args.image:
            return execute(args.image, root)
        path = Path(args.finish).absolute()
        validate_receipt(path, root)
        with receipt_lock(path) as verify:
            task = Task(path, validate_receipt(path, root), verify)
            with task.signals():
                return task.finish()
    except (Refusal, OSError, ValueError, KeyError, TypeError) as error:
        explain(str(error))
        return 1


if __name__ == '__main__':
    sys.exit(main())
