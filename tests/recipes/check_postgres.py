#!/usr/bin/env python3
"""Run the documented grants/RLS recipe in an owned disposable local database.

Requires Docker and an already available PostgreSQL image. Never pulls images,
uses existing containers, exposes network ports, or invokes remote db commands.
"""
import argparse
from pathlib import Path
import re
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]


def run(*args, **kwargs):
    return subprocess.run(list(args), check=True, text=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='Already present local postgres image')
    args = parser.parse_args()
    run('docker', 'image', 'inspect', args.image, '--format', '{{.Id}} {{json .RepoDigests}}')
    name = 'cc-rpi-recipe-' + uuid.uuid4().hex[:12]
    content = (ROOT / 'templates/skills/supabase/SKILL.md').read_text()
    blocks = re.findall(r'```sql\n(.*?)```', content, re.S)
    if len(blocks) != 2:
        raise RuntimeError('Expected both table and default-privilege recipes')
    sql = (ROOT / 'tests/recipes/access-setup.sql').read_text()
    sql += '\n' + blocks[1] + '\n' + blocks[0] + '\n'
    sql += (ROOT / 'tests/recipes/access-assertions.sql').read_text()
    created = False
    try:
        run('docker', 'run', '--detach', '--rm', '--network', 'none', '--name', name,
            '--user', 'postgres', '--entrypoint', 'sh', args.image, '-c',
            'initdb -D /tmp/rpi-pg --auth=trust >/tmp/rpi-init.log && '
            'exec postgres -D /tmp/rpi-pg -k /tmp -c listen_addresses=')
        created = True
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            ready = subprocess.run(['docker', 'exec', name, 'pg_isready', '-h', '/tmp'], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError('Owned postgres fixture did not become ready')
        run('docker', 'exec', name, 'postgres', '--version')
        run('docker', 'exec', '-i', name, 'psql', '-h', '/tmp', '-U', 'postgres',
            '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', input=sql)
    finally:
        if created:
            run('docker', 'stop', name, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
